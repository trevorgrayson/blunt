from __future__ import annotations

from argparse import ArgumentParser, RawDescriptionHelpFormatter
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from typing import List, Optional, Sequence

from tkts.backends import Backend, get_backend_from_env
from tkts.trello_client import TrelloError


_STATUS_ORDER = ["todo", "in-progress", "in-review", "blocked", "done"]
_STATUS_RANK = {status: idx for idx, status in enumerate(_STATUS_ORDER)}
_EXEC_PROMPT = (
    "@PRD.md @progress.txt \\\n"
    "  1. Follow @AGENTS.md\n"
    "  2. Find the highest-priority task and implement it. \\\n"
    "  3. Run your tests and type checks.\n"
    "  4. update with your progress.\n"
    "  5. Commit your changes."
)

_FEATURE_TAG_PATTERN = re.compile(r"^(?:feature:)?(?P<name>\w+)$")


def _render_feature_tag(tags: Optional[Sequence[str]]) -> Optional[str]:
    if not tags:
        return None

    explicit: list[str] = []
    implicit: list[str] = []
    for tag in tags:
        if not tag:
            continue
        match = _FEATURE_TAG_PATTERN.fullmatch(tag.strip())
        if not match:
            continue
        name = match.group("name")
        if ":" in tag:
            explicit.append(name)
        else:
            implicit.append(name)

    if explicit:
        return sorted(explicit)[0]
    if implicit:
        return sorted(implicit)[0]
    return None


def _parse_args() -> ArgumentParser:
    try:
        from tkts.backends import available_backends

        backend_names = ", ".join(available_backends())
    except Exception:
        backend_names = "local, file, trello"

    parser = ArgumentParser(
        prog="tkts",
        description="Ticket tracking with pluggable backends.",
        formatter_class=RawDescriptionHelpFormatter,
        epilog=(
            "Backend selection order:\n"
            "  1. TKTS_BACKEND env var\n"
            "  2. .tkts/config (searched from CWD upward): backend=... (or tkts_backend=...)\n"
            "  3. default: local (file-based)\n"
            "\n"
            "Backend root (file-based engine):\n"
            "  - TKTS_ROOT env var or .tkts/config root=... (or tkts_root=...)\n"
            "  - default root: ~/.tkts\n"
            "\n"
            f"Available backends: {backend_names}\n"
            "\n"
            "Examples:\n"
            "  TKTS_BACKEND=trello tkts list\n"
            "  TKTS_ROOT=./.tkts-data tkts new \"Replace printer toner\"\n"
        ),
    )
    parser.add_argument(
        "verb",
        nargs="?",
        default="todo",
        help="Action to perform: list/todo (default), new, edit, update, done, show, tail, plan, exec, tui, or mcp.",
    )
    parser.add_argument(
        "subject",
        nargs="*",
        default=None,
        help="Ticket subject for `new`.",
    )
    parser.add_argument(
        "--body",
        default=None,
        help="Optional body for new tickets.",
    )
    parser.add_argument(
        "--desc",
        "--description",
        dest="desc",
        action="store_true",
        help="Open the editor to capture the ticket description/body.",
    )
    parser.add_argument(
        "--assignee",
        default=None,
        help="Optional assignee for new tickets.",
    )
    parser.add_argument(
        "--tags",
        default=None,
        help="Comma-separated list of tags.",
    )
    parser.add_argument(
        "--status",
        default=None,
        help="Optional status for new tickets (todo, in-progress, in-review, blocked, done).",
    )
    parser.add_argument(
        "--set-subject",
        default=None,
        help="Set a new subject when updating a ticket.",
    )
    parser.add_argument(
        "--append-body",
        default=None,
        help="Append an update block to the ticket body.",
    )
    parser.add_argument(
        "--comment",
        default=None,
        help="Append a comment block to the ticket body.",
    )
    parser.add_argument(
        "--log-message",
        default=None,
        help="Add a freeform message to the change log.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Limit entries when tailing a change log.",
    )
    parser.add_argument(
        "--exec",
        dest="exec_plan",
        action="store_true",
        help="Execute a PRD by breaking it into tasks and stepping through them.",
    )
    parser.add_argument(
        "--read-only",
        dest="read_only",
        action="store_true",
        help="Run MCP server in read-only mode (no writes).",
    )
    parser.add_argument(
        "--watch",
        nargs="?",
        const=5.0,
        default=None,
        type=float,
        help="TUI only: auto-refresh ticket list every N seconds (default: 5).",
    )
    return parser


def _render_list(backend: Backend) -> int:
    tickets = backend.list_tickets()
    if not tickets:
        print("No tickets found.")
        return 0
    tickets = sorted(
        tickets,
        key=lambda ticket: (
            _STATUS_RANK.get(ticket.status or "unknown", len(_STATUS_RANK)),
            (ticket.subject or "").lower(),
            ticket.ticket_id,
        ),
    )
    for ticket in tickets:
        status = ticket.status or "unknown"
        short_id = ticket.ticket_id[:5]
        prefix = f"{short_id} [{status}]"
        feature_tag = _render_feature_tag(ticket.tags)
        if feature_tag:
            prefix = f"{prefix} {feature_tag}"
        print(f"{prefix} {ticket.subject}")
    return 0


def _parse_tags(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
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
    body: Optional[str],
    assignee: Optional[str],
    tags: List[str],
    status: Optional[str],
) -> int:
    subject = _normalize_subject(subject_parts)
    if not subject:
        raise SystemExit("Subject is required for new tickets.")
    ticket = backend.create_ticket(
        subject=subject,
        body=body or "",
        assignee=assignee,
        tags=tags,
        status=status,
    )
    print(f"Created {ticket.ticket_id}: {ticket.subject}")
    return 0


def _handle_show(backend: Backend, ticket_id: str) -> int:
    ticket = backend.get_ticket(ticket_id)
    if not ticket:
        raise SystemExit(f"Ticket {ticket_id} not found.")
    print(f"Id: {ticket.ticket_id}")
    print(f"Subject: {ticket.subject}")
    print(f"Status: {ticket.status or 'unknown'}")
    if ticket.assignee:
        print(f"Assignee: {ticket.assignee}")
    if ticket.tags:
        print(f"Tags: {', '.join(ticket.tags)}")
    print(f"Created: {ticket.created_at}")
    print(f"Updated: {ticket.updated_at}")
    if ticket.body:
        print("")
        print(ticket.body)
    return 0


def _handle_update(
    backend: Backend,
    ticket_id: str,
    subject: Optional[str],
    body: Optional[str],
    assignee: Optional[str],
    tags: Optional[List[str]],
    status: Optional[str],
    append_body: Optional[str],
    comment: Optional[str],
    log_message: Optional[str],
) -> int:
    ticket = backend.update_ticket(
        ticket_id,
        subject=subject,
        body=body,
        assignee=assignee,
        tags=tags,
        status=status,
        append_body=append_body,
        comment=comment,
        log_message=log_message,
    )
    print(f"Updated {ticket.ticket_id}: {ticket.subject}")
    return 0


def _handle_tail(backend: Backend, ticket_id: str, limit: int) -> int:
    entries = backend.tail_ticket_changelog(ticket_id, limit=limit)
    if not entries:
        print("No change log entries found.")
        return 0
    for entry in entries:
        print(entry)
    return 0


def _open_editor(path: Path) -> None:
    editor = os.environ.get("EDITOR") or "vi"
    command = shlex.split(editor) + [str(path)]
    subprocess.run(command, check=False)


def _capture_description(initial_body: Optional[str]) -> str:
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as handle:
        path = Path(handle.name)
        if initial_body:
            handle.write(initial_body)
            handle.flush()
    _open_editor(path)
    body = path.read_text(encoding="utf-8")
    path.unlink(missing_ok=True)
    return body


def _confirm(prompt: str) -> bool:
    response = input(prompt).strip().lower()
    return response in {"y", "yes"}


def _prompt_task_list() -> List[str]:
    print("Enter tasks one per line. Submit an empty line to finish.")
    tasks: List[str] = []
    while True:
        line = input("> ").strip()
        if not line:
            break
        tasks.append(line)
    return tasks


def _execute_tasks(tasks: List[str]) -> None:
    if not tasks:
        print("No tasks provided.")
        return
    for idx, task in enumerate(tasks, start=1):
        print(f"Task {idx}/{len(tasks)}: {task}")
        while True:
            if _confirm("Mark complete and move to the next task? [y/N]: "):
                break
            print("Task still in progress. Continue when ready.")


def _handle_plan(filename: str, exec_plan: bool) -> int:
    path = Path(filename).expanduser()
    if not path.exists():
        raise SystemExit(f"PRD file not found: {path}")

    while True:
        _open_editor(path)
        if _confirm("Is this PRD actionable? [y/N]: "):
            break
        print("Re-opening PRD for refinement.")

    if exec_plan:
        print("Break the PRD into actionable tasks.")
        tasks = _prompt_task_list()
        _execute_tasks(tasks)
    return 0


def _handle_exec(agent_args: Optional[Sequence[str]]) -> int:
    """
    There is a permission issue with reading the provided PRD.
    Trevor is short cutting this method to print a workable CLI command for execution.
    :param agent_args:
    :return:
    """
    return "codex exec --sandbox workspace-write @AGENTS.md"

    if agent_args:
        command = list(agent_args)
    else:
        command = ["codex", "exec", "--sandbox", "workspace-write"]
    command.append(_EXEC_PROMPT)
    result = subprocess.run(command, check=False)
    return result.returncode


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parse_args()
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    args, unknown = parser.parse_known_args(raw_args)
    if args.verb == "exec" and unknown:
        args.subject = list(args.subject or [])
        args.subject.extend(unknown)
        unknown = []
    if unknown:
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")
    try:
        backend = get_backend_from_env()
    except (ValueError, TrelloError) as exc:
        raise SystemExit(str(exc)) from None

    verb = args.verb or "list"
    if verb in {"list", "todo"}:
        return _render_list(backend)
    if verb == "new":
        body = _capture_description(args.body) if args.desc else args.body
        return _handle_new(
            backend,
            args.subject,
            body,
            args.assignee,
            _parse_tags(args.tags),
            args.status,
        )
    if verb == "edit":
        if not args.subject:
            raise SystemExit("Ticket id is required for edit.")
        if len(args.subject) != 1:
            raise SystemExit("Ticket id is required for edit.")
        ticket = backend.edit_ticket(args.subject[0])
        print(f"Updated {ticket.ticket_id}: {ticket.subject}")
        return 0
    if verb == "update":
        if not args.subject:
            raise SystemExit("Ticket id is required for update.")
        if len(args.subject) != 1:
            raise SystemExit("Ticket id is required for update.")
        tags = _parse_tags(args.tags) if args.tags is not None else None
        return _handle_update(
            backend,
            args.subject[0],
            args.set_subject,
            args.body,
            args.assignee,
            tags,
            args.status,
            args.append_body,
            args.comment,
            args.log_message,
        )
    if verb == "done":
        if not args.subject:
            raise SystemExit("Ticket id is required for done.")
        if len(args.subject) != 1:
            raise SystemExit("Ticket id is required for done.")
        tags = _parse_tags(args.tags) if args.tags is not None else None
        return _handle_update(
            backend,
            args.subject[0],
            args.set_subject,
            args.body,
            args.assignee,
            tags,
            "done",
            args.append_body,
            args.comment,
            args.log_message,
        )
    if verb == "show":
        if not args.subject:
            raise SystemExit("Ticket id is required for show.")
        if len(args.subject) != 1:
            raise SystemExit("Ticket id is required for show.")
        return _handle_show(backend, args.subject[0])
    if verb == "tail":
        if not args.subject:
            raise SystemExit("Ticket id is required for tail.")
        if len(args.subject) != 1:
            raise SystemExit("Ticket id is required for tail.")
        return _handle_tail(backend, args.subject[0], args.limit)
    if verb == "mcp":
        from tkts.mcp_server import run_mcp_server

        return run_mcp_server(read_only=args.read_only)
    if verb in {"tui", "ncurses"}:
        try:
            from tkts.ncurses_tui import run_tui
        except Exception as exc:  # pragma: no cover - curses import failures
            raise SystemExit(f"Unable to start TUI: {exc}") from None
        if args.watch is not None and args.watch <= 0:
            raise SystemExit("--watch must be > 0 seconds.")
        return run_tui(watch=args.watch)
    if verb == "plan":
        if not args.subject:
            raise SystemExit("Filename is required for plan.")
        if len(args.subject) != 1:
            raise SystemExit("Only one filename is supported for plan.")
        return _handle_plan(args.subject[0], args.exec_plan)
    if verb == "exec":
        return _handle_exec(args.subject)

    if verb:
        subject_parts = [verb]
        if args.subject:
            subject_parts.extend(args.subject)
        body = _capture_description(args.body) if args.desc else args.body
        return _handle_new(
            backend,
            subject_parts,
            body,
            args.assignee,
            _parse_tags(args.tags),
            args.status,
        )

    raise SystemExit(f"Unknown verb: {verb}")


if __name__ == "__main__":
    raise SystemExit(main())
