from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol

from tkts.models import Ticket
from tkts.storage import TicketStore, load_config


class Backend(Protocol):
    def list_tickets(self) -> List[Ticket]:
        ...

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        ...

    def create_ticket(
        self,
        subject: str,
        body: str = "",
        assignee: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Ticket:
        ...

    def edit_ticket(self, ticket_id: str) -> Ticket:
        ...


BackendFactory = Callable[[Optional[str]], Backend]

_BACKENDS: Dict[str, BackendFactory] = {}


def register_backend(name: str, factory: BackendFactory) -> None:
    key = name.strip().lower()
    if not key:
        raise ValueError("Backend name is required.")
    _BACKENDS[key] = factory


def available_backends() -> List[str]:
    return sorted(_BACKENDS.keys())


def get_backend(name: Optional[str] = None, root: Optional[str] = None) -> Backend:
    key = (name or "local").strip().lower()
    factory = _BACKENDS.get(key)
    if not factory:
        raise ValueError(f"Unknown backend: {name}")
    return factory(root)


def get_backend_from_env(start: Optional[Path] = None) -> Backend:
    config = load_config(start)
    backend = os.environ.get("TKTS_BACKEND") or config.backend or "local"
    root = os.environ.get("TKTS_ROOT") or config.root
    return get_backend(backend, root)


def _local_backend(root: Optional[str]) -> Backend:
    if root:
        return TicketStore(Path(root).expanduser())
    return TicketStore.from_env()


register_backend("local", _local_backend)
register_backend("file", _local_backend)
