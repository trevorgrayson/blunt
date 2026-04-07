#!/usr/bin/env python3
"""
List all Fivetran "connectors" (Connections) and return their full data, including active/paused status.

Auth:
  - Create a Fivetran System Key, then set:
      FIVETRAN_API_KEY=...
      FIVETRAN_API_SECRET=...

Docs:
  - GET https://api.fivetran.com/v1/connections (supports cursor pagination; includes `paused` + `status`)
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


FIVETRAN_BASE_URL = "https://api.fivetran.com"
DEFAULT_ACCEPT_HEADER = "application/json;version=2"


class FivetranError(RuntimeError):
    pass


def _basic_auth_header(api_key: str, api_secret: str) -> str:
    token = f"{api_key}:{api_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(token).decode("ascii")


def _http_get_json(url: str, headers: Dict[str, str], timeout_s: int = 30) -> Dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            body = resp.read().decode(charset, errors="replace")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise FivetranError(f"HTTP {e.code} calling {url}: {raw}") from e
    except urllib.error.URLError as e:
        raise FivetranError(f"Network error calling {url}: {e}") from e
    except json.JSONDecodeError as e:
        raise FivetranError(f"Failed to parse JSON from {url}: {e}") from e


def _build_url(path: str, params: Dict[str, Any]) -> str:
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return f"{FIVETRAN_BASE_URL}{path}" + (f"?{qs}" if qs else "")


def list_all_connections(
    api_key: str,
    api_secret: str,
    *,
    group_id: Optional[str] = None,
    schema: Optional[str] = None,
    page_limit: int = 1000,
    timeout_s: int = 30,
) -> List[Dict[str, Any]]:
    """
    Returns the concatenated `data.items` across all pages from:
      GET /v1/connections?group_id=...&schema=...&cursor=...&limit=...
    """
    headers = {
        "Authorization": _basic_auth_header(api_key, api_secret),
        "Accept": DEFAULT_ACCEPT_HEADER,
        "User-Agent": "fivetran-list-connections-python-urllib/1.0",
    }

    all_items: List[Dict[str, Any]] = []
    cursor: Optional[str] = None

    while True:
        url = _build_url(
            "/v1/connections",
            {
                "group_id": group_id,
                "schema": schema,
                "cursor": cursor,
                "limit": page_limit,
            },
        )
        payload = _http_get_json(url, headers=headers, timeout_s=timeout_s)

        # Typical successful shape: { "code": "Success", "message": "...", "data": { "items": [...], "next_cursor": "..." } }
        data = payload.get("data") or {}
        items = data.get("items") or []
        if not isinstance(items, list):
            raise FivetranError(f"Unexpected response shape (data.items not a list). Full payload: {payload}")

        all_items.extend(items)

        next_cursor = data.get("next_cursor")
        if not next_cursor:
            break
        cursor = next_cursor

    return all_items


def main() -> int:
    p = argparse.ArgumentParser(description="List all Fivetran connections (connectors) with full returned data.")
    p.add_argument("--group-id", default=None, help="Optional: filter by Fivetran group_id")
    p.add_argument("--schema", default=None, help="Optional: filter by schema name")
    p.add_argument("--limit", type=int, default=1000, help="Page size (1..1000). Default: 1000")
    p.add_argument("--timeout", type=int, default=30, help="HTTP timeout (seconds). Default: 30")
    p.add_argument("--out", default=None, help="Write output JSON to a file instead of stdout")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = p.parse_args()

    api_key = os.environ.get("FIVETRAN_API_KEY", "").strip()
    api_secret = os.environ.get("FIVETRAN_API_SECRET", "").strip()
    if not api_key or not api_secret:
        print("Missing env vars: FIVETRAN_API_KEY and/or FIVETRAN_API_SECRET", file=sys.stderr)
        return 2

    connections = list_all_connections(
        api_key,
        api_secret,
        group_id=args.group_id,
        schema=args.schema,
        page_limit=args.limit,
        timeout_s=args.timeout,
    )

    # NOTE: Each item includes fields like `paused` and `status` (setup_state/sync_state/update_state, etc).
    out_obj = {
        "count": len(connections),
        "connections": connections,
    }

    indent = 2 if args.pretty else None
    text = json.dumps(out_obj, indent=indent, sort_keys=False)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + ("\n" if not text.endswith("\n") else ""))
    else:
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

