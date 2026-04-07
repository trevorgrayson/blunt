from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

from tkts.mcp_server import _build_server, _ticket_to_dict
from tkts.storage import TicketStore


class _FakeServer:
    def __init__(self, name: str) -> None:
        self.name = name
        self._list_tools_handler: Callable[[], Any] | None = None
        self._list_resources_handler: Callable[[], Any] | None = None
        self._read_resource_handler: Callable[[Any], Any] | None = None
        self._call_tool_handler: Callable[[str, dict[str, Any] | None], Any] | None = None

    def list_tools(self) -> Callable[[Callable[[], Any]], Callable[[], Any]]:
        def decorator(fn: Callable[[], Any]) -> Callable[[], Any]:
            self._list_tools_handler = fn
            return fn

        return decorator

    def list_resources(self) -> Callable[[Callable[[], Any]], Callable[[], Any]]:
        def decorator(fn: Callable[[], Any]) -> Callable[[], Any]:
            self._list_resources_handler = fn
            return fn

        return decorator

    def read_resource(self) -> Callable[[Callable[[Any], Any]], Callable[[Any], Any]]:
        def decorator(fn: Callable[[Any], Any]) -> Callable[[Any], Any]:
            self._read_resource_handler = fn
            return fn

        return decorator

    def call_tool(self) -> Callable[[Callable[[str, dict[str, Any] | None], Any]], Callable[[str, dict[str, Any] | None], Any]]:
        def decorator(fn: Callable[[str, dict[str, Any] | None], Any]) -> Callable[[str, dict[str, Any] | None], Any]:
            self._call_tool_handler = fn
            return fn

        return decorator


class _StubResource:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class _StubTool:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class _StubReadResourceContents:
    def __init__(self, content: str, mime_type: str) -> None:
        self.content = content
        self.mime_type = mime_type


class _StubTextContent:
    def __init__(self, type: str, text: str) -> None:
        self.type = type
        self.text = text


def _build_test_server(store: TicketStore, read_only: bool = False) -> _FakeServer:
    return _build_server(
        backend=store,
        read_only=read_only,
        Server=_FakeServer,
        TextContent=_StubTextContent,
        Tool=_StubTool,
        Resource=_StubResource,
        ReadResourceContents=_StubReadResourceContents,
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_list_resources_includes_ticket_and_collection(tmp_path: Any) -> None:
    store = TicketStore(root=tmp_path)
    ticket = store.create_ticket(subject="Test", body="Body")

    server = _build_test_server(store)
    resources = _run(server._list_resources_handler())

    assert resources
    assert any(resource.uri == "tkts://tickets" for resource in resources)
    assert any(resource.uri == f"tkts://tickets/{ticket.ticket_id}" for resource in resources)


def test_read_resource_list_returns_ticket_payloads(tmp_path: Any) -> None:
    store = TicketStore(root=tmp_path)
    ticket = store.create_ticket(subject="Test", body="Body")

    server = _build_test_server(store)
    contents = _run(server._read_resource_handler("tkts://tickets"))

    assert len(contents) == 1
    payload = json.loads(contents[0].content)
    expected_ticket = store.get_ticket(ticket.ticket_id)
    assert expected_ticket is not None
    assert payload == [_ticket_to_dict(expected_ticket)]


def test_read_resource_ticket_returns_single_ticket(tmp_path: Any) -> None:
    store = TicketStore(root=tmp_path)
    ticket = store.create_ticket(subject="Test", body="Body")

    server = _build_test_server(store)
    contents = _run(server._read_resource_handler(f"tkts://tickets/{ticket.ticket_id}"))

    assert len(contents) == 1
    payload = json.loads(contents[0].content)
    expected_ticket = store.get_ticket(ticket.ticket_id)
    assert expected_ticket is not None
    assert payload == _ticket_to_dict(expected_ticket)


def test_list_tools_respects_read_only(tmp_path: Any) -> None:
    store = TicketStore(root=tmp_path)
    server = _build_test_server(store, read_only=True)

    tools = _run(server._list_tools_handler())
    names = {tool.name for tool in tools}

    assert "create_ticket" not in names
    assert "update_ticket" not in names
