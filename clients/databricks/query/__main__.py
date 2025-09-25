#!/usr/bin/env python3
"""
Databricks Statement Execution API (no external deps)

Env vars (required):
  DATABRICKS_HOST           e.g. https://abc-12345.cloud.databricks.com
  DATABRICKS_TOKEN          personal access token
  DATABRICKS_WAREHOUSE_ID   SQL Warehouse ID
Optional:
  DATABRICKS_CATALOG
  DATABRICKS_SCHEMA
  QUERY                     SQL text (fallback if not passed as --query)
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error

API_BASE = "/api/2.0/sql/statements"


def env(name: str, required: bool = True, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        sys.exit(f"Missing required env var: {name}")
    return val


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _http_json(method: str, url: str, headers: dict, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return json.loads(body.decode("utf-8")) if body else {}
    except urllib.error.HTTPError as e:
        details = e.read().decode("utf-8") if e.fp else ""
        msg = f"HTTP {e.code} {e.reason} for {url}\n{details}"
        raise RuntimeError(msg) from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error for {url}: {e.reason}") from None


def submit_statement(host: str, token: str, warehouse_id: str, statement: str,
                     catalog: str | None, schema: str | None) -> str:
    url = f"{host}{API_BASE}"
    payload: dict = {
        "statement": statement,
        "warehouse_id": warehouse_id,
        # result format "JSON_ARRAY" is default; leaving implicit.
    }
    options: dict = {}
    if catalog:
        options["catalog"] = catalog
    if schema:
        options["schema"] = schema
    if options:
        payload["options"] = options

    resp = _http_json("POST", url, _headers(token), payload)
    return resp["statement_id"]


def wait_for_done(host: str, token: str, statement_id: str, timeout_s: int = 600, poll_s: float = 1.0) -> dict:
    url = f"{host}{API_BASE}/{statement_id}"
    deadline = time.time() + timeout_s
    while True:
        resp = _http_json("GET", url, _headers(token))
        state = resp.get("status", {}).get("state", "UNKNOWN")
        if state in ("SUCCEEDED", "FAILED", "CANCELED"):
            return resp
        if time.time() > deadline:
            raise TimeoutError(f"Timed out waiting for statement {statement_id} to finish (last state={state})")
        time.sleep(poll_s)


def fetch_chunk(host: str, token: str, statement_id: str, chunk_index: int) -> dict:
    url = f"{host}{API_BASE}/{statement_id}/result/chunks/{chunk_index}"
    return _http_json("GET", url, _headers(token))


def collect_rows(result_envelope: dict, host: str, token: str, statement_id: str) -> tuple[list[dict], list[dict]]:
    """
    Returns (rows, columns), where:
      - rows is a list of dicts (col_name -> value)
      - columns is the raw schema column list from the API
    """
    # schema
    columns = result_envelope.get("manifest", {}).get("schema", {}).get("columns", [])
    col_names = [c.get("name") for c in columns]

    rows: list[dict] = []

    # first page of data (if present)
    first_data = result_envelope.get("result", {}).get("data_array", [])
    for arr in first_data:
        rows.append({col_names[i]: arr[i] for i in range(len(col_names))})

    # chunk pagination
    next_chunk = result_envelope.get("next_chunk_index")
    while next_chunk is not None:
        chunk = fetch_chunk(host, token, statement_id, next_chunk)
        data = chunk.get("data_array", [])
        for arr in data:
            rows.append({col_names[i]: arr[i] for i in range(len(col_names))})
        next_chunk = chunk.get("next_chunk_index")

    return rows, columns


def main():
    parser = argparse.ArgumentParser(description="Run a SELECT via Databricks Statement Execution API (stdlib only).")
    parser.add_argument("--query", help="SQL to execute (defaults to QUERY env var)")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds (default: 600)")
    args = parser.parse_args()

    host = env("DATABRICKS_HOST")
    token = env("DATABRICKS_TOKEN")
    warehouse_id = env("DATABRICKS_WAREHOUSE_ID")
    catalog = os.environ.get("DATABRICKS_CATALOG")
    schema = os.environ.get("DATABRICKS_SCHEMA")
    statement = args.query or env("QUERY", required=False)
    if not statement:
        statement = sys.stdin.read()

    # normalize host (no trailing slash)
    host = host.rstrip("/")

    try:
        stmt_id = submit_statement(host, token, warehouse_id, statement, catalog, schema)
        status = wait_for_done(host, token, stmt_id, timeout_s=args.timeout)

        state = status.get("status", {}).get("state")
        if state != "SUCCEEDED":
            err = status.get("status", {}).get("error", {})
            message = err.get("message") or json.dumps(err)
            raise RuntimeError(f"Statement {stmt_id} ended in state {state}: {message}")

        rows, columns = collect_rows(status, host, token, stmt_id)

        out = {
            "statement_id": stmt_id,
            "state": state,
            "row_count": len(rows),
            "columns": columns,   # includes names & types
            "rows": rows,
        }
        print(json.dumps(out, indent=2))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
