from __future__ import annotations

from argparse import ArgumentParser
from typing import List, Optional, Sequence

from tkts.backends import Backend, get_backend_from_env


def _parse_args() -> ArgumentParser:
    parser = ArgumentParser("tkts")
    parser.add_argument(
        "verb",
        nargs="?",
        default="list",
        help="Action to perform: list (default), new, edit, or mcp.",
    )
    parser.add_argument(
        "subject",
        nargs="*",
        default=None,
        help="Ticket subject for `new`.",
    )
    parser.add_argument(
        "--body",
        default="",
        help="Optional body for new tickets.",
    )
    parser.add_argument(
        "--assignee",
        default=None,
        help="Optional assignee for new tickets.",
    )
    parser.add_argument(
        "--tags",
        default="",
        help="Comma-separated list of tags.",
    )
    return parser


def _render_list(backend: Backend) -> int:
    tickets = backend.list_tickets()
    if not tickets:
        print("No tickets found.")
        return 0
    for ticket in tickets:
        tag_text = f" [{', '.join(ticket.tags)}]" if ticket.tags else ""
        assignee_text = f" ({ticket.assignee})" if ticket.assignee else ""
        print(f"{ticket.ticket_id}: {ticket.subject}{assignee_text}{tag_text}")
    return 0


def _parse_tags(raw: str) -> List[str]:
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def _normalize_subject(subject_parts: Optional[Sequence[str]]) -> Optional[str]:
    if not subject_parts:
        return None
    if isinstance(subject_parts, str):
        return subject_parts
    subject = " ".join(part.strip() for part in subject_parts if part.strip())
    return subject or None


def _handle_new(
    backend: Backend,
    subject_parts: Optional[Sequence[str] | str],
    body: str,
    assignee: Optional[str],
    tags: List[str],
) -> int:
    subject = _normalize_subject(subject_parts)
    if not subject:
        raise SystemExit("Subject is required for new tickets.")
    ticket = backend.create_ticket(subject=subject, body=body, assignee=assignee, tags=tags)
    print(f"Created {ticket.ticket_id}: {ticket.subject}")
    return 0


def main() -> int:
    parser = _parse_args()
    args = parser.parse_args()
    backend = get_backend_from_env()

    verb = args.verb or "list"
    if verb in {"list", "todo"}:
        return _render_list(backend)
    if verb == "new":
        return _handle_new(backend, args.subject, args.body, args.assignee, _parse_tags(args.tags))
    if verb == "edit":
        if not args.subject:
            raise SystemExit("Ticket id is required for edit.")
        if len(args.subject) != 1:
            raise SystemExit("Ticket id is required for edit.")
        ticket = backend.edit_ticket(args.subject[0])
        print(f"Updated {ticket.ticket_id}: {ticket.subject}")
        return 0
    if verb == "mcp":
        from tkts.mcp_server import run_mcp_server

        return run_mcp_server()

    if verb:
        subject_parts = [verb]
        if args.subject:
            subject_parts.extend(args.subject)
        return _handle_new(backend, subject_parts, args.body, args.assignee, _parse_tags(args.tags))

    raise SystemExit(f"Unknown verb: {verb}")


if __name__ == "__main__":
    raise SystemExit(main())
