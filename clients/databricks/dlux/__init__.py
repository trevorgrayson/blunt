#!/usr/bin/env python3
"""
List Databricks failed queries due to privilege/authorization errors
from system.query.history (workspace scope), with principal and resource hint.

Env:
  DATABRICKS_HOST   e.g. https://abc-12345.cloud.databricks.com
  DATABRICKS_TOKEN  PAT with SQL access
  WAREHOUSE_ID      Any SQL warehouse that can read System Tables

CLI:
  --limit N         Max rows (default 1000)
  --where "..."     Extra SQL filter (optional), e.g.:
                    --where "client_application = 'Tableau'"
  --show-sql        Print the SQL before execution

Output: JSON array with keys:
  account_id, workspace_id, statement_id, executed_by, executed_by_user_id,
  warehouse_id, client_application, client_driver, statement_type,
  resource_hint, error_message
"""

import os, sys, json, time, argparse, re
import urllib.request, urllib.error

API_BASE = "/api/2.0/sql/statements"

# Common wording we see for auth/privilege failures (case-insensitive RLIKE)
PRIVILEGE_PATTERNS = [
    "not authorized",
    "permission denied",
    "insufficient privileges",
    "does not have .* privilege",
    "requires .* privilege",
    "operation not allowed",
    "access denied",
    "unauthorized",
    "permission required",
]

# Pull likely object identifiers out of error text (best-effort).
RESOURCE_REGEXES = [
    re.compile(r"`([A-Za-z0-9_\-]+)`\.`([A-Za-z0-9_\-]+)`\.`([A-Za-z0-9_\-]+)`"),
    re.compile(r"(catalog|schema|table|view|function|volume|share|database|external location|storage credential)\s+`([^`]+)`", re.IGNORECASE),
    re.compile(r"\b([A-Za-z0-9_\-]+)\.([A-Za-z0-9_\-]+)\.([A-Za-z0-9_\-]+)\b"),
    re.compile(r"(table|view|function|volume)\s+([A-Za-z0-9_\-]+)", re.IGNORECASE),
]

def env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        sys.exit(f"Missing required environment variable: {name}")
    return v

def http_json(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = None
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} calling {url}:\n{detail}") from None

def execute_sql_and_collect(host: str, token: str, warehouse_id: str, sql: str, poll_secs: float = 1.5, max_wait_secs: int = 180) -> list[dict]:
    print(sql)
    start = http_json("POST", f"{host}{API_BASE}", token, {
        "statement": sql,
        "warehouse_id": warehouse_id,
        "disposition": "EXTERNAL_LINKS",
        "wait_timeout": "0s",
    })
    statement_id = start.get("statement_id") or start.get("id")
    if not statement_id:
        raise SystemExit(f"Could not obtain statement_id from response: {start}")

    deadline = time.time() + max_wait_secs
    status = start.get("status", {})
    while status.get("state") not in ("SUCCEEDED", "FAILED", "CANCELED"):
        if time.time() > deadline:
            raise SystemExit(f"Timed out waiting for statement {statement_id} to finish.")
        time.sleep(poll_secs)
        res = http_json("GET", f"{host}{API_BASE}/{statement_id}", token)
        status = res.get("status", {})
        if status.get("state") in ("SUCCEEDED", "FAILED", "CANCELED"):
            start = res
            break

    if status.get("state") != "SUCCEEDED":
        raise SystemExit(f"Statement did not succeed: {status}")

    result = start.get("result", {})
    cols = [c["name"] for c in result.get("schema", {}).get("columns", [])]
    rows = []

    for link in result.get("manifest", {}).get("external_links", []):
        url = link.get("external_link")
        if not url:
            continue
        with urllib.request.urlopen(url) as resp:
            chunk = json.loads(resp.read().decode("utf-8"))
        for arr in chunk.get("data_array", []):
            rows.append(dict(zip(cols, arr)))
    return rows

def build_sql(limit: int, where_extra: str | None) -> str:
    # like_filters = " OR ".join([f"lower(error_message) RLIKE '{p}'" for p in PRIVILEGE_PATTERNS])
    where = f"""
WHERE execution_status = 'FAILED'
"""
    # AND ({like_filters})
    if where_extra:
        where += f"  AND ({where_extra})\n"
    # Only use columns present in your provided schema
    sql = f"""
SELECT
  account_id,
  workspace_id,
  statement_id,
  executed_by,
  executed_by_user_id,
  compute.warehouse_id AS warehouse_id,
  client_application,
  client_driver,
  statement_type,
  error_message,
  statement_text
FROM system.query.history
{where}
LIMIT {int(limit)}
"""
    # Strip trailing spaces for readability in --show-sql
    return "\n".join(line.rstrip() for line in sql.splitlines())

def extract_resource_hint(error_message: str, statement_text: str | None = None) -> str | None:
    if error_message:
        for rx in RESOURCE_REGEXES:
            m = rx.search(error_message)
            if m:
                parts = [g for g in m.groups()
                         if g and g.lower() not in {"catalog","schema","table","view","function","volume","share","database","external location","storage credential"}]
                if parts:
                    return ".".join(parts)
    if statement_text:
        m = re.search(r"\b([A-Za-z0-9_\-]+)\.([A-Za-z0-9_\-]+)\.([A-Za-z0-9_\-]+)\b", statement_text)
        if m:
            return ".".join(m.groups())
    return None

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=1000, help="Max rows to return (default 1000)")
    ap.add_argument("--where", type=str, default=None, help="Extra SQL filter (without WHERE). E.g. executed_by = 'alice@acme.com'")
    ap.add_argument("--show-sql", action="store_true", help="Print the SQL that will be executed")
    args = ap.parse_args()

    host = env("DATABRICKS_HOST").rstrip("/")
    token = env("DATABRICKS_TOKEN")
    warehouse_id = env("WAREHOUSE_ID")

    sql = build_sql(args.limit, args.where)
    if args.show_sql:
        print("-- SQL to be executed:\n", sql, file=sys.stderr)

    rows = execute_sql_and_collect(host, token, warehouse_id, sql)

    out = []
    for r in rows:
        resource_hint = extract_resource_hint(r.get("error_message") or "", r.get("statement_text") or "")
        out.append({
            "account_id": r.get("account_id"),
            "workspace_id": r.get("workspace_id"),
            "statement_id": r.get("statement_id"),
            "executed_by": r.get("executed_by"),
            "executed_by_user_id": r.get("executed_by_user_id"),
            "warehouse_id": r.get("warehouse_id"),
            "client_application": r.get("client_application"),
            "client_driver": r.get("client_driver"),
            "statement_type": r.get("statement_type"),
            "resource_hint": resource_hint,
            "error_message": r.get("error_message"),
        })

    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
