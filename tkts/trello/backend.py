from __future__ import annotations

import json
import os
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

from tkts.backends import register_backend
from tkts.models import Ticket
from tkts.trello.client import (
    TrelloAmbiguousIdError,
    TrelloClient,
    TrelloConfigError,
    TrelloCredentials,
    TrelloNotFoundError,
)


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


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _env_str(name: str, default: Optional[str] = None) -> Optional[str]:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip()
    return value or default


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_status_to_list(raw: Optional[str]) -> Dict[str, str]:
    if not raw:
        return {}
    raw = raw.strip()
    if not raw:
        return {}
    if raw.startswith("{"):
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise TrelloConfigError("TRELLO_STATUS_TO_LIST must be a JSON object or 'k:v,k:v' string.")
        mapping: Dict[str, str] = {}
        for key, value in payload.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            normalized = _normalize_status(key)
            if normalized:
                mapping[normalized] = value.strip()
        return mapping
    mapping = {}
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    for part in parts:
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        normalized = _normalize_status(key)
        if not normalized:
            continue
        mapping[normalized] = value.strip()
    return mapping


def _assignee_field() -> str:
    field = (_env_str("TRELLO_ASSIGNEE_FIELD", "username") or "username").strip()
    if field not in {"username", "fullName", "id"}:
        raise TrelloConfigError("TRELLO_ASSIGNEE_FIELD must be one of: username, fullName, id.")
    return field


@dataclass
class _BoardCache:
    lists_by_id: Dict[str, str]
    list_ids_by_name_lc: Dict[str, str]
    labels_by_name_lc: Dict[str, Dict[str, Any]]
    members: List[Dict[str, Any]]


class TrelloBackend:
    def __init__(self, root: Optional[str] = None) -> None:
        _ = root
        board_id = _env_str("TRELLO_BOARD_ID")
        if not board_id:
            raise TrelloConfigError("Missing Trello board id: `TRELLO_BOARD_ID`.")

        self._board_id = board_id
        self._include_done = _env_bool("TRELLO_INCLUDE_DONE", False)
        self._create_missing_labels = _env_bool("TRELLO_CREATE_MISSING_LABELS", False)
        self._default_status = _normalize_status(_env_str("TRELLO_DEFAULT_STATUS", "todo")) or "todo"
        self._edit_opens_browser = _env_bool("TRELLO_EDIT_OPENS_BROWSER", False)
        self._status_to_list = {status: status for status in _ALLOWED_STATUSES}
        self._status_to_list.update(_parse_status_to_list(_env_str("TRELLO_STATUS_TO_LIST")))

        self._client = TrelloClient(credentials=TrelloCredentials.from_env())
        self._cache: Optional[_BoardCache] = None

    def _load_cache(self) -> _BoardCache:
        if self._cache is not None:
            return self._cache

        lists = self._client.get_board_lists(self._board_id)
        lists_by_id: Dict[str, str] = {}
        list_ids_by_name_lc: Dict[str, str] = {}
        for entry in lists or []:
            list_id = str(entry.get("id") or "")
            name = str(entry.get("name") or "").strip()
            if not list_id or not name:
                continue
            lists_by_id[list_id] = name
            list_ids_by_name_lc[name.lower()] = list_id

        labels = self._client.get_board_labels(self._board_id)
        labels_by_name_lc: Dict[str, Dict[str, Any]] = {}
        for label in labels or []:
            label_id = str(label.get("id") or "")
            name = str(label.get("name") or "").strip()
            if not label_id or not name:
                continue
            labels_by_name_lc[name.lower()] = label

        members = self._client.get_board_members(self._board_id) or []

        self._cache = _BoardCache(
            lists_by_id=lists_by_id,
            list_ids_by_name_lc=list_ids_by_name_lc,
            labels_by_name_lc=labels_by_name_lc,
            members=members,
        )
        return self._cache

    def _status_from_list_name(self, list_name: str) -> Optional[str]:
        name_lc = (list_name or "").strip().lower()
        if not name_lc:
            return None
        for status, mapped in self._status_to_list.items():
            if mapped.strip().lower() == name_lc:
                return status
        if name_lc in _ALLOWED_STATUSES:
            return name_lc
        return list_name.strip() or None

    def _list_id_for_status(self, status: str) -> str:
        normalized = _normalize_status(status)
        if not normalized:
            raise ValueError("Status is required.")
        cache = self._load_cache()
        desired_name = (self._status_to_list.get(normalized) or normalized).strip().lower()
        list_id = cache.list_ids_by_name_lc.get(desired_name)
        if not list_id:
            raise TrelloConfigError(
                f"Missing Trello list for status '{normalized}' (expected list named '{self._status_to_list.get(normalized) or normalized}')."
            )
        return list_id

    def _resolve_assignee(self, assignee: Optional[str]) -> Optional[str]:
        value = (assignee or "").strip()
        return value or None

    def _member_id_for_assignee(self, assignee: str) -> str:
        field = _assignee_field()
        cache = self._load_cache()
        needle = assignee.strip().lower()
        matches: list[Dict[str, Any]] = []
        for member in cache.members:
            if field == "id":
                candidate = str(member.get("id") or "").strip().lower()
            else:
                candidate = str(member.get(field) or "").strip().lower()
            if candidate and candidate == needle:
                matches.append(member)
        if not matches and field != "id":
            for member in cache.members:
                candidate = str(member.get("username") or "").strip().lower()
                if candidate and candidate == needle:
                    matches.append(member)
                    break
        if len(matches) == 1:
            member_id = str(matches[0].get("id") or "")
            if member_id:
                return member_id
        if len(matches) > 1:
            raise TrelloAmbiguousIdError(f"Assignee '{assignee}' matched multiple Trello members.")
        raise TrelloConfigError(f"Assignee '{assignee}' not found on Trello board members.")

    def _label_ids_for_tags(self, tags: Optional[Iterable[str]]) -> List[str]:
        if not tags:
            return []
        cache = self._load_cache()
        label_ids: List[str] = []
        missing: List[str] = []
        for tag in tags:
            name = (tag or "").strip()
            if not name:
                continue
            label = cache.labels_by_name_lc.get(name.lower())
            if not label:
                missing.append(name)
                continue
            label_id = str(label.get("id") or "")
            if label_id:
                label_ids.append(label_id)
        if missing and self._create_missing_labels:
            for name in missing:
                label = self._client.create_board_label(self._board_id, name)
                label_id = str(label.get("id") or "")
                if label_id:
                    label_ids.append(label_id)
            return label_ids
        if missing:
            missing_display = ", ".join(sorted(missing))
            raise TrelloConfigError(
                f"Missing Trello labels on board: {missing_display}. "
                "Create them in Trello or set `TRELLO_CREATE_MISSING_LABELS=true`."
            )
        return label_ids

    def _ticket_from_card(self, card: Dict[str, Any], *, lists_by_id: Dict[str, str]) -> Ticket:
        ticket_id = str(card.get("shortLink") or card.get("id") or "")
        subject = str(card.get("name") or "")
        body = str(card.get("desc") or "")
        list_id = str(card.get("idList") or "")
        list_name = lists_by_id.get(list_id, "")
        status = self._status_from_list_name(list_name)
        tags = [str(label.get("name") or "") for label in card.get("labels", []) if label.get("name")]
        members = card.get("members") or []
        assignee = None
        if members:
            field = _assignee_field()
            primary = members[0]
            if field == "id":
                assignee = str(primary.get("id") or "")
            else:
                assignee = str(primary.get(field) or "")
            assignee = assignee or None
        updated_at = str(card.get("dateLastActivity") or "")
        url = str(card.get("url") or "")
        extra_headers = {
            "Trello-Card-Id": str(card.get("id") or ""),
            "Trello-Url": url,
        }
        return Ticket(
            ticket_id=ticket_id,
            subject=subject,
            body=body,
            assignee=assignee,
            tags=tags,
            status=status,
            created_at=None,
            updated_at=updated_at,
            extra_headers=extra_headers,
        )

    def list_tickets(self, *, list_name: Optional[str] = None) -> List[Ticket]:
        list_name = list_name or _env_str("TKTS_TRELLO_LIST")
        cache = self._load_cache()
        cards = self._client.list_board_cards(
            self._board_id,
            fields="shortLink,name,desc,idList,labels,idMembers,dateLastActivity,url",
            filter="open",
            include_members=True,
            list_name=list_name,
        )
        tickets = [self._ticket_from_card(card, lists_by_id=cache.lists_by_id) for card in cards or []]
        if list_name:
            return tickets
        if self._include_done:
            return tickets
        return [ticket for ticket in tickets if ticket.status != "done"]

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        cache = self._load_cache()
        card = self._resolve_ticket(ticket_id)
        if not card:
            return None
        return self._ticket_from_card(card, lists_by_id=cache.lists_by_id)

    def _resolve_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        if not ticket_id:
            return None
        ticket_id = ticket_id.strip()
        if not ticket_id:
            return None

        if len(ticket_id) >= 8:
            card = self._client.get_card(
                ticket_id,
                fields="shortLink,name,desc,idList,labels,idMembers,dateLastActivity,url",
            )
            return card

        cards = self._client.list_board_cards(
            self._board_id,
            fields="shortLink,name,desc,idList,labels,idMembers,dateLastActivity,url",
            filter="open",
            include_members=True,
        )
        matches = [card for card in cards or [] if str(card.get("shortLink") or "").startswith(ticket_id)]
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        ids = ", ".join(sorted(str(card.get("shortLink") or "") for card in matches if card.get("shortLink")))
        raise TrelloAmbiguousIdError(f"Ticket id prefix '{ticket_id}' matched multiple Trello cards: {ids}")

    def create_ticket(
        self,
        subject: str,
        body: str = "",
        assignee: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
    ) -> Ticket:
        subject = (subject or "").strip()
        if not subject:
            raise ValueError("Subject is required.")
        body = body or ""
        status = _normalize_status(status) or self._default_status

        list_id = self._list_id_for_status(status)
        member_ids = []
        if assignee:
            member_ids.append(self._member_id_for_assignee(assignee))
        label_ids = self._label_ids_for_tags(tags)

        card = self._client.create_card(
            name=subject,
            desc=body,
            list_id=list_id,
            member_ids=member_ids,
            label_ids=label_ids,
        )
        ticket = self.get_ticket(str(card.get("shortLink") or ""))
        if ticket:
            return ticket
        return Ticket(
            ticket_id=str(card.get("shortLink") or card.get("id") or ""),
            subject=subject,
            body=body,
            assignee=assignee,
            tags=tags or [],
            status=status,
            created_at=None,
            updated_at=_utc_now_iso(),
            extra_headers={"Trello-Card-Id": str(card.get("id") or "")},
        )

    def edit_ticket(self, ticket_id: str) -> Ticket:
        if not self._edit_opens_browser:
            ticket = self.get_ticket(ticket_id)
            if not ticket:
                raise TrelloNotFoundError(f"Ticket {ticket_id} not found.")
            return ticket
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            raise TrelloNotFoundError(f"Ticket {ticket_id} not found.")
        url = ticket.extra_headers.get("Trello-Url")
        if url:
            webbrowser.open(url)
        return ticket

    def update_ticket(
        self,
        ticket_id: str,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        assignee: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        append_body: Optional[str] = None,
        comment: Optional[str] = None,
        log_message: Optional[str] = None,
    ) -> Ticket:
        card = self._resolve_ticket(ticket_id)
        if not card:
            raise TrelloNotFoundError(f"Ticket {ticket_id} not found.")

        updates: Dict[str, Any] = {}
        if subject is not None:
            updates["name"] = subject
        if body is not None:
            updates["desc"] = body
        if status is not None:
            list_id = self._list_id_for_status(status)
            updates["idList"] = list_id
        if assignee is not None:
            member_ids: List[str] = []
            resolved = self._resolve_assignee(assignee)
            if resolved:
                member_ids.append(self._member_id_for_assignee(resolved))
            updates["idMembers"] = ",".join(member_ids)
        if tags is not None:
            label_ids = self._label_ids_for_tags(tags)
            updates["idLabels"] = ",".join(label_ids)

        if updates:
            self._client.update_card(str(card.get("id") or ""), fields=updates)

        if append_body:
            self._client.add_card_comment(str(card.get("id") or ""), f"Append: {append_body}")
        if comment:
            self._client.add_card_comment(str(card.get("id") or ""), comment)
        if log_message:
            self._client.add_card_comment(str(card.get("id") or ""), f"Log: {log_message}")

        updated = self.get_ticket(ticket_id)
        if not updated:
            raise TrelloNotFoundError(f"Ticket {ticket_id} not found.")
        return updated

    def tail_ticket_changelog(self, ticket_id: str, limit: int = 10) -> List[str]:
        card = self._resolve_ticket(ticket_id)
        if not card:
            raise TrelloNotFoundError(f"Ticket {ticket_id} not found.")
        actions = self._client.list_card_actions(str(card.get("id") or ""), limit=limit)
        lines: List[str] = []
        for action in actions or []:
            text = str(action.get("data", {}).get("text") or "")
            member = action.get("memberCreator") or {}
            name = str(member.get("fullName") or member.get("username") or "unknown")
            created_at = str(action.get("date") or "")
            lines.append(f"[{created_at}] {name}: {text}")
        return lines


def _trello_backend_factory(root: Optional[str]) -> TrelloBackend:
    return TrelloBackend(root=root)


register_backend("trello", _trello_backend_factory)
