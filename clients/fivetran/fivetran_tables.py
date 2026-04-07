#!/usr/bin/env python3

import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple


FIVETRAN_BASE_URL = "https://api.fivetran.com"
ACCEPT_HEADER = "application/json;version=2"


def basic_auth_header(api_key: str, api_secret: str) -> str:
    token = f"{api_key}:{api_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(token).decode("ascii")


def http_get_json(url: str, headers: Dict[str, str], timeout: int = 30) -> Dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset))


def build_url(path: str, params: Dict[str, Any]) -> str:
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return f"{FIVETRAN_BASE_URL}{path}" + (f"?{qs}" if qs else "")


def list_all_connections(headers: Dict[str, str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    cursor: Optional[str] = None

    while True:
        url = build_url("/v1/connections", {"cursor": cursor, "limit": 1000})
        payload = http_get_json(url, headers)
        data = payload.get("data", {})

        results.extend(data.get("items", []))
        cursor = data.get("next_cursor")
        if not cursor:
            break

    return results


def get_enabled_tables(
    connection_id: str, headers: Dict[str, str]
) -> List[Tuple[str, str]]:
    """
    Returns a list of (destination_schema, destination_table)
    for enabled schemas + enabled tables.
    """
    url = build_url(f"/v1/connections/{urllib.parse.quote(connection_id)}/schemas", {})
    payload = http_get_json(url, headers)
    schemas = payload.get("data", {}).get("schemas", {})

    rows: List[Tuple[str, str]] = []

    if not isinstance(schemas, dict):
        return rows

    for schema_key, schema in schemas.items():
        if not isinstance(schema, dict) or not schema.get("enabled"):
            continue

        schema_name = schema.get("name_in_destination", schema_key)
        tables = schema.get("tables", {})

        if not isinstance(tables, dict):
            continue

        for table_key, table in tables.items():
            if not isinstance(table, dict) or not table.get("enabled"):
                continue

            table_name = table.get("name_in_destination", table_key)
            rows.append((schema_name, table_name))

    return rows


def tsv_escape(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\n", " ").replace("\r", " ")


def main() -> int:
    api_key = os.environ.get("FIVETRAN_API_KEY")
    api_secret = os.environ.get("FIVETRAN_API_SECRET")

    if not api_key or not api_secret:
        print("Missing FIVETRAN_API_KEY or FIVETRAN_API_SECRET", file=sys.stderr)
        return 1

    headers = {
        "Authorization": basic_auth_header(api_key, api_secret),
        "Accept": ACCEPT_HEADER,
        "User-Agent": "fivetran-connections-tables-tsv",
    }

    connections = list_all_connections(headers)

    tables_by_connection: Dict[str, List[Tuple[str, str]]] = {}

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(get_enabled_tables, c["id"], headers): c["id"]
            for c in connections
            if "id" in c
        }

        for future in as_completed(futures):
            cid = futures[future]
            try:
                tables_by_connection[cid] = future.result()
            except Exception:
                tables_by_connection[cid] = []

    columns = [
        "connection_id",
        "service",
        "destination_schema",
        "destination_table",
        "group_id",
        "paused",
        "sync_state",
        "setup_state",
        "update_state",
    ]

    # Header
    print("\t".join(columns))

    for c in connections:
        status = c.get("status", {})
        cid = c.get("id", "")
        tables = tables_by_connection.get(cid, [])

        for schema_name, table_name in tables:
            row = [
                cid,
                c.get("service", ""),
                schema_name,
                table_name,
                c.get("group_id", ""),
                c.get("paused", ""),
                status.get("sync_state", ""),
                status.get("setup_state", ""),
                status.get("update_state", ""),
            ]
            print("\t".join(tsv_escape(v) for v in row))

    return 0


if __name__ == "__main__":
    sys.exit(main())

