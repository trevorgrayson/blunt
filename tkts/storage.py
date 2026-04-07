from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from tkts.models import Ticket


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TicketStore:
    root: Path

    @classmethod
    def from_env(cls) -> "TicketStore":
        root = os.environ.get("TKTS_ROOT")
        if root:
            return cls(Path(root).expanduser())
        return cls(Path.home() / ".tkts")

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def ticket_dir(self) -> Path:
        return self.root / "tickets"

    def _ticket_path(self, ticket_id: str) -> Path:
        return self.ticket_dir() / f"{ticket_id}.tkt"

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
        path = self._ticket_path(ticket_id)
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        return Ticket.from_string(raw, fallback_id=ticket_id)

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
    ) -> Ticket:
        ticket_id = uuid.uuid4().hex
        now = _utc_now_iso()
        ticket = Ticket(
            ticket_id=ticket_id,
            subject=subject,
            body=body,
            assignee=assignee,
            tags=list(tags or []),
            created_at=now,
            updated_at=now,
        )
        self.save_ticket(ticket)
        return ticket
