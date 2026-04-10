from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, MutableMapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


class TrelloError(RuntimeError):
    pass


class TrelloConfigError(TrelloError):
    pass


class TrelloAuthError(TrelloError):
    pass


class TrelloNotFoundError(TrelloError):
    pass


class TrelloAmbiguousIdError(TrelloError):
    pass


class TrelloApiError(TrelloError):
    def __init__(self, message: str, *, status: Optional[int] = None) -> None:
        super().__init__(message)
        self.status = status


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


def _redact(value: Optional[str]) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 4:
        return "<redacted>"
    return f"{value[:2]}…{value[-2:]}"


@dataclass(frozen=True)
class TrelloCredentials:
    api_key: str
    api_token: str

    @classmethod
    def from_env(cls) -> TrelloCredentials:
        api_key = _env_str("TRELLO_API_KEY")
        api_token = _env_str("TRELLO_API_TOKEN")
        missing: list[str] = []
        if not api_key:
            missing.append("TRELLO_API_KEY")
        if not api_token:
            missing.append("TRELLO_API_TOKEN")
        if missing:
            raise TrelloConfigError(f"Missing Trello credentials: {', '.join(missing)}.")
        return cls(api_key=api_key, api_token=api_token)


class TrelloClient:
    def __init__(
        self,
        *,
        credentials: TrelloCredentials,
        base_url: Optional[str] = None,
        timeout_s: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        self._credentials = credentials
        self._timeout_s = timeout_s
        self._max_retries = max(0, int(max_retries))
        default_base = "https://api.trello.com/1"
        self._base_url = (base_url or _env_str("TRELLO_BASE_URL") or default_base).rstrip("/") + "/"

    def _auth_params(self) -> dict[str, str]:
        return {"key": self._credentials.api_key, "token": self._credentials.api_token}

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        merged: dict[str, Any] = {}
        merged.update(self._auth_params())
        if params:
            merged.update({k: v for k, v in params.items() if v is not None})

        url = urljoin(self._base_url, path.lstrip("/"))
        if merged:
            url = f"{url}?{urlencode(merged, doseq=True)}"

        body_bytes: Optional[bytes] = None
        headers = {"Accept": "application/json"}
        if json_body is not None:
            body_bytes = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        request = Request(url, method=method.upper(), data=body_bytes, headers=headers)

        backoffs = [0.4, 0.9, 1.8]
        attempts = self._max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                with urlopen(request, timeout=self._timeout_s) as resp:
                    payload = resp.read()
                    if not payload:
                        return None
                    content_type = resp.headers.get("Content-Type", "")
                    if "application/json" in content_type:
                        return json.loads(payload.decode("utf-8"))
                    return payload.decode("utf-8", errors="replace")
            except HTTPError as exc:
                status = getattr(exc, "code", None)
                retryable = status in {429, 500, 502, 503, 504}
                if retryable and attempt < attempts - 1:
                    time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                    last_error = exc
                    continue

                try:
                    raw = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    raw = ""

                safe_context = (
                    f"Trello request failed (status={status}). "
                    "Check `TRELLO_API_KEY`, `TRELLO_API_TOKEN`, and Trello board configuration."
                )
                message = safe_context if not raw else safe_context
                if status in {401, 403}:
                    raise TrelloAuthError(safe_context) from exc
                if status == 404:
                    raise TrelloNotFoundError("Trello resource not found.") from exc
                raise TrelloApiError(message, status=status) from exc
            except URLError as exc:
                if attempt < attempts - 1:
                    time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                    last_error = exc
                    continue
                raise TrelloApiError("Trello request failed due to a network error.") from exc

        if last_error:
            raise TrelloApiError("Trello request failed after retries.") from last_error
        raise TrelloApiError("Trello request failed.")

    def get_me(self, *, fields: str = "id,username,fullName") -> dict[str, Any]:
        return self._request("GET", "/members/me", params={"fields": fields})

    def list_boards(
        self,
        *,
        fields: str = "id,name,shortLink,url,closed",
        filter: str = "open",
    ) -> list[dict[str, Any]]:
        return self._request("GET", "/members/me/boards", params={"fields": fields, "filter": filter})

    def get_board_lists(self, board_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/boards/{board_id}/lists", params={"fields": "id,name"})

    def get_board_labels(self, board_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/boards/{board_id}/labels", params={"fields": "name,color"})

    def create_board_label(self, board_id: str, name: str, *, color: str = "green") -> dict[str, Any]:
        return self._request("POST", "/labels", params={"idBoard": board_id, "name": name, "color": color})

    def get_board_members(self, board_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/boards/{board_id}/members", params={"fields": "username,fullName"})

    def list_board_cards(
        self,
        board_id: str,
        *,
        fields: str,
        filter: str = "open",
        include_members: bool = True,
        list_name: Optional[str] = None,
        list_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        params: MutableMapping[str, Any] = {"fields": fields, "filter": filter}
        if include_members:
            params["members"] = "true"
            params["member_fields"] = "username,fullName"
        list_id = (list_id or "").strip() or None
        list_name = (list_name or "").strip() or None
        if list_id and list_name:
            raise ValueError("Specify only one of list_id or list_name.")
        if list_name:
            list_id = self._resolve_list_id_by_name(board_id, list_name)
        if list_id:
            return self._request("GET", f"/lists/{list_id}/cards", params=params)
        return self._request("GET", f"/boards/{board_id}/cards", params=params)

    def _resolve_list_id_by_name(self, board_id: str, list_name: str) -> str:
        name = (list_name or "").strip()
        if not name:
            raise ValueError("List name is required.")
        lists = self.get_board_lists(board_id)
        matches: list[dict[str, Any]] = []
        needle = name.lower()
        for entry in lists or []:
            entry_name = str(entry.get("name") or "").strip()
            if entry_name and entry_name.lower() == needle:
                matches.append(entry)
        if not matches:
            raise TrelloNotFoundError(f"Trello list '{list_name}' not found on board.")
        if len(matches) > 1:
            raise TrelloAmbiguousIdError(f"Trello list '{list_name}' matched multiple lists on board.")
        list_id = str(matches[0].get("id") or "").strip()
        if not list_id:
            raise TrelloNotFoundError(f"Trello list '{list_name}' missing id.")
        return list_id

    def get_card(self, card_id: str, *, fields: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/cards/{card_id}",
            params={"fields": fields, "members": "true", "member_fields": "username,fullName"},
        )

    def create_card(
        self,
        *,
        name: str,
        desc: str,
        list_id: str,
        member_ids: Optional[Iterable[str]] = None,
        label_ids: Optional[Iterable[str]] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"name": name, "desc": desc, "idList": list_id}
        if member_ids:
            params["idMembers"] = ",".join(member_ids)
        if label_ids:
            params["idLabels"] = ",".join(label_ids)
        return self._request("POST", "/cards", params=params)

    def update_card(self, card_id: str, *, fields: Mapping[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/cards/{card_id}", params=dict(fields))

    def add_card_comment(self, card_id: str, text: str) -> dict[str, Any]:
        return self._request("POST", f"/cards/{card_id}/actions/comments", params={"text": text})

    def list_card_actions(
        self,
        card_id: str,
        *,
        limit: int = 50,
        filter: str = "commentCard",
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            f"/cards/{card_id}/actions",
            params={"limit": limit, "filter": filter, "memberCreator_fields": "fullName,username"},
        )
