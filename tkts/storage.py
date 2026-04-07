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
