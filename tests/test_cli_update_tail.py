from __future__ import annotations

import os
import sys

from tkts.__main__ import main
from tkts.storage import TicketStore


def _run_cli(args: list[str], tmp_path: os.PathLike[str], capsys, monkeypatch) -> str:
    monkeypatch.setenv("TKTS_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["tkts", *args])
    main()
    return capsys.readouterr().out


def test_cli_update_and_tail(tmp_path: os.PathLike[str], capsys, monkeypatch) -> None:
    store = TicketStore(root=tmp_path)
    ticket = store.create_ticket(subject="CLI ticket", body="Body", status="todo")

    output = _run_cli(
        ["update", ticket.ticket_id, "--status", "in-progress", "--comment", "Starting work"],
        tmp_path,
        capsys,
        monkeypatch,
    )

    assert "Updated" in output

    tail_output = _run_cli(
        ["tail", ticket.ticket_id, "--limit", "5"],
        tmp_path,
        capsys,
        monkeypatch,
    )

    assert "status todo -> in-progress" in tail_output
    assert "comment added" in tail_output


def test_cli_done_marks_ticket_complete(tmp_path: os.PathLike[str], capsys, monkeypatch) -> None:
    store = TicketStore(root=tmp_path)
    ticket = store.create_ticket(subject="CLI done ticket", body="Body", status="in-progress")

    output = _run_cli(
        ["done", ticket.ticket_id],
        tmp_path,
        capsys,
        monkeypatch,
    )

    assert "Updated" in output

    updated = store.get_ticket(ticket.ticket_id)
    assert updated is not None
    assert updated.status == "done"
