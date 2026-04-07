from __future__ import annotations

import os
import sys

from tkts.__main__ import main
from tkts.storage import TicketStore


_STATUS_ORDER = ["todo", "in-progress", "in-review", "blocked", "done"]
_STATUS_RANK = {status: idx for idx, status in enumerate(_STATUS_ORDER)}


def _run_cli(args: list[str], tmp_path: os.PathLike[str], capsys, monkeypatch) -> str:
    monkeypatch.setenv("TKTS_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["tkts", *args])
    main()
    return capsys.readouterr().out


def _extract_status(line: str) -> str:
    if "[" not in line or "]" not in line:
        return "unknown"
    return line.split("[", 1)[1].split("]", 1)[0].strip() or "unknown"


def test_cli_list_sorted_by_status(tmp_path: os.PathLike[str], capsys, monkeypatch) -> None:
    store = TicketStore(root=tmp_path)
    store.create_ticket(subject="Done ticket", body="Body", status="done")
    store.create_ticket(subject="Todo ticket", body="Body", status="todo")
    store.create_ticket(subject="Blocked ticket", body="Body", status="blocked")
    store.create_ticket(subject="In progress ticket", body="Body", status="in-progress")
    store.create_ticket(subject="In review ticket", body="Body", status="in-review")
    store.create_ticket(subject="Unknown ticket", body="Body", status=None)

    output = _run_cli(["list"], tmp_path, capsys, monkeypatch)
    lines = [line for line in output.splitlines() if line.strip()]

    assert len(lines) == 6

    ranks = [
        _STATUS_RANK.get(_extract_status(line), len(_STATUS_RANK))
        for line in lines
    ]
    assert ranks == sorted(ranks)
