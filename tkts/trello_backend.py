from __future__ import annotations

import json
import os
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from tkts.backends import register_backend
from tkts.models import Ticket
from tkts.trello_client import (
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
        return None

    def _list_id_for_status(self, status: str) -> str:
        normalized = _normalize_status(status)
        if not normalized:
            raise ValueError("Status is required.")
        cache = self._load_cache()
        desired_name = (self._status_to_list.get(normalized) or normalized).strip().lower()
        list_id = cache.list_ids_by_name_lc.get(desired_name)
        if not list_id:
            raise TrelloConfigError(f"Missing Trello list for status '{normalized}' (expected list named '{self._status_to_list.get(normalized) or normalized}').")
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
            if label:
                label_id = str(label.get("id") or "")
                if label_id:
                    label_ids.append(label_id)
                continue
            missing.append(name)

        if missing and not self._create_missing_labels:
            missing_display = ", ".join(sorted(set(missing)))
            raise TrelloConfigError(
                f"Missing Trello labels on board: {missing_display}. "
                "Create them in Trello or set `TRELLO_CREATE_MISSING_LABELS=true`."
            )

        for name in sorted(set(missing)):
            created = self._client.create_board_label(self._board_id, name)
            cache.labels_by_name_lc[name.lower()] = created
            label_id = str(created.get("id") or "")
            if label_id:
                label_ids.append(label_id)

        return label_ids

    def _ticket_from_card(self, card: Mapping[str, Any], *, include_body: bool) -> Ticket:
        cache = self._load_cache()
        card_id = str(card.get("id") or "")
        short_link = str(card.get("shortLink") or "")
        subject = str(card.get("name") or "")
        desc = str(card.get("desc") or "") if include_body else ""
        list_id = str(card.get("idList") or "")
        list_name = cache.lists_by_id.get(list_id, "")
        status = self._status_from_list_name(list_name)
        labels = card.get("labels") or []
        tags = [str(label.get("name") or "").strip() for label in labels if str(label.get("name") or "").strip()]
        members = card.get("members") or []
        if not isinstance(members, list):
            members = []
        primary_member = members[0] if members else None
        assignee = None
        if isinstance(primary_member, dict):
            field = _assignee_field()
            if field == "id":
                assignee = str(primary_member.get("id") or "").strip() or None
            else:
                assignee = str(primary_member.get(field) or "").strip() or None
        updated_at = str(card.get("dateLastActivity") or "") or None
        url = str(card.get("url") or "").strip()

        extra_headers: Dict[str, str] = {}
        if card_id:
            extra_headers["Trello-Card-Id"] = card_id
        if url:
            extra_headers["Trello-Url"] = url

        return Ticket(
            ticket_id=short_link,
            subject=subject,
            body=desc,
            assignee=assignee,
            tags=tags,
            status=status,
            created_at=None,
            updated_at=updated_at,
            documents=[],
            extra_headers=extra_headers,
        )

    def _resolve_card_by_shortlink_prefix(self, ticket_id: str, *, include_desc: bool) -> Optional[Dict[str, Any]]:
        prefix = (ticket_id or "").strip()
        if not prefix:
            return None
        fields = "id,shortLink,name,desc,idList,labels,idMembers,dateLastActivity,url"
        if not include_desc:
            fields = "id,shortLink,name,idList,labels,idMembers,dateLastActivity,url"
        cards = self._client.list_board_cards(self._board_id, fields=fields, filter="open", include_members=True)
        matches: List[Dict[str, Any]] = []
        for card in cards or []:
            short_link = str(card.get("shortLink") or "")
            if not short_link:
                continue
            if short_link == prefix or short_link.startswith(prefix):
                matches.append(card)
        if not matches:
            return None
        if len(matches) > 1:
            ids = ", ".join(
                sorted(
                    str(card.get("shortLink") or "")
                    for card in matches
                    if str(card.get("shortLink") or "")
                )
            )
            raise TrelloAmbiguousIdError(f"Ticket id prefix '{prefix}' matched multiple Trello cards: {ids}")
        return matches[0]

    def list_tickets(self) -> List[Ticket]:
        fields = "id,shortLink,name,idList,labels,idMembers,dateLastActivity,url"
        cards = self._client.list_board_cards(self._board_id, fields=fields, filter="open", include_members=True)
        tickets: List[Ticket] = []
        for card in cards or []:
            ticket = self._ticket_from_card(card, include_body=False)
            if not ticket.ticket_id:
                continue
            if not self._include_done and ticket.status == "done":
                continue
            tickets.append(ticket)
        return tickets

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        card = self._resolve_card_by_shortlink_prefix(ticket_id, include_desc=True)
        if not card:
            return None
        return self._ticket_from_card(card, include_body=True)

    def create_ticket(
        self,
        subject: str,
        body: str = "",
        assignee: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
    ) -> Ticket:
        normalized_status = _normalize_status(status) or self._default_status
        list_id = self._list_id_for_status(normalized_status)
        resolved_assignee = self._resolve_assignee(assignee)
        member_ids = [self._member_id_for_assignee(resolved_assignee)] if resolved_assignee else None
        label_ids = self._label_ids_for_tags(tags)
        created = self._client.create_card(name=subject, desc=body or "", list_id=list_id, member_ids=member_ids, label_ids=label_ids)
        ticket = self._ticket_from_card(created, include_body=True)
        if not self._include_done and ticket.status == "done":
            return ticket
        return ticket

    def edit_ticket(self, ticket_id: str) -> Ticket:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            raise TrelloNotFoundError(f"Ticket {ticket_id} not found.")
        if self._edit_opens_browser:
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
        card = self._resolve_card_by_shortlink_prefix(ticket_id, include_desc=True)
        if not card:
            raise TrelloNotFoundError(f"Ticket {ticket_id} not found.")
        card_id = str(card.get("id") or "")
        if not card_id:
            raise TrelloNotFoundError(f"Ticket {ticket_id} not found.")

        update_fields: Dict[str, Any] = {}
        if subject is not None:
            update_fields["name"] = subject
        if body is not None:
            update_fields["desc"] = body
        if status is not None:
            normalized_status = _normalize_status(status)
            if normalized_status:
                update_fields["idList"] = self._list_id_for_status(normalized_status)
        if tags is not None:
            update_fields["idLabels"] = ",".join(self._label_ids_for_tags(tags))
        if assignee is not None:
            resolved = self._resolve_assignee(assignee)
            if resolved:
                update_fields["idMembers"] = self._member_id_for_assignee(resolved)
            else:
                update_fields["idMembers"] = ""

        if update_fields:
            card = self._client.update_card(card_id, fields=update_fields)

        if append_body:
            text = f"Append ({_utc_now_iso()})\n{append_body.strip()}"
            self._client.add_card_comment(card_id, text)
        if comment:
            self._client.add_card_comment(card_id, comment.strip())
        if log_message:
            text = f"Log ({_utc_now_iso()})\n{log_message.strip()}"
            self._client.add_card_comment(card_id, text)

        refreshed = self._resolve_card_by_shortlink_prefix(str(card.get("shortLink") or ticket_id), include_desc=True)
        if not refreshed:
            card = self._client.get_card(card_id, fields="id,shortLink,name,desc,idList,labels,idMembers,dateLastActivity,url")
            return self._ticket_from_card(card, include_body=True)
        return self._ticket_from_card(refreshed, include_body=True)

    def tail_ticket_changelog(self, ticket_id: str, limit: int = 10) -> List[str]:
        card = self._resolve_card_by_shortlink_prefix(ticket_id, include_desc=False)
        if not card:
            raise TrelloNotFoundError(f"Ticket {ticket_id} not found.")
        card_id = str(card.get("id") or "")
        if not card_id:
            raise TrelloNotFoundError(f"Ticket {ticket_id} not found.")

        actions = self._client.list_card_actions(
            card_id,
            limit=max(1, min(100, int(limit) * 3)),
            filter="commentCard",
        )
        entries: List[str] = []
        for action in actions or []:
            action_type = str(action.get("type") or "")
            if action_type != "commentCard":
                continue
            date = str(action.get("date") or "").strip()
            creator = action.get("memberCreator") or {}
            author = str(creator.get("fullName") or creator.get("username") or "").strip()
            data = action.get("data") or {}
            text = str((data.get("text") or "")).rstrip()
            label = f"{author}: " if author else ""
            prefix = f"{date} " if date else ""
            entries.append(f"{prefix}{label}{text}".strip())

        entries = [entry for entry in entries if entry]
        if not entries:
            return []
        entries = list(reversed(entries))
        return entries[-max(1, int(limit)) :]


def _trello_backend_factory(root: Optional[str]) -> TrelloBackend:
    return TrelloBackend(root=root)


register_backend("trello", _trello_backend_factory)
