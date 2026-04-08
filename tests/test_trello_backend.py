from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import pytest

from tkts.backends import get_backend_from_env
from tkts.trello_backend import TrelloBackend
from tkts.trello_client import TrelloAmbiguousIdError, TrelloConfigError, TrelloClient


def _set_required_env(monkeypatch) -> None:
    monkeypatch.setenv("TRELLO_API_KEY", "key")
    monkeypatch.setenv("TRELLO_API_TOKEN", "token")
    monkeypatch.setenv("TRELLO_BOARD_ID", "board123")


def _install_fake_request(monkeypatch, responses: Dict[Tuple[str, str], Any], calls: List[Tuple[str, str, dict[str, Any]]]) -> None:
    def fake_request(self: TrelloClient, method: str, path: str, *, params=None, json_body=None) -> Any:
        calls.append((method.upper(), path, dict(params or {})))
        key = (method.upper(), path)
        if key not in responses:
            raise AssertionError(f"Unexpected Trello request: {key}")
        value = responses[key]
        return value(params or {})

    monkeypatch.setattr(TrelloClient, "_request", fake_request, raising=True)


def test_backend_registration_via_env(monkeypatch) -> None:
    _set_required_env(monkeypatch)
    calls: list[tuple[str, str, dict[str, Any]]] = []
    _install_fake_request(
        monkeypatch,
        responses={
            ("GET", "/boards/board123/lists"): lambda _: [{"id": "l1", "name": "todo"}],
            ("GET", "/boards/board123/labels"): lambda _: [],
            ("GET", "/boards/board123/members"): lambda _: [],
            ("GET", "/boards/board123/cards"): lambda _: [],
        },
        calls=calls,
    )

    monkeypatch.setenv("TKTS_BACKEND", "trello")
    backend = get_backend_from_env()
    assert isinstance(backend, TrelloBackend)


def test_list_tickets_excludes_done_by_default(monkeypatch) -> None:
    _set_required_env(monkeypatch)
    calls: list[tuple[str, str, dict[str, Any]]] = []
    _install_fake_request(
        monkeypatch,
        responses={
            ("GET", "/boards/board123/lists"): lambda _: [
                {"id": "l1", "name": "todo"},
                {"id": "l2", "name": "done"},
            ],
            ("GET", "/boards/board123/labels"): lambda _: [{"id": "lab1", "name": "feature:trello", "color": "green"}],
            ("GET", "/boards/board123/members"): lambda _: [{"id": "m1", "username": "alice", "fullName": "Alice"}],
            ("GET", "/boards/board123/cards"): lambda _: [
                {
                    "id": "c1",
                    "shortLink": "abc12345",
                    "name": "Todo card",
                    "idList": "l1",
                    "labels": [{"name": "feature:trello"}],
                    "members": [{"id": "m1", "username": "alice", "fullName": "Alice"}],
                    "dateLastActivity": "2026-04-08T00:00:00.000Z",
                    "url": "https://trello.example/c1",
                },
                {
                    "id": "c2",
                    "shortLink": "def67890",
                    "name": "Done card",
                    "idList": "l2",
                    "labels": [],
                    "members": [],
                    "dateLastActivity": "2026-04-08T00:00:00.000Z",
                    "url": "https://trello.example/c2",
                },
            ],
        },
        calls=calls,
    )

    backend = TrelloBackend()
    tickets = backend.list_tickets()
    assert [ticket.subject for ticket in tickets] == ["Todo card"]


def test_list_tickets_includes_done_when_enabled(monkeypatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("TRELLO_INCLUDE_DONE", "true")
    calls: list[tuple[str, str, dict[str, Any]]] = []
    _install_fake_request(
        monkeypatch,
        responses={
            ("GET", "/boards/board123/lists"): lambda _: [
                {"id": "l1", "name": "todo"},
                {"id": "l2", "name": "done"},
            ],
            ("GET", "/boards/board123/labels"): lambda _: [],
            ("GET", "/boards/board123/members"): lambda _: [],
            ("GET", "/boards/board123/cards"): lambda _: [
                {"id": "c1", "shortLink": "abc12345", "name": "Todo", "idList": "l1", "labels": [], "members": [], "dateLastActivity": None, "url": ""},
                {"id": "c2", "shortLink": "def67890", "name": "Done", "idList": "l2", "labels": [], "members": [], "dateLastActivity": None, "url": ""},
            ],
        },
        calls=calls,
    )

    backend = TrelloBackend()
    tickets = backend.list_tickets()
    assert {ticket.subject for ticket in tickets} == {"Todo", "Done"}


def test_get_ticket_prefix_ambiguity(monkeypatch) -> None:
    _set_required_env(monkeypatch)
    calls: list[tuple[str, str, dict[str, Any]]] = []
    _install_fake_request(
        monkeypatch,
        responses={
            ("GET", "/boards/board123/lists"): lambda _: [{"id": "l1", "name": "todo"}],
            ("GET", "/boards/board123/labels"): lambda _: [],
            ("GET", "/boards/board123/members"): lambda _: [],
            ("GET", "/boards/board123/cards"): lambda _: [
                {"id": "c1", "shortLink": "abc11111", "name": "One", "idList": "l1", "labels": [], "members": [], "dateLastActivity": None, "url": ""},
                {"id": "c2", "shortLink": "abc22222", "name": "Two", "idList": "l1", "labels": [], "members": [], "dateLastActivity": None, "url": ""},
            ],
        },
        calls=calls,
    )

    backend = TrelloBackend()
    with pytest.raises(TrelloAmbiguousIdError):
        backend.get_ticket("abc")


def test_create_ticket_missing_label_fails_by_default(monkeypatch) -> None:
    _set_required_env(monkeypatch)
    calls: list[tuple[str, str, dict[str, Any]]] = []

    _install_fake_request(
        monkeypatch,
        responses={
            ("GET", "/boards/board123/lists"): lambda _: [{"id": "l1", "name": "todo"}],
            ("GET", "/boards/board123/labels"): lambda _: [],
            ("GET", "/boards/board123/members"): lambda _: [],
            ("GET", "/boards/board123/cards"): lambda _: [],
            ("POST", "/cards"): lambda _: {},
            ("POST", "/labels"): lambda _: {"id": "labx", "name": "feature:trello", "color": "green"},
        },
        calls=calls,
    )

    backend = TrelloBackend()
    with pytest.raises(TrelloConfigError):
        backend.create_ticket(subject="Test", body="Body", tags=["feature:trello"])


def test_create_ticket_creates_missing_label_when_enabled(monkeypatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("TRELLO_CREATE_MISSING_LABELS", "true")
    calls: list[tuple[str, str, dict[str, Any]]] = []
    created_payload: dict[str, Any] = {}

    def post_labels(params: dict[str, Any]) -> dict[str, Any]:
        assert params["name"] == "feature:trello"
        return {"id": "labx", "name": "feature:trello", "color": "green"}

    def post_cards(params: dict[str, Any]) -> dict[str, Any]:
        created_payload.update(params)
        return {
            "id": "c1",
            "shortLink": "abc12345",
            "name": params["name"],
            "desc": params.get("desc", ""),
            "idList": params["idList"],
            "labels": [{"name": "feature:trello"}],
            "members": [],
            "dateLastActivity": "2026-04-08T00:00:00.000Z",
            "url": "https://trello.example/c1",
        }

    _install_fake_request(
        monkeypatch,
        responses={
            ("GET", "/boards/board123/lists"): lambda _: [{"id": "l1", "name": "todo"}],
            ("GET", "/boards/board123/labels"): lambda _: [],
            ("GET", "/boards/board123/members"): lambda _: [],
            ("POST", "/labels"): post_labels,
            ("POST", "/cards"): post_cards,
            ("GET", "/boards/board123/cards"): lambda _: [],
        },
        calls=calls,
    )

    backend = TrelloBackend()
    ticket = backend.create_ticket(subject="Hello", body="Body", tags=["feature:trello"])
    assert ticket.ticket_id == "abc12345"
    assert "idLabels" in created_payload


def test_update_ticket_moves_list_and_adds_comments(monkeypatch) -> None:
    _set_required_env(monkeypatch)
    calls: list[tuple[str, str, dict[str, Any]]] = []

    cards_state = [
        {
            "id": "c1",
            "shortLink": "abc12345",
            "name": "Old",
            "desc": "Old body",
            "idList": "l1",
            "labels": [],
            "members": [],
            "dateLastActivity": "2026-04-08T00:00:00.000Z",
            "url": "https://trello.example/c1",
        }
    ]

    def get_cards(_: dict[str, Any]) -> list[dict[str, Any]]:
        return cards_state

    def put_card(params: dict[str, Any]) -> dict[str, Any]:
        assert params["name"] == "New"
        assert params["idList"] == "l2"
        cards_state[0]["name"] = "New"
        cards_state[0]["idList"] = "l2"
        return dict(cards_state[0])

    def post_comment(params: dict[str, Any]) -> dict[str, Any]:
        assert "text" in params
        return {"id": "a1"}

    _install_fake_request(
        monkeypatch,
        responses={
            ("GET", "/boards/board123/lists"): lambda _: [{"id": "l1", "name": "todo"}, {"id": "l2", "name": "in-progress"}],
            ("GET", "/boards/board123/labels"): lambda _: [],
            ("GET", "/boards/board123/members"): lambda _: [],
            ("GET", "/boards/board123/cards"): get_cards,
            ("PUT", "/cards/c1"): put_card,
            ("POST", "/cards/c1/actions/comments"): post_comment,
        },
        calls=calls,
    )

    backend = TrelloBackend()
    updated = backend.update_ticket("abc12", subject="New", status="in-progress", append_body="A", comment="B", log_message="C")
    assert updated.subject == "New"
    assert updated.status == "in-progress"

    comment_calls = [call for call in calls if call[0] == "POST" and call[1].endswith("/actions/comments")]
    assert len(comment_calls) == 3


def test_tail_ticket_changelog_returns_chronological(monkeypatch) -> None:
    _set_required_env(monkeypatch)
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def get_cards(_: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"id": "c1", "shortLink": "abc12345", "name": "X", "idList": "l1", "labels": [], "members": [], "dateLastActivity": None, "url": ""}]

    def get_actions(_: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {"type": "commentCard", "date": "2026-04-08T01:00:00.000Z", "memberCreator": {"fullName": "Alice"}, "data": {"text": "Second"}},
            {"type": "commentCard", "date": "2026-04-08T00:00:00.000Z", "memberCreator": {"fullName": "Bob"}, "data": {"text": "First"}},
        ]

    _install_fake_request(
        monkeypatch,
        responses={
            ("GET", "/boards/board123/lists"): lambda _: [{"id": "l1", "name": "todo"}],
            ("GET", "/boards/board123/labels"): lambda _: [],
            ("GET", "/boards/board123/members"): lambda _: [],
            ("GET", "/boards/board123/cards"): get_cards,
            ("GET", "/cards/c1/actions"): get_actions,
        },
        calls=calls,
    )

    backend = TrelloBackend()
    entries = backend.tail_ticket_changelog("abc", limit=10)
    assert entries[0].endswith("First")
    assert entries[1].endswith("Second")
