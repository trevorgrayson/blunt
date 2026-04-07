from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from tkts.backends import Backend, get_backend_from_env


def _require_mcp() -> Any:
    try:
        import mcp  # type: ignore
        from mcp.server import Server  # type: ignore
        from mcp.server.lowlevel.helper_types import (  # type: ignore
            ReadResourceContents,
        )
        from mcp.server.stdio import stdio_server  # type: ignore
        from mcp.types import Resource, TextContent, Tool  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise SystemExit(
            "The mcp Python SDK is required. Install `mcp` to use `tkts mcp`."
        ) from exc

    return mcp, Server, stdio_server, TextContent, Tool, Resource, ReadResourceContents


def _ticket_to_dict(ticket: Any) -> Dict[str, Any]:
    return {
        "id": ticket.ticket_id,
        "subject": ticket.subject,
        "body": ticket.body,
        "assignee": ticket.assignee,
        "tags": ticket.tags,
        "status": getattr(ticket, "status", None),
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
    }


def _build_server(
    *,
    backend: Backend,
    read_only: bool,
    Server: Any,
    TextContent: Any,
    Tool: Any,
    Resource: Any,
    ReadResourceContents: Any,
) -> Any:
    server = Server("tkts")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        tools = [
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
                name="tail_ticket_changelog",
                description="Tail a ticket change log.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticket_id": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                    "required": ["ticket_id"],
                },
            ),
        ]
        if not read_only:
            tools.append(
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
                            "status": {
                                "type": "string",
                                "enum": ["todo", "in-progress", "in-review", "blocked", "done"],
                            },
                        },
                        "required": ["subject"],
                    },
                )
            )
            tools.append(
                Tool(
                    name="update_ticket",
                    description="Update ticket fields, status, or append comments.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string"},
                            "subject": {"type": "string"},
                            "body": {"type": "string"},
                            "assignee": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "status": {
                                "type": "string",
                                "enum": ["todo", "in-progress", "in-review", "blocked", "done"],
                            },
                            "append_body": {"type": "string"},
                            "comment": {"type": "string"},
                            "log_message": {"type": "string"},
                        },
                        "required": ["ticket_id"],
                    },
                )
            )
        return tools

    @server.list_resources()
    async def list_resources() -> List[Resource]:
        tickets = backend.list_tickets()
        resources: List[Resource] = [
            Resource(
                name="tickets",
                title="Tickets",
                uri="tkts://tickets",
                description="List all tickets.",
                mimeType="application/json",
            )
        ]
        for ticket in tickets:
            resources.append(
                Resource(
                    name=f"ticket-{ticket.ticket_id}",
                    title=ticket.subject or f"Ticket {ticket.ticket_id}",
                    uri=f"tkts://tickets/{ticket.ticket_id}",
                    description="Single ticket.",
                    mimeType="application/json",
                )
            )
        return resources

    @server.read_resource()
    async def read_resource(uri: Any) -> List[ReadResourceContents]:
        uri_str = str(uri)
        if uri_str == "tkts://tickets":
            tickets = [_ticket_to_dict(ticket) for ticket in backend.list_tickets()]
            return [
                ReadResourceContents(
                    content=json.dumps(tickets, ensure_ascii=True),
                    mime_type="application/json",
                )
            ]
        prefix = "tkts://tickets/"
        if uri_str.startswith(prefix):
            ticket_id = uri_str[len(prefix) :]
            if not ticket_id:
                raise ValueError("ticket_id is required")
            ticket = backend.get_ticket(str(ticket_id))
            if not ticket:
                raise ValueError(f"Ticket {ticket_id} not found")
            return [
                ReadResourceContents(
                    content=json.dumps(_ticket_to_dict(ticket), ensure_ascii=True),
                    mime_type="application/json",
                )
            ]
        raise ValueError(f"Unknown resource: {uri_str}")

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
            if read_only:
                raise ValueError("create_ticket is disabled in read-only mode")
            subject = arguments.get("subject")
            if not subject:
                raise ValueError("subject is required")
            body = str(arguments.get("body") or "")
            assignee = arguments.get("assignee")
            tags = arguments.get("tags")
            status = arguments.get("status")
            ticket = backend.create_ticket(
                subject=str(subject),
                body=body,
                assignee=str(assignee) if assignee else None,
                tags=tags if isinstance(tags, list) else None,
                status=str(status) if status else None,
            )
            return [TextContent(type="text", text=json.dumps(_ticket_to_dict(ticket), ensure_ascii=True))]
        if name == "update_ticket":
            if read_only:
                raise ValueError("update_ticket is disabled in read-only mode")
            ticket_id = arguments.get("ticket_id")
            if not ticket_id:
                raise ValueError("ticket_id is required")
            ticket = backend.update_ticket(
                str(ticket_id),
                subject=arguments.get("subject"),
                body=arguments.get("body"),
                assignee=arguments.get("assignee"),
                tags=arguments.get("tags") if isinstance(arguments.get("tags"), list) else None,
                status=arguments.get("status"),
                append_body=arguments.get("append_body"),
                comment=arguments.get("comment"),
                log_message=arguments.get("log_message"),
            )
            return [TextContent(type="text", text=json.dumps(_ticket_to_dict(ticket), ensure_ascii=True))]
        if name == "tail_ticket_changelog":
            ticket_id = arguments.get("ticket_id")
            if not ticket_id:
                raise ValueError("ticket_id is required")
            limit = arguments.get("limit")
            limit_value = int(limit) if limit is not None else 10
            entries = backend.tail_ticket_changelog(str(ticket_id), limit=limit_value)
            return [TextContent(type="text", text=json.dumps(entries, ensure_ascii=True))]

        raise ValueError(f"Unknown tool: {name}")

    return server


def run_mcp_server(read_only: bool = False) -> int:
    _, Server, stdio_server, TextContent, Tool, Resource, ReadResourceContents = _require_mcp()

    backend: Backend = get_backend_from_env()
    server = _build_server(
        backend=backend,
        read_only=read_only,
        Server=Server,
        TextContent=TextContent,
        Tool=Tool,
        Resource=Resource,
        ReadResourceContents=ReadResourceContents,
    )

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    import asyncio

    asyncio.run(_run())
    return 0
