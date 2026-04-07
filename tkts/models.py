from __future__ import annotations

from dataclasses import dataclass, field
from email.message import EmailMessage
from email.parser import Parser
from email.policy import default
from typing import Dict, List, Optional


def _split_tags(raw: str) -> List[str]:
    if not raw:
        return []
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def _join_tags(tags: List[str]) -> str:
    return ", ".join(tags)


@dataclass
class Ticket:
    ticket_id: str
    subject: str
    body: str
    assignee: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    extra_headers: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_string(cls, raw: str, fallback_id: Optional[str] = None) -> "Ticket":
        message = Parser(policy=default).parsestr(raw)
        ticket_id = message.get("Id") or message.get("Ticket-Id") or fallback_id
        if not ticket_id:
            raise ValueError("Ticket id missing")

        subject = message.get("Subject", "").strip()
        body = message.get_body(preferencelist=("plain",))
        body_text = body.get_content() if body else message.get_content()

        assignee = message.get("Assignee")
        tags = _split_tags(message.get("Tags", ""))

        created_at = message.get("Created")
        updated_at = message.get("Updated")

        extra_headers: Dict[str, str] = {}
        for key, value in message.items():
            if key in {"Id", "Ticket-Id", "Subject", "Assignee", "Tags", "Created", "Updated"}:
                continue
            extra_headers[key] = value

        return cls(
            ticket_id=ticket_id,
            subject=subject,
            body=body_text,
            assignee=assignee,
            tags=tags,
            created_at=created_at,
            updated_at=updated_at,
            extra_headers=extra_headers,
        )

    def to_message(self) -> EmailMessage:
        message = EmailMessage()
        message["Id"] = self.ticket_id
        message["Subject"] = self.subject
        if self.assignee:
            message["Assignee"] = self.assignee
        if self.tags:
            message["Tags"] = _join_tags(self.tags)
        if self.created_at:
            message["Created"] = self.created_at
        if self.updated_at:
            message["Updated"] = self.updated_at
        for key, value in self.extra_headers.items():
            if key in message:
                continue
            message[key] = value
        message.set_content(self.body or "")
        return message

    def to_string(self) -> str:
        return self.to_message().as_string()
