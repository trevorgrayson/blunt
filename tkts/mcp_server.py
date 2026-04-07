from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from tkts.backends import Backend, get_backend_from_env


def _require_mcp() -> Any:
    try:
        import mcp  # type: ignore
        from mcp.server import Server  # type: ignore
        from mcp.server.stdio import stdio_server  # type: ignore
        from mcp.types import TextContent, Tool  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise SystemExit(
            "The mcp Python SDK is required. Install `mcp` to use `tkts mcp`."
        ) from exc

    return mcp, Server, stdio_server, TextContent, Tool


def _ticket_to_dict(ticket: Any) -> Dict[str, Any]:
    return {
        "id": ticket.ticket_id,
        "subject": ticket.subject,
        "body": ticket.body,
        "assignee": ticket.assignee,
        "tags": ticket.tags,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
    }


def run_mcp_server() -> int:
    _, Server, stdio_server, TextContent, Tool = _require_mcp()

    backend: Backend = get_backend_from_env()
    server = Server("tkts")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="list_tickets",
                description="List all tickets.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="get_ticket",
                description="Fetch a single ticket by id.",
                inputSchema={
                    "type": "object",
                    "properties": {"ticket_id": {"type": "string"}},
                    "required": ["ticket_id"],
                },
            ),
            Tool(
                name="create_ticket",
                description="Create a new ticket.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                        "assignee": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["subject"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Optional[Dict[str, Any]]) -> List[TextContent]:
        arguments = arguments or {}
        if name == "list_tickets":
            tickets = [_ticket_to_dict(ticket) for ticket in backend.list_tickets()]
            return [TextContent(type="text", text=json.dumps(tickets, ensure_ascii=True))]
        if name == "get_ticket":
            ticket_id = arguments.get("ticket_id")
            if not ticket_id:
                raise ValueError("ticket_id is required")
            ticket = backend.get_ticket(str(ticket_id))
            if not ticket:
                raise ValueError(f"Ticket {ticket_id} not found")
            return [TextContent(type="text", text=json.dumps(_ticket_to_dict(ticket), ensure_ascii=True))]
        if name == "create_ticket":
            subject = arguments.get("subject")
            if not subject:
                raise ValueError("subject is required")
            body = str(arguments.get("body") or "")
            assignee = arguments.get("assignee")
            tags = arguments.get("tags")
            ticket = backend.create_ticket(
                subject=str(subject),
                body=body,
                assignee=str(assignee) if assignee else None,
                tags=tags if isinstance(tags, list) else None,
            )
            return [TextContent(type="text", text=json.dumps(_ticket_to_dict(ticket), ensure_ascii=True))]

        raise ValueError(f"Unknown tool: {name}")

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream)

    import asyncio

    asyncio.run(_run())
    return 0
