from __future__ import annotations

import os

import pytest

from tkts.models import Ticket
from tkts.storage import TicketStore


def _make_ticket(ticket_id: str, subject: str) -> Ticket:
    return Ticket(
        ticket_id=ticket_id,
        subject=subject,
        body="Body",
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-01T00:00:00Z",
    )


def test_get_ticket_accepts_prefix(tmp_path: os.PathLike[str]) -> None:
    store = TicketStore(root=tmp_path)
    store.save_ticket(_make_ticket("abc12345", "First"))
    store.save_ticket(_make_ticket("def67890", "Second"))

    ticket = store.get_ticket("abc1")

    assert ticket is not None
    assert ticket.ticket_id == "abc12345"


def test_get_ticket_rejects_ambiguous_prefix(tmp_path: os.PathLike[str]) -> None:
    store = TicketStore(root=tmp_path)
    store.save_ticket(_make_ticket("abc12345", "First"))
    store.save_ticket(_make_ticket("abc67890", "Second"))

    with pytest.raises(ValueError, match="Multiple tickets match"):
        store.get_ticket("abc")


def test_edit_ticket_accepts_prefix(tmp_path: os.PathLike[str], monkeypatch: pytest.MonkeyPatch) -> None:
    store = TicketStore(root=tmp_path)
    store.save_ticket(_make_ticket("deadbeef", "Fix build"))

    monkeypatch.setenv("EDITOR", "true")

    ticket = store.edit_ticket("dead")

    assert ticket.ticket_id == "deadbeef"
