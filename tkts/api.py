from __future__ import annotations

from typing import Iterable, List, Optional

from tkts.backends import Backend, get_backend, get_backend_from_env
from tkts.models import Ticket


def get_store(root: Optional[str] = None, backend: Optional[str] = None) -> Backend:
    if root or backend:
        return get_backend(backend or "local", root)
    return get_backend_from_env()


def list_tickets(store: Optional[Backend] = None) -> List[Ticket]:
    store = store or get_store()
    return store.list_tickets()


def get_ticket(ticket_id: str, store: Optional[Backend] = None) -> Optional[Ticket]:
    store = store or get_store()
    return store.get_ticket(ticket_id)


def create_ticket(
    subject: str,
    body: str = "",
    assignee: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    status: Optional[str] = None,
    store: Optional[Backend] = None,
) -> Ticket:
    store = store or get_store()
    return store.create_ticket(subject=subject, body=body, assignee=assignee, tags=tags, status=status)
