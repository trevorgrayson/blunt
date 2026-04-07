from __future__ import annotations

import os

from tkts.storage import TicketStore


def test_update_ticket_status_and_changelog(tmp_path: os.PathLike[str]) -> None:
    store = TicketStore(root=tmp_path)
    ticket = store.create_ticket(subject="Test ticket", body="Body", status="todo")

    updated = store.update_ticket(ticket.ticket_id, status="in-progress", comment="Starting work")

    assert updated.status == "in-progress"
    changelog = store.tail_ticket_changelog(ticket.ticket_id, limit=5)
    assert changelog
    assert any("status todo -> in-progress" in entry for entry in changelog)
    assert any("comment added" in entry for entry in changelog)


def test_update_ticket_with_existing_changelog(tmp_path: os.PathLike[str]) -> None:
    store = TicketStore(root=tmp_path)
    ticket = store.create_ticket(subject="Test ticket", body="Body", status="todo")

    store.update_ticket(ticket.ticket_id, comment="First update")
    updated = store.update_ticket(ticket.ticket_id, status="done", comment="Second update")

    assert updated.status == "done"
    changelog = store.tail_ticket_changelog(ticket.ticket_id, limit=10)
    assert any("comment added" in entry for entry in changelog)
