from __future__ import annotations

import os

import pytest

from tkts.backends import get_backend_from_env


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


_RUN = _env_bool("TRELLO_INTEGRATION")
_HAS_CREDS = all(os.environ.get(name) for name in ("TRELLO_API_KEY", "TRELLO_API_TOKEN", "TRELLO_BOARD_ID"))


@pytest.mark.skipif(not _RUN, reason="Set TRELLO_INTEGRATION=true to run Trello integration tests.")
@pytest.mark.skipif(not _HAS_CREDS, reason="Missing one of: TRELLO_API_KEY, TRELLO_API_TOKEN, TRELLO_BOARD_ID.")
def test_trello_list_tickets_smoke(monkeypatch) -> None:
    monkeypatch.setenv("TKTS_BACKEND", "trello")
    backend = get_backend_from_env()
    tickets = backend.list_tickets()
    assert isinstance(tickets, list)
