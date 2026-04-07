# tkts Backend Interface Specification

This document defines the backend interface expected by tkts and describes how to select or migrate tickets between engines.

## Overview

Backends implement the `Backend` protocol defined in `tkts/backends.py`. The CLI, Python API, and MCP server depend on these methods to manage tickets.

A backend is registered with `register_backend(name, factory)` where `factory` has the signature `factory(root: Optional[str]) -> Backend`.

## Backend Contract

Backends must implement the following methods:

- `list_tickets() -> List[Ticket]`
  - Return all tickets for the backend.

- `get_ticket(ticket_id: str) -> Optional[Ticket]`
  - Return a ticket by id.
  - Local backend supports prefix matching; other backends should either do the same or require full ids.
  - Return `None` if the ticket is not found.

- `create_ticket(subject: str, body: str = "", assignee: Optional[str] = None, tags: Optional[List[str]] = None, status: Optional[str] = None) -> Ticket`
  - Create a ticket and return the created record.
  - Implementations should validate `status` against allowed values (`todo`, `in-progress`, `in-review`, `blocked`, `done`).

- `edit_ticket(ticket_id: str) -> Ticket`
  - Open the ticket for editing and return the updated ticket.
  - For non-file backends, this may be a no-op or delegated to the backend UI.

- `update_ticket(ticket_id: str, subject: Optional[str] = None, body: Optional[str] = None, assignee: Optional[str] = None, tags: Optional[List[str]] = None, status: Optional[str] = None, append_body: Optional[str] = None, comment: Optional[str] = None, log_message: Optional[str] = None) -> Ticket`
  - Apply structured updates to a ticket and return the updated ticket.
  - If `append_body` or `comment` are provided, the local backend appends a block to the ticket body and records a changelog entry.

- `tail_ticket_changelog(ticket_id: str, limit: int = 10) -> List[str]`
  - Return the most recent change log entries.
  - Return entries in chronological order (oldest to newest), truncated to `limit`.

## Ticket Model

Backends should return `tkts.models.Ticket` instances. Fields used by tkts:

- `ticket_id`: Unique identifier for the ticket.
- `subject`: Short title.
- `body`: Primary text body.
- `assignee`: Optional assignee.
- `tags`: Optional list of tags.
- `status`: Optional status (`todo`, `in-progress`, `in-review`, `blocked`, `done`).
- `created_at`, `updated_at`: ISO-8601 timestamps if available.
- `documents`: Optional list of text/plain documents (multi-document support).
- `extra_headers`: Additional metadata headers (optional).

## Selecting a Backend

The backend is chosen in this order:

1. `TKTS_BACKEND` environment variable.
2. `.tkts/config` file entry `backend=...` or `tkts_backend=...`.
3. Defaults to `local`.

You can also override the backend root via `TKTS_ROOT` or `.tkts/config` `root=...`/`tkts_root=...` for backends that use a filesystem root.

## Transferring Tickets Between Backends

tkts does not ship a dedicated migration command yet, but you can use the Python API to move selected tickets:

```python
from tkts.backends import get_backend

source = get_backend("local", root="/path/to/source")
target = get_backend("jira")

for ticket in source.list_tickets():
    target.create_ticket(
        subject=ticket.subject,
        body=ticket.body,
        assignee=ticket.assignee,
        tags=ticket.tags,
        status=ticket.status,
    )
```

Notes:

- If you need to migrate only specific tickets, filter `source.list_tickets()` by `ticket_id` or tags.
- The core API only accepts the primary body text; if your backend supports richer documents or attachments, extend the migration to map `ticket.documents` to your backend’s attachment model.
- Backends that support changelog entries can store a summary of migration activity via `update_ticket(..., log_message=...)` after creation.
