#!/usr/bin/env python3
"""
tickets_cli.py — Minimal CLI for listing and showing tickets.

Features
--------
- `list`  : Prints tickets assigned to you in a clean, fixed-width table.
- `show`  : Prints a single ticket as Markdown.

Backends
--------
1) Jira (Cloud/Server)
   Env vars (required):
     - JIRA_BASE_URL      e.g. "https://yourcompany.atlassian.net"
     - JIRA_EMAIL         e.g. "alice@example.com"
     - JIRA_API_TOKEN     e.g. "xxx" (Jira Cloud API token or server password)
   Notes:
     - `list` uses JQL `assignee = currentUser()` and excludes resolved items by default.
     - Fields fetched: summary, status, assignee, priority, issuetype, labels, created, updated, description.

2) Mock (local JSON file for testing / demos)
   Env vars:
     - TICKETS_JSON       path to a JSON file with structure:
         {
           "tickets": [
             {
               "id": "DEMO-1",
               "title": "Example issue",
               "status": "Open",
               "assignee": "you@example.com",
               "priority": "Medium",
               "type": "Task",
               "labels": ["demo"],
               "url": "https://example.local/DEMO-1",
               "created": "2025-10-01T10:00:00Z",
               "updated": "2025-10-02T15:30:00Z",
               "description": "Plain text or basic **markdown**"
             }
           ]
         }

Usage
-----
$ python tickets_cli.py list [--backend jira|mock] [--include-done]
$ python tickets_cli.py show <TICKET_ID> [--backend jira|mock]

Design goals
------------
- Core libraries only (no 'requests').
- Clean, dependency-free table rendering.
- Conservative, readable code; robust error handling.

License
-------
MIT
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import sys
import textwrap
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib import request, parse, error


# ---------- Utilities ----------

ISO_INPUT_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
)

def parse_iso8601(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    for fmt in ISO_INPUT_FORMATS:
        try:
            if fmt.endswith("Z"):
                # Zulu => set tzinfo=UTC
                if s.endswith("Z"):
                    return dt.datetime.strptime(s, fmt).replace(tzinfo=dt.timezone.utc)
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None

def fmt_dt(s: Optional[str]) -> str:
    d = parse_iso8601(s)
    if not d:
        return ""
    # Render in local time without seconds to keep table tidy
    local = d.astimezone()
    return local.strftime("%Y-%m-%d %H:%M")

def truncate(s: str, width: int) -> str:
    if len(s) <= width:
        return s
    if width <= 1:
        return s[:width]
    return s[: width - 1] + "…"

def safe_get(d: Dict[str, Any], *path, default=None):
    cur = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur

def print_table(rows: List[List[str]], headers: List[str]) -> None:
    # Compute column widths
    cols = len(headers)
    widths = [len(h) for h in headers]
    for r in rows:
        for i in range(cols):
            widths[i] = max(widths[i], len(r[i]))
    # Render
    sep = "  "
    header_line = sep.join(h.ljust(widths[i]) for i, h in enumerate(headers))
    rule_line = sep.join("-" * widths[i] for i in range(cols))
    print(header_line)
    print(rule_line)
    for r in rows:
        print(sep.join(r[i].ljust(widths[i]) for i in range(cols)))


# ---------- Backend interface ----------

class Ticket:
    def __init__(
        self,
        id: str,
        title: str,
        status: str = "",
        assignee: str = "",
        priority: str = "",
        type_: str = "",
        labels: Optional[List[str]] = None,
        url: str = "",
        created: Optional[str] = None,
        updated: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.id = id
        self.title = title
        self.status = status
        self.assignee = assignee
        self.priority = priority
        self.type = type_
        self.labels = labels or []
        self.url = url
        self.created = created
        self.updated = updated
        self.description = description or ""

    # Markdown view
    def to_markdown(self) -> str:
        lines = [
            f"# {self.id} — {self.title}",
            "",
            f"- **Status:** {self.status}" if self.status else "- **Status:**",
            f"- **Assignee:** {self.assignee}" if self.assignee else "- **Assignee:**",
            f"- **Priority:** {self.priority}" if self.priority else "- **Priority:**",
            f"- **Type:** {self.type}" if self.type else "- **Type:**",
            f"- **Labels:** {', '.join(self.labels) if self.labels else ''}",
            f"- **URL:** {self.url}" if self.url else "- **URL:**",
            f"- **Created:** {fmt_dt(self.created)}" if self.created else "- **Created:**",
            f"- **Updated:** {fmt_dt(self.updated)}" if self.updated else "- **Updated:**",
            "",
            "## Description",
            "",
            self.description.strip() if self.description else "_(no description)_",
            "",
        ]
        return "\n".join(lines)


class TicketsBackend:
    def list_assigned_to_me(self, include_done: bool = False) -> List[Ticket]:
        raise NotImplementedError

    def get_ticket(self, ticket_id: str) -> Ticket:
        raise NotImplementedError


# ---------- Jira backend ----------

class JiraBackend(TicketsBackend):
    def __init__(self):
        self.base = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
        email = os.environ.get("JIRA_EMAIL", "")
        token = os.environ.get("JIRA_API_TOKEN", "")
        if not self.base or not email or not token:
            missing = [k for k, v in [
                ("JIRA_BASE_URL", self.base),
                ("JIRA_EMAIL", email),
                ("JIRA_API_TOKEN", token),
            ] if not v]
            raise RuntimeError(
                "Missing Jira configuration: " + ", ".join(missing) +
                "\nSet required environment variables."
            )
        creds = f"{email}:{token}".encode("utf-8")
        self.auth_header = "Basic " + base64.b64encode(creds).decode("ascii")

    def _search_jql(self, jql: str, fields: List[str], max_per_page: int = 200) -> List[Dict[str, Any]]:
        """
        Calls GET /rest/api/3/search/jql with pagination until isLast == True.
        Returns a list of 'issues' dicts.
        """
        all_issues: List[Dict[str, Any]] = []
        next_token: Optional[str] = None
        while True:
            params = {
                "jql": jql,
                "maxResults": str(max_per_page),
                "fields": ",".join(fields),
            }
            if next_token:
                params["nextPageToken"] = next_token

            data = self._req("GET", "/rest/api/3/search/jql", params=params)
            issues = data.get("issues", []) or []
            all_issues.extend(issues)
            if data.get("isLast", True):
                break
            next_token = data.get("nextPageToken")
            if not next_token:  # safety: if server forgets to send it, bail to avoid loop
                break
        return all_issues

    def _req(self, method: str, path: str, params: Optional[Dict[str, str]] = None, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        url = self.base + path
        if params:
            url += "?" + parse.urlencode(params)
        body_bytes = None
        req_headers = {"Authorization": self.auth_header, "Accept": "application/json"}
        if headers:
            req_headers.update(headers)
        if data is not None:
            body_bytes = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        req = request.Request(url, data=body_bytes, headers=req_headers, method=method)
        try:
            with request.urlopen(req) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                text = resp.read().decode(charset)
                return json.loads(text)
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Jira HTTP {e.code}: {e.reason}\n{detail}") from None
        except error.URLError as e:
            raise RuntimeError(f"Jira connection error: {e.reason}") from None

    def list_assigned_to_me(self, include_done: bool = False) -> List[Ticket]:
        jql = "assignee = currentUser()"
        if not include_done:
            jql += " AND resolution = EMPTY"
        fields = ["summary", "status", "assignee", "priority", "issuetype", "labels", "created", "updated"]

        issues = self._search_jql(jql, fields)
        out: List[Ticket] = []
        for it in issues:
            key = it.get("key", "")
            f = it.get("fields", {}) or {}
            out.append(
                Ticket(
                    id=key,
                    title=str(safe_get(f, "summary", default="")).strip(),
                    status=str(safe_get(f, "status", "name", default="")).strip(),
                    assignee=str(safe_get(f, "assignee", "displayName", default="")).strip(),
                    priority=str(safe_get(f, "priority", "name", default="")).strip(),
                    type_=str(safe_get(f, "issuetype", "name", default="")).strip(),
                    labels=[str(x) for x in (f.get("labels") or [])],
                    url=f"{self.base}/browse/{key}" if key else "",
                    created=f.get("created"),
                    updated=f.get("updated"),
                )
            )
        return out

    def get_ticket(self, ticket_id: str) -> Ticket:
        params = {
            "fields": "summary,status,assignee,priority,issuetype,labels,created,updated,description",
        }
        it = self._req("GET", f"/rest/api/3/issue/{parse.quote(ticket_id)}", params=params)
        f = it.get("fields", {}) or {}
        key = it.get("key", ticket_id)

        # Description can be plain string or Atlassian Document Format (ADF)
        desc = f.get("description")
        desc_md = self._adf_to_markdown(desc)

        return Ticket(
            id=key,
            title=str(f.get("summary", "")).strip(),
            status=str(safe_get(f, "status", "name", default="")).strip(),
            assignee=str(safe_get(f, "assignee", "displayName", default="")).strip(),
            priority=str(safe_get(f, "priority", "name", default="")).strip(),
            type_=str(safe_get(f, "issuetype", "name", default="")).strip(),
            labels=[str(x) for x in (f.get("labels") or [])],
            url=f"{self.base}/browse/{key}" if key else "",
            created=f.get("created"),
            updated=f.get("updated"),
            description=desc_md,
        )

    # --- very small ADF → Markdown converter (best-effort) ---
    def _adf_to_markdown(self, adf: Any) -> str:
        if adf is None:
            return ""
        if isinstance(adf, str):
            return adf
        # ADF is usually a dict {"type":"doc","content":[...]}
        def walk(node: Any) -> str:
            if not isinstance(node, dict):
                return ""
            t = node.get("type")
            if t == "text":
                text = node.get("text", "") or ""
                marks = node.get("marks") or []
                for m in marks:
                    mtype = m.get("type")
                    if mtype == "strong":
                        text = f"**{text}**"
                    elif mtype == "em":
                        text = f"*{text}*"
                    elif mtype == "code":
                        text = f"`{text}`"
                    elif mtype == "link":
                        href = safe_get(m, "attrs", "href", default="")
                        if href:
                            text = f"[{text}]({href})"
                return text
            if t in ("paragraph", "heading", "bulletList", "orderedList", "listItem", "blockquote", "codeBlock"):
                return self._block_to_md(node)
            # Fallback: concat children
            return "".join(walk(c) for c in (node.get("content") or []))

        return "".join(walk(c) for c in (adf.get("content") or []))

    def _block_to_md(self, node: Dict[str, Any]) -> str:
        t = node.get("type")
        content = node.get("content") or []
        if t == "paragraph":
            text = "".join(self._inline_text(c) for c in content)
            return text + "\n\n" if text.strip() else "\n"
        if t == "heading":
            level = int(safe_get(node, "attrs", "level", default=1) or 1)
            prefix = "#" * max(1, min(level, 6))
            text = "".join(self._inline_text(c) for c in content)
            return f"{prefix} {text}\n\n"
        if t == "bulletList":
            return "".join(self._list_item(c, bullet=True) for c in content) + "\n"
        if t == "orderedList":
            start = int(safe_get(node, "attrs", "order", default=1) or 1)
            return "".join(self._list_item(c, bullet=False, start_idx=i)
                           for i, c in enumerate(content, start)) + "\n"
        if t == "blockquote":
            inner = "".join(self._inline_text(c) if c.get("type") == "paragraph"
                            else self._block_to_md(c) for c in content)
            quoted = "\n".join("> " + line if line.strip() else ">" for line in inner.rstrip("\n").splitlines())
            return quoted + "\n\n"
        if t == "codeBlock":
            lang = safe_get(node, "attrs", "language", default="") or ""
            code = "".join(self._text_from_subtree(c) for c in content)
            return f"```{lang}\n{code.strip()}\n```\n\n"
        if t == "listItem":
            # List items are handled by parent
            return "".join(self._inline_text(c) for c in content) + "\n"
        # Fallback
        return "".join(self._text_from_subtree(c) for c in content)

    def _inline_text(self, node: Dict[str, Any]) -> str:
        if node.get("type") == "text":
            return self._adf_text_node_to_md(node)
        return self._text_from_subtree(node)

    def _adf_text_node_to_md(self, node: Dict[str, Any]) -> str:
        text = node.get("text", "") or ""
        for m in node.get("marks") or []:
            mtype = m.get("type")
            if mtype == "strong":
                text = f"**{text}**"
            elif mtype == "em":
                text = f"*{text}*"
            elif mtype == "code":
                text = f"`{text}`"
            elif mtype == "link":
                href = safe_get(m, "attrs", "href", default="")
                if href:
                    text = f"[{text}]({href})"
        return text

    def _text_from_subtree(self, node: Dict[str, Any]) -> str:
        if node.get("type") == "text":
            return node.get("text", "") or ""
        return "".join(self._text_from_subtree(c) for c in (node.get("content") or []))


# ---------- Mock backend ----------

class MockBackend(TicketsBackend):
    def __init__(self):
        path = os.environ.get("TICKETS_JSON", "")
        if not path:
            raise RuntimeError("Mock backend requires TICKETS_JSON env var pointing to a JSON file.")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise RuntimeError(f"Mock file not found: {path}") from None
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse mock JSON: {e}") from None
        self._tickets = data.get("tickets", [])

    def list_assigned_to_me(self, include_done: bool = False) -> List[Ticket]:
        mine = [t for t in self._tickets if t.get("assignee")]
        if not include_done:
            mine = [t for t in mine if str(t.get("status", "")).lower() not in ("done", "resolved", "closed")]
        return [self._to_ticket(t) for t in mine]

    def get_ticket(self, ticket_id: str) -> Ticket:
        for t in self._tickets:
            if t.get("id") == ticket_id:
                return self._to_ticket(t)
        raise RuntimeError(f"Ticket not found: {ticket_id}")

    @staticmethod
    def _to_ticket(t: Dict[str, Any]) -> Ticket:
        return Ticket(
            id=str(t.get("id", "")),
            title=str(t.get("title", "")),
            status=str(t.get("status", "")),
            assignee=str(t.get("assignee", "")),
            priority=str(t.get("priority", "")),
            type_=str(t.get("type", "")),
            labels=[str(x) for x in (t.get("labels") or [])],
            url=str(t.get("url", "")),
            created=str(t.get("created", "")),
            updated=str(t.get("updated", "")),
            description=str(t.get("description", "")),
        )


# ---------- CLI ----------

def choose_backend(name: str) -> TicketsBackend:
    name = (name or "jira").lower()
    if name == "jira":
        return JiraBackend()
    if name == "mock":
        return MockBackend()
    raise RuntimeError(f"Unknown backend: {name}")

def cmd_list(args: argparse.Namespace) -> int:
    try:
        backend = choose_backend(args.backend)
        tickets = backend.list_assigned_to_me(include_done=args.include_done)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    headers = ["ID", "Title", "Status", "Priority", "Type", "Updated"]
    rows: List[List[str]] = []
    for t in tickets:
        rows.append([
            t.id,
            truncate(t.title, 50),
            t.status,
            t.priority,
            t.type,
            fmt_dt(t.updated),
        ])

    if not rows:
        print("(no tickets found)")
        return 0

    print_table(rows, headers)
    return 0

def cmd_show(args: argparse.Namespace) -> int:
    try:
        backend = choose_backend(args.backend)
        t = backend.get_ticket(args.ticket_id)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    print(t.to_markdown())
    return 0

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tickets",
        description="List your tickets or show a ticket as Markdown."
    )
    p.add_argument("--backend", choices=["jira", "mock"], default="jira",
                   help="Which backend to use (default: jira)")

    sub = p.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List tickets assigned to you (table).")
    p_list.add_argument("--include-done", action="store_true",
                        help="Include resolved/closed issues.")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Show a single ticket as Markdown.")
    p_show.add_argument("ticket_id", help="Ticket ID/Key (e.g., ABC-123)")
    p_show.set_defaults(func=cmd_show)

    return p

def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
