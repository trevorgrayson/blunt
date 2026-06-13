"""
syndicate.sheets

Publish a directory of CSV/TSV files to Google Sheets, idempotently.

Pure-python (stdlib only) in the spirit of clients/databricks: hand-rolled
``urllib`` against the Google REST APIs rather than the vendored google SDKs.

Model
-----
- Auth is the OAuth *installed-app* flow. ``credentials.json`` is an OAuth
  client (Desktop type). The first run opens a browser for consent and caches
  ``token.json`` (with a refresh token) next to it; later runs just refresh the
  access token via an HTTP POST -- no crypto, so no third-party deps.
- Sheets are created in and owned by *your* Google account.
- Scope is ``drive.file``: the app can only see/manage files it created. That
  is exactly what makes title-based idempotency safe -- a lookup can never
  collide with a sheet you made by hand.

Idempotency
-----------
A directory maps to one spreadsheet titled after the directory; each file maps
to one tab named after the file (sans extension). A single file maps to a
spreadsheet titled after the file, with one tab. Re-publishing finds the
existing spreadsheet by title (among app-created files) and *mirrors* the
source: missing tabs are added, present tabs are cleared and rewritten, and
tabs with no matching file are deleted.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode, urlparse, parse_qs
import urllib.error
import urllib.request


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"

SPREADSHEET_MIME = "application/vnd.google-apps.spreadsheet"

# Google caps sheet (tab) titles at 100 chars.
MAX_TAB_TITLE = 100


# --------------------------------------------------------------------------- #
# HTTP plumbing
# --------------------------------------------------------------------------- #

def _http_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
    form: dict | None = None,
) -> dict:
    """Issue an HTTP request and decode the JSON body.

    ``payload`` is JSON-encoded; ``form`` is urlencoded (for token endpoints).
    """
    headers: dict[str, str] = {}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif form is not None:
        data = urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return json.loads(body.decode("utf-8")) if body else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason} for {url}\n{detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error for {url}: {e.reason}") from None


# --------------------------------------------------------------------------- #
# OAuth installed-app flow
# --------------------------------------------------------------------------- #

@dataclass
class Credentials:
    """A live access token plus the bits needed to refresh and persist it."""

    client_id: str
    client_secret: str
    token: str
    refresh_token: str | None
    token_path: Path

    @property
    def auth_token(self) -> str:
        return self.token


def _load_client_config(credentials_path: Path) -> dict:
    raw = json.loads(credentials_path.read_text())
    # Desktop clients nest under "installed"; web clients under "web".
    config = raw.get("installed") or raw.get("web")
    if not config:
        raise RuntimeError(
            f"{credentials_path} is not an OAuth client file "
            "(expected an 'installed' or 'web' key). Download a Desktop OAuth "
            "client from the Google Cloud console."
        )
    return config


class _CodeCatcher(BaseHTTPRequestHandler):
    """One-shot handler that captures the ?code=... loopback redirect."""

    code: str | None = None

    def do_GET(self):  # noqa: N802 (http.server API)
        params = parse_qs(urlparse(self.path).query)
        _CodeCatcher.code = (params.get("code") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = _CodeCatcher.code is not None
        msg = "Authorized. You can close this tab." if ok else "No code returned."
        self.wfile.write(f"<html><body><h3>{msg}</h3></body></html>".encode())

    def log_message(self, *args):  # silence the default stderr logging
        pass


def _run_consent_flow(config: dict, token_path: Path) -> Credentials:
    """Open the browser, capture the auth code on localhost, exchange for tokens."""
    server = HTTPServer(("127.0.0.1", 0), _CodeCatcher)
    redirect_uri = f"http://127.0.0.1:{server.server_address[1]}/"

    auth_url = AUTH_URI + "?" + urlencode(
        {
            "client_id": config["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    print("Opening browser for Google authorization...", file=sys.stderr)
    print(f"If it does not open, visit:\n{auth_url}", file=sys.stderr)
    webbrowser.open(auth_url)

    _CodeCatcher.code = None
    server.handle_request()  # blocks until the redirect hits
    server.server_close()
    if not _CodeCatcher.code:
        raise RuntimeError("Authorization failed: no code received from Google.")

    tokens = _http_json(
        "POST",
        TOKEN_URI,
        form={
            "code": _CodeCatcher.code,
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    creds = Credentials(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        token_path=token_path,
    )
    _save_token(creds)
    return creds


def _save_token(creds: Credentials) -> None:
    creds.token_path.write_text(
        json.dumps(
            {
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
            },
            indent=2,
        )
    )
    # token.json holds a refresh token; keep it owner-only.
    try:
        os.chmod(creds.token_path, 0o600)
    except OSError:
        pass


def _refresh(creds: Credentials) -> Credentials:
    if not creds.refresh_token:
        raise RuntimeError("No refresh token available; re-run the consent flow.")
    tokens = _http_json(
        "POST",
        TOKEN_URI,
        form={
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "refresh_token": creds.refresh_token,
            "grant_type": "refresh_token",
        },
    )
    creds.token = tokens["access_token"]
    _save_token(creds)
    return creds


def load_credentials(credentials_path: str | Path, token_path: str | Path | None = None) -> Credentials:
    """Return usable Credentials, running the consent flow on first use.

    ``token.json`` is cached next to ``credentials.json`` unless ``token_path``
    overrides it.
    """
    credentials_path = Path(credentials_path).expanduser()
    if not credentials_path.exists():
        raise FileNotFoundError(f"credentials file not found: {credentials_path}")
    config = _load_client_config(credentials_path)
    token_path = (
        Path(token_path).expanduser()
        if token_path
        else credentials_path.with_name("token.json")
    )

    if token_path.exists():
        cached = json.loads(token_path.read_text())
        creds = Credentials(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            token=cached.get("access_token", ""),
            refresh_token=cached.get("refresh_token"),
            token_path=token_path,
        )
        # Refresh up front so the access token is fresh for this run.
        return _refresh(creds)

    return _run_consent_flow(config, token_path)


def _request(creds: Credentials, method: str, url: str, payload: dict | None = None) -> dict:
    """API call that transparently refreshes the token once on 401."""
    try:
        return _http_json(method, url, token=creds.auth_token, payload=payload)
    except RuntimeError as e:
        if "HTTP 401" in str(e):
            _refresh(creds)
            return _http_json(method, url, token=creds.auth_token, payload=payload)
        raise


# --------------------------------------------------------------------------- #
# Reading source files
# --------------------------------------------------------------------------- #

def _delimiter_for(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".tsv":
        return "\t"
    if ext == ".csv":
        return ","
    # Unknown extension: sniff a sample, fall back to comma.
    sample = path.read_text(errors="replace")[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
    except csv.Error:
        return ","


def read_table(path: Path) -> list[list[str]]:
    """Read a CSV/TSV file into a 2D list of strings."""
    delimiter = _delimiter_for(path)
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as fh:
        return [row for row in csv.reader(fh, delimiter=delimiter)]


def _tab_title(path: Path) -> str:
    return path.stem[:MAX_TAB_TITLE] or "Sheet1"


def collect_sources(path: str | Path) -> tuple[str, list[Path]]:
    """Resolve the input into (spreadsheet_title, ordered source files).

    A directory -> titled after the directory, one file per tab.
    A single file -> titled after the file, one tab.
    """
    path = Path(path).expanduser()
    if path.is_dir():
        files = sorted(
            p for p in path.iterdir()
            if p.is_file() and p.suffix.lower() in (".csv", ".tsv")
        )
        if not files:
            raise RuntimeError(f"No .csv or .tsv files found in {path}")
        return path.resolve().name, files
    if path.is_file():
        return path.stem, [path]
    raise FileNotFoundError(f"not a file or directory: {path}")


# --------------------------------------------------------------------------- #
# Drive lookup + Sheets writes
# --------------------------------------------------------------------------- #

def find_spreadsheet(creds: Credentials, title: str, folder_id: str | None = None) -> str | None:
    """Return the id of an app-created spreadsheet with this exact title, if any.

    When ``folder_id`` is given the match is scoped to that Drive folder, so the
    same title can live independently under different folders.
    """
    # drive.file scope only surfaces files this client created -> safe match.
    q = (
        f"name = '{title.replace(chr(39), chr(92) + chr(39))}' and "
        f"mimeType = '{SPREADSHEET_MIME}' and trashed = false"
    )
    if folder_id:
        q += f" and '{folder_id}' in parents"
    params = urlencode({"q": q, "fields": "files(id,name)", "spaces": "drive"})
    result = _request(creds, "GET", f"{DRIVE_FILES}?{params}")
    files = result.get("files", [])
    return files[0]["id"] if files else None


def _move_to_folder(creds: Credentials, file_id: str, folder_id: str) -> None:
    """Reparent a file into ``folder_id`` (Sheets are created in My Drive root)."""
    params = urlencode(
        {"addParents": folder_id, "removeParents": "root", "fields": "id,parents"}
    )
    _request(creds, "PATCH", f"{DRIVE_FILES}/{file_id}?{params}", payload={})


def create_spreadsheet(
    creds: Credentials, title: str, tab_titles: list[str], folder_id: str | None = None
) -> str:
    body = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": t}} for t in tab_titles],
    }
    result = _request(creds, "POST", SHEETS_API, payload=body)
    spreadsheet_id = result["spreadsheetId"]
    if folder_id:
        _move_to_folder(creds, spreadsheet_id, folder_id)
    return spreadsheet_id


def _existing_tabs(creds: Credentials, spreadsheet_id: str) -> dict[str, int]:
    """Map current tab title -> sheetId."""
    params = urlencode({"fields": "sheets(properties(sheetId,title))"})
    meta = _request(creds, "GET", f"{SHEETS_API}/{spreadsheet_id}?{params}")
    return {
        s["properties"]["title"]: s["properties"]["sheetId"]
        for s in meta.get("sheets", [])
    }


def reconcile_tabs(
    creds: Credentials,
    spreadsheet_id: str,
    desired_titles: list[str],
) -> None:
    """Mirror the tab set: add missing tabs, delete tabs with no source file.

    Adds happen before deletes so we never transiently drop below Google's
    one-sheet-per-spreadsheet minimum.
    """
    existing = _existing_tabs(creds, spreadsheet_id)
    desired = set(desired_titles)

    requests: list[dict] = []
    for title in desired_titles:
        if title not in existing:
            requests.append({"addSheet": {"properties": {"title": title}}})
    for title, sheet_id in existing.items():
        if title not in desired:
            requests.append({"deleteSheet": {"sheetId": sheet_id}})

    if requests:
        _request(
            creds,
            "POST",
            f"{SHEETS_API}/{spreadsheet_id}:batchUpdate",
            payload={"requests": requests},
        )


def _quote_range(tab_title: str) -> str:
    # Single-quote the tab and escape embedded quotes for A1 notation.
    return "'" + tab_title.replace("'", "''") + "'"


def write_tab(creds: Credentials, spreadsheet_id: str, tab_title: str, values: list[list[str]]) -> None:
    """Clear the tab then write values, so stale rows never linger."""
    rng = _quote_range(tab_title)
    _request(
        creds,
        "POST",
        f"{SHEETS_API}/{spreadsheet_id}/values/{urllib.parse.quote(rng)}:clear",
        payload={},
    )
    if not values:
        return
    params = urlencode({"valueInputOption": "USER_ENTERED"})
    _request(
        creds,
        "PUT",
        f"{SHEETS_API}/{spreadsheet_id}/values/{urllib.parse.quote(rng)}?{params}",
        payload={"range": rng, "majorDimension": "ROWS", "values": values},
    )


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def publish(
    creds: Credentials,
    path: str | Path,
    *,
    folder_id: str | None = None,
    stream=print,
) -> str:
    """Publish a file or directory to a single spreadsheet. Returns its URL.

    ``folder_id`` is an optional Drive folder id; when set the spreadsheet is
    created in (and looked up within) that folder rather than My Drive root.
    """
    title, files = collect_sources(path)
    tab_titles = [_tab_title(f) for f in files]

    spreadsheet_id = find_spreadsheet(creds, title, folder_id)
    if spreadsheet_id is None:
        spreadsheet_id = create_spreadsheet(creds, title, tab_titles, folder_id)
        stream(f"created spreadsheet '{title}' ({spreadsheet_id})")
    else:
        reconcile_tabs(creds, spreadsheet_id, tab_titles)
        stream(f"reusing spreadsheet '{title}' ({spreadsheet_id})")

    for src, tab in zip(files, tab_titles):
        values = read_table(src)
        write_tab(creds, spreadsheet_id, tab, values)
        rows = max(0, len(values) - 1)
        stream(f"  {src.name} -> tab '{tab}' ({rows} data rows)")

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
