from __future__ import annotations

from argparse import ArgumentParser
import os
from pathlib import Path
import shlex
import subprocess
from typing import List, Optional, Sequence

from tkts.backends import Backend, get_backend_from_env


def _parse_args() -> ArgumentParser:
    parser = ArgumentParser("tkts")
    parser.add_argument(
        "verb",
        nargs="?",
        default="todo",
        help="Action to perform: list/todo (default), new, edit, plan, or mcp.",
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
    parser.add_argument(
        "--status",
        default=None,
        help="Optional status for new tickets (e.g., blocked, done).",
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
    status: Optional[str],
) -> int:
    subject = _normalize_subject(subject_parts)
    if not subject:
        raise SystemExit("Subject is required for new tickets.")
    ticket = backend.create_ticket(
        subject=subject,
        body=body,
        assignee=assignee,
        tags=tags,
        status=status,
    )
    print(f"Created {ticket.ticket_id}: {ticket.subject}")
    return 0


def _open_editor(path: Path) -> None:
    editor = os.environ.get("EDITOR") or "vi"
    command = shlex.split(editor) + [str(path)]
    subprocess.run(command, check=False)


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


def main() -> int:
    parser = _parse_args()
    args = parser.parse_args()
    backend = get_backend_from_env()

    verb = args.verb or "list"
    if verb in {"list", "todo"}:
        return _render_list(backend)
    if verb == "new":
        return _handle_new(
            backend,
            args.subject,
            args.body,
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
    if verb == "mcp":
        from tkts.mcp_server import run_mcp_server

        return run_mcp_server(read_only=args.read_only)
    if verb == "plan":
        if not args.subject:
            raise SystemExit("Filename is required for plan.")
        if len(args.subject) != 1:
            raise SystemExit("Only one filename is supported for plan.")
        return _handle_plan(args.subject[0], args.exec_plan)

    if verb:
        subject_parts = [verb]
        if args.subject:
            subject_parts.extend(args.subject)
        return _handle_new(
            backend,
            subject_parts,
            args.body,
            args.assignee,
            _parse_tags(args.tags),
            args.status,
        )

    raise SystemExit(f"Unknown verb: {verb}")


if __name__ == "__main__":
    raise SystemExit(main())
