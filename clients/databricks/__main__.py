#!/usr/bin/env python3
"""
Databricks client utilities.

Current verbs:
  tail   Poll system.query.history and stream new rows to stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Iterable
import urllib.error
import urllib.request

from .resources import run_resource_browser


API_BASE = "/api/2.0/sql/statements"


def env(name: str, required: bool = True, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        sys.exit(f"Missing required environment variable: {name}")
    return value


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _http_json(method: str, url: str, headers: dict[str, str], payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return json.loads(body.decode("utf-8")) if body else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason} for {url}\n{detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error for {url}: {e.reason}") from None


def submit_statement(host: str, token: str, warehouse_id: str, statement: str) -> str:
    response = _http_json(
        "POST",
        f"{host}{API_BASE}",
        _headers(token),
        {
            "statement": statement,
            "warehouse_id": warehouse_id,
            "wait_timeout": "0s",
            "disposition": "EXTERNAL_LINKS",
        },
    )
    statement_id = response.get("statement_id") or response.get("id")
    if not statement_id:
        raise RuntimeError(f"Could not obtain statement_id from response: {response}")
    return statement_id


def wait_for_statement(host: str, token: str, statement_id: str, timeout_s: int = 300, poll_s: float = 1.0) -> dict:
    deadline = time.time() + timeout_s
    while True:
        response = _http_json("GET", f"{host}{API_BASE}/{statement_id}", _headers(token))
        state = response.get("status", {}).get("state", "UNKNOWN")
        if state in ("SUCCEEDED", "FAILED", "CANCELED"):
            return response
        if time.time() > deadline:
            raise TimeoutError(f"Timed out waiting for statement {statement_id} to finish (last state={state})")
        time.sleep(poll_s)


def collect_rows(result_envelope: dict) -> list[dict]:
    columns = result_envelope.get("manifest", {}).get("schema", {}).get("columns", [])
    col_names = [c.get("name") for c in columns]
    rows: list[dict] = []

    for arr in result_envelope.get("result", {}).get("data_array", []):
        rows.append({col_names[i]: arr[i] for i in range(min(len(col_names), len(arr)))})

    for link in result_envelope.get("manifest", {}).get("external_links", []):
        url = link.get("external_link")
        if not url:
            continue
        with urllib.request.urlopen(url) as resp:
            chunk = json.loads(resp.read().decode("utf-8"))
        for arr in chunk.get("data_array", []):
            rows.append({col_names[i]: arr[i] for i in range(min(len(col_names), len(arr)))})

    return rows


def query_rows(host: str, token: str, warehouse_id: str, sql: str, timeout_s: int = 300) -> list[dict]:
    statement_id = submit_statement(host, token, warehouse_id, sql)
    result = wait_for_statement(host, token, statement_id, timeout_s=timeout_s)
    if result.get("status", {}).get("state") != "SUCCEEDED":
        err = result.get("status", {}).get("error", {})
        message = err.get("message") or json.dumps(err)
        raise RuntimeError(f"Statement {statement_id} ended in state {result.get('status', {}).get('state')}: {message}")
    return collect_rows(result)


def _normalize_statement_text(statement_text: str | None, width: int = 120) -> str:
    if not statement_text:
        return ""
    text = " ".join(statement_text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def _format_row(row: dict) -> str:
    start_time = row.get("start_time") or row.get("update_time") or ""
    if isinstance(start_time, datetime):
        start_time = start_time.isoformat()
    status = row.get("execution_status") or "UNKNOWN"
    executed_by = row.get("executed_by") or "unknown"
    statement_id = row.get("statement_id") or "-"
    statement_type = row.get("statement_type") or "UNKNOWN"
    statement_text = _normalize_statement_text(row.get("statement_text"))
    client_application = row.get("client_application") or "unknown-client"
    prefix = f"{start_time} [{status}] {executed_by} {statement_type} {statement_id}"
    suffix = f" ({client_application})"
    return f"{prefix}{suffix}" if not statement_text else f"{prefix}{suffix} {statement_text}"


def _row_start_time(row: dict) -> datetime | None:
    start_time = row.get("start_time")
    if isinstance(start_time, str):
        return _parse_timestamp(start_time)
    if isinstance(start_time, datetime):
        return start_time
    return None


def _initial_snapshot(rows: list[dict], limit: int, fallback_watermark: datetime) -> tuple[list[dict], datetime]:
    aware_min = datetime.min.replace(tzinfo=timezone.utc)
    ordered = sorted(rows, key=lambda row: _row_start_time(row) or aware_min)
    selected = ordered[-limit:] if limit > 0 else ordered
    watermark = fallback_watermark
    for row in selected:
        start_time = _row_start_time(row)
        if isinstance(start_time, datetime) and start_time > watermark:
            watermark = start_time
    return selected, watermark


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _tail_sql(watermark: datetime | None, limit: int, order: str = "ASC") -> str:
    where = ""
    if watermark is not None:
        where = f"WHERE start_time >= TIMESTAMP '{watermark.isoformat()}'\n"
    return "\n".join(
        [
            "SELECT",
            "  account_id,",
            "  workspace_id,",
            "  statement_id,",
            "  executed_by,",
            "  executed_by_user_id,",
            "  statement_type,",
            "  execution_status,",
            "  client_application,",
            "  client_driver,",
            "  statement_text,",
            "  start_time,",
            "  update_time",
            "FROM system.query.history",
            where.rstrip(),
            f"ORDER BY start_time {order}",
            f"LIMIT {int(limit)}",
        ]
    ).strip()


def tail_query_history(
    host: str,
    token: str,
    warehouse_id: str,
    limit: int = 20,
    poll_secs: float = 10.0,
    max_rows_per_poll: int = 100,
    stream = print,
    sleeper = time.sleep,
    max_cycles: int | None = None,
) -> None:
    seen_ids: set[str] = set()
    started_at = datetime.now(timezone.utc)

    bootstrap_sql = _tail_sql(None, max_rows_per_poll, order="DESC")
    initial_rows = query_rows(host, token, warehouse_id, bootstrap_sql)
    current_rows, watermark = _initial_snapshot(initial_rows, limit, started_at)

    for row in current_rows:
        statement_id = row.get("statement_id")
        if statement_id and statement_id in seen_ids:
            continue
        if statement_id:
            seen_ids.add(statement_id)
        stream(_format_row(row))

    cycles = 0
    while True:
        if max_cycles is not None and cycles >= max_cycles:
            return
        cycles += 1
        sleeper(poll_secs)

        sql = _tail_sql(watermark, max_rows_per_poll)
        rows = query_rows(host, token, warehouse_id, sql)
        if not rows:
            continue

        newest = watermark
        for row in rows:
            statement_id = row.get("statement_id")
            if statement_id and statement_id in seen_ids:
                continue
            if statement_id:
                seen_ids.add(statement_id)
            stream(_format_row(row))

            start_time = _row_start_time(row)
            if isinstance(start_time, datetime) and start_time > newest:
                newest = start_time

        watermark = newest


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Databricks client utilities.")
    subparsers = parser.add_subparsers(dest="verb")

    tail_parser = subparsers.add_parser("tail", help="Poll query history and print new rows.")
    tail_parser.add_argument("--limit", type=int, default=20, help="How many recent rows to print before following (default: %(default)s)")
    tail_parser.add_argument("--poll-secs", type=float, default=10.0, help="Seconds to sleep between polls (default: %(default)s)")
    tail_parser.add_argument("--max-rows-per-poll", type=int, default=100, help="Max rows fetched each poll (default: %(default)s)")
    tail_parser.add_argument("--warehouse-id", default=os.getenv("DATABRICKS_WAREHOUSE_ID") or os.getenv("WAREHOUSE_ID"), help="SQL warehouse id (defaults to DATABRICKS_WAREHOUSE_ID or WAREHOUSE_ID)")
    tail_parser.add_argument("--host", default=os.getenv("DATABRICKS_HOST"), help="Databricks host URL (defaults to DATABRICKS_HOST)")
    tail_parser.add_argument("--token", default=os.getenv("DATABRICKS_TOKEN"), help="Databricks token (defaults to DATABRICKS_TOKEN)")

    jobs_parser = subparsers.add_parser("jobs", help="List Databricks jobs in a TUI.")
    jobs_parser.add_argument("name_filter", nargs="?", default=None, help="Optional case-insensitive filter on job names.")
    jobs_parser.add_argument("--host", default=os.getenv("DATABRICKS_HOST"), help="Databricks host URL (defaults to DATABRICKS_HOST)")
    jobs_parser.add_argument("--token", default=os.getenv("DATABRICKS_TOKEN"), help="Databricks token (defaults to DATABRICKS_TOKEN)")

    pipelines_parser = subparsers.add_parser("pipelines", help="List Databricks pipelines in a TUI.")
    pipelines_parser.add_argument("name_filter", nargs="?", default=None, help="Optional case-insensitive filter on pipeline names.")
    pipelines_parser.add_argument("--host", default=os.getenv("DATABRICKS_HOST"), help="Databricks host URL (defaults to DATABRICKS_HOST)")
    pipelines_parser.add_argument("--token", default=os.getenv("DATABRICKS_TOKEN"), help="Databricks token (defaults to DATABRICKS_TOKEN)")

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.verb != "tail":
        if args.verb in {"jobs", "pipelines"}:
            host = args.host.rstrip("/") if args.host else env("DATABRICKS_HOST")
            token = args.token or env("DATABRICKS_TOKEN")
            return run_resource_browser(
                kind=args.verb,
                host=host,
                token=token,
                name_filter=args.name_filter,
                watch_interval=5.0,
            )
        parser.print_help()
        return

    host = args.host.rstrip("/") if args.host else env("DATABRICKS_HOST")
    token = args.token or env("DATABRICKS_TOKEN")
    warehouse_id = args.warehouse_id or env("WAREHOUSE_ID")

    try:
        tail_query_history(
            host=host,
            token=token,
            warehouse_id=warehouse_id,
            limit=args.limit,
            poll_secs=args.poll_secs,
            max_rows_per_poll=args.max_rows_per_poll,
        )
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    raise SystemExit(main())
