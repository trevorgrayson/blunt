from __future__ import annotations

import os
import shlex
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from tkts.models import Ticket


_ALLOWED_STATUSES = {"todo", "in-progress", "in-review", "blocked", "done"}
_CHANGE_LOG_HEADER = "Change Log:"


def _normalize_status(status: Optional[str]) -> Optional[str]:
    if status is None:
        return None
    normalized = status.strip().lower()
    if not normalized:
        return None
    if normalized not in _ALLOWED_STATUSES:
        allowed = ", ".join(sorted(_ALLOWED_STATUSES))
        raise ValueError(f"Unknown status '{status}'. Allowed values: {allowed}.")
    return normalized


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_optional_string(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_tags(tags: Optional[Iterable[str]]) -> Optional[List[str]]:
    if tags is None:
        return None
    normalized = [tag.strip() for tag in tags if tag.strip()]
    return normalized


def _extract_change_log(documents: List[str]) -> tuple[Optional[int], List[str]]:
    for idx, document in enumerate(documents):
        if not document:
            continue
        lines = document.splitlines()
        if not lines:
            continue
        if lines[0].strip() != _CHANGE_LOG_HEADER:
            continue
        entries = [line for line in lines[1:] if line.strip()]
        return idx, entries
    return None, []


def _format_change_log(entries: List[str]) -> str:
    payload = [_CHANGE_LOG_HEADER, *entries]
    return "\n".join(payload).rstrip() + "\n"


def _append_body_block(body: str, label: str, message: str, timestamp: str) -> str:
    header = f"{label} ({timestamp})"
    block = f"{header}\n{message.strip()}"
    if not body:
        return f"{block}\n"
    return f"{body.rstrip()}\n\n---\n{block}\n"


def _coerce_documents(ticket: Ticket) -> List[str]:
    if ticket.documents:
        return list(ticket.documents)
    if ticket.body:
        return [ticket.body]
    return []


def _update_documents(ticket: Ticket, documents: List[str]) -> None:
    ticket.documents = documents
    ticket.body = documents[0] if documents else ""


def _find_config_path(start: Path) -> Optional[Path]:
    resolved = start.resolve()
    for candidate_root in (resolved, *resolved.parents):
        candidate = candidate_root / ".tkts" / "config"
        if candidate.is_file():
            return candidate
    return None


@dataclass
class TktsConfig:
    root: Optional[str] = None
    backend: Optional[str] = None


def _read_config(path: Path) -> TktsConfig:
    config = TktsConfig()
    try:
        contents = path.read_text(encoding="utf-8")
    except OSError:
        return config
    for line in contents.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, value = stripped.split("=", 1)
            normalized = key.strip().lower()
            if normalized in {"root", "tkts_root"}:
                config.root = value.strip()
            elif normalized in {"backend", "tkts_backend"}:
                config.backend = value.strip()
            continue
        if config.root is None:
            config.root = stripped
    return config


def load_config(start: Optional[Path] = None) -> TktsConfig:
    candidate = _find_config_path((start or Path.cwd()))
    if not candidate:
        return TktsConfig()
    return _read_config(candidate)


@dataclass
class TicketStore:
    root: Path

    @classmethod
    def from_env(cls) -> "TicketStore":
        root = os.environ.get("TKTS_ROOT")
        if root:
            return cls(Path(root).expanduser())
        config = load_config()
        if config.root:
            return cls(Path(config.root).expanduser())
        return cls(Path.home() / ".tkts")

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def ticket_dir(self) -> Path:
        return self.root / "tickets"

    def _ticket_path(self, ticket_id: str) -> Path:
        return self.ticket_dir() / f"{ticket_id}.tkt"

    def _resolve_ticket_id(self, ticket_id: str) -> Optional[str]:
        if not ticket_id:
            return None
        if self._ticket_path(ticket_id).exists():
            return ticket_id
        matches = [candidate for candidate in self.list_ids() if candidate.startswith(ticket_id)]
        if not matches:
            return None
        if len(matches) > 1:
            raise ValueError(f"Multiple tickets match '{ticket_id}'. Be more specific.")
        return matches[0]

    def list_ids(self) -> List[str]:
        directory = self.ticket_dir()
        if not directory.exists():
            return []
        return sorted(path.stem for path in directory.glob("*.tkt"))

    def list_tickets(self) -> List[Ticket]:
        tickets = []
        for ticket_id in self.list_ids():
            ticket = self.get_ticket(ticket_id)
            if ticket:
                tickets.append(ticket)
        return tickets

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        resolved_id = self._resolve_ticket_id(ticket_id)
        if not resolved_id:
            return None
        path = self._ticket_path(resolved_id)
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        return Ticket.from_string(raw, fallback_id=resolved_id)

    def save_ticket(self, ticket: Ticket) -> None:
        self.ensure()
        directory = self.ticket_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = self._ticket_path(ticket.ticket_id)
        path.write_text(ticket.to_string(), encoding="utf-8")

    def create_ticket(
        self,
        subject: str,
        body: str = "",
        assignee: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        status: Optional[str] = None,
    ) -> Ticket:
        ticket_id = uuid.uuid4().hex
        now = _utc_now_iso()
        normalized_status = _normalize_status(status)
        ticket = Ticket(
            ticket_id=ticket_id,
            subject=subject,
            body=body,
            assignee=assignee,
            tags=list(tags or []),
            status=normalized_status,
            created_at=now,
            updated_at=now,
        )
        self.save_ticket(ticket)
        return ticket

    def edit_ticket(self, ticket_id: str) -> Ticket:
        resolved_id = self._resolve_ticket_id(ticket_id)
        if not resolved_id:
            raise FileNotFoundError(f"Ticket {ticket_id} not found.")
        path = self._ticket_path(resolved_id)
        if not path.exists():
            raise FileNotFoundError(f"Ticket {ticket_id} not found.")

        editor = os.environ.get("EDITOR") or "vi"
        command = shlex.split(editor) + [str(path)]
        subprocess.run(command, check=False)

        raw = path.read_text(encoding="utf-8")
        ticket = Ticket.from_string(raw, fallback_id=resolved_id)
        ticket.updated_at = _utc_now_iso()
        self.save_ticket(ticket)
        return ticket

    def update_ticket(
        self,
        ticket_id: str,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        assignee: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        status: Optional[str] = None,
        append_body: Optional[str] = None,
        comment: Optional[str] = None,
        log_message: Optional[str] = None,
    ) -> Ticket:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            raise FileNotFoundError(f"Ticket {ticket_id} not found.")

        changes: List[str] = []
        now = _utc_now_iso()

        if subject is not None:
            normalized_subject = subject.strip()
            if not normalized_subject:
                raise ValueError("Subject cannot be empty.")
            if normalized_subject != ticket.subject:
                changes.append(f"- {now} subject updated")
                ticket.subject = normalized_subject

        if body is not None:
            if body != ticket.body:
                changes.append(f"- {now} body replaced")
                ticket.body = body

        if assignee is not None:
            normalized_assignee = _normalize_optional_string(assignee)
            if normalized_assignee != ticket.assignee:
                changes.append(f"- {now} assignee updated")
                ticket.assignee = normalized_assignee

        if tags is not None:
            normalized_tags = _normalize_tags(tags) or []
            if normalized_tags != ticket.tags:
                changes.append(f"- {now} tags updated")
                ticket.tags = normalized_tags

        if status is not None:
            normalized_status = _normalize_optional_string(status)
            normalized_status = _normalize_status(normalized_status)
            if normalized_status != ticket.status:
                from_status = ticket.status or "unknown"
                to_status = normalized_status or "unknown"
                changes.append(f"- {now} status {from_status} -> {to_status}")
                ticket.status = normalized_status

        append_body_text = _normalize_optional_string(append_body)
        if append_body_text:
            changes.append(f"- {now} body appended")
            ticket.body = _append_body_block(ticket.body, "Update", append_body_text, now)

        comment_text = _normalize_optional_string(comment)
        if comment_text:
            changes.append(f"- {now} comment added")
            ticket.body = _append_body_block(ticket.body, "Comment", comment_text, now)

        if log_message:
            changes.append(f"- {now} note: {log_message.strip()}")

        if changes:
            documents = _coerce_documents(ticket)
            if documents:
                documents[0] = ticket.body
            else:
                documents = [ticket.body]

            change_idx, entries = _extract_change_log(documents)
            entries.extend(changes)
            change_doc = _format_change_log(entries)
            if change_idx is None:
                documents.append(change_doc)
            else:
                documents[change_idx] = change_doc
            _update_documents(ticket, documents)

            ticket.updated_at = now
            self.save_ticket(ticket)

        return ticket

    def tail_ticket_changelog(self, ticket_id: str, limit: int = 10) -> List[str]:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            raise FileNotFoundError(f"Ticket {ticket_id} not found.")
        documents = _coerce_documents(ticket)
        _, entries = _extract_change_log(documents)
        if limit <= 0:
            return []
        return entries[-limit:]
