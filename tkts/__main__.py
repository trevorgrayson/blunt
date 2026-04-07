from __future__ import annotations

from argparse import ArgumentParser
from typing import List, Optional

from tkts.storage import TicketStore


def _parse_args() -> ArgumentParser:
    parser = ArgumentParser("tkts")
    parser.add_argument(
        "verb",
        nargs="?",
        default="list",
        help="Action to perform: list (default) or new.",
    )
    parser.add_argument(
        "subject",
        nargs="?",
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


def _render_list(store: TicketStore) -> int:
    tickets = store.list_tickets()
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


def _handle_new(
    store: TicketStore,
    subject: Optional[str],
    body: str,
    assignee: Optional[str],
    tags: List[str],
) -> int:
    if not subject:
        raise SystemExit("Subject is required for new tickets.")
    ticket = store.create_ticket(subject=subject, body=body, assignee=assignee, tags=tags)
    print(f"Created {ticket.ticket_id}: {ticket.subject}")
    return 0


def main() -> int:
    parser = _parse_args()
    args = parser.parse_args()
    store = TicketStore.from_env()

    verb = args.verb or "list"
    if verb in {"list", "todo"}:
        return _render_list(store)
    if verb == "new":
        return _handle_new(store, args.subject, args.body, args.assignee, _parse_tags(args.tags))

    if verb and args.subject is None:
        return _handle_new(store, verb, args.body, args.assignee, _parse_tags(args.tags))

    raise SystemExit(f"Unknown verb: {verb}")


if __name__ == "__main__":
    raise SystemExit(main())
