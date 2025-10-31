"""
Terraform Cloud/Enterprise workspace build status checker.

- Uses only Python standard libraries (urllib, json, os, argparse).
- Works with Terraform Cloud (default) or Terraform Enterprise (custom base URL).
- Fetches the latest run for a workspace and reports its status and metadata.

Usage (CLI):

  python tfc_status.py --org YOUR_ORG --workspace YOUR_WS \
    [--base-url https://app.terraform.io] [--token YOUR_TOKEN]

Defaults:
- Token is read from $TFC_TOKEN if --token is not provided.
- Base URL is read from $TFC_BASE_URL if --base-url is not provided.

Exit codes:
  0 -> success terminal state (applied/planned_and_finished)
  1 -> failure terminal state (errored/canceled/discarded)
  2 -> non-terminal (still running / pending) or unknown

Programmatic usage:
  from tfc_status import check_workspace_status
  info = check_workspace_status(org, workspace, token)
  print(info["status"], info["run_url"]) 
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Dict, Optional
from urllib import request, error, parse

TFC_API_MEDIA = "application/vnd.api+json"
DEFAULT_BASE_URL = "https://app.terraform.io"

SUCCESS_TERMINAL = {"applied", "planned_and_finished"}
FAILURE_TERMINAL = {"errored", "canceled", "discarded"}


@dataclass
class RunInfo:
    run_id: str
    status: str
    run_url: str
    workspace_id: str
    workspace_name: str
    organization: str
    triggered_by: Optional[str]
    vcs_sha: Optional[str]
    vcs_branch: Optional[str]
    message: Optional[str]


class TFCError(RuntimeError):
    pass


def _build_url(base_url: str, path: str, query: Optional[Dict[str, str]] = None) -> str:
    base = base_url.rstrip("/")
    url = f"{base}{path}"
    if query:
        url += "?" + parse.urlencode(query)
    return url


def _api_get(url: str, token: str) -> Dict:
    req = request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", TFC_API_MEDIA)
    req.add_header("Accept", TFC_API_MEDIA)

    try:
        with request.urlopen(req, timeout=30) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            payload = resp.read().decode(charset)
            return json.loads(payload)
    except error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = "<no body>"
        raise TFCError(f"HTTP {e.code} for {url}: {detail}") from e
    except error.URLError as e:
        raise TFCError(f"Network error for {url}: {e}") from e


def _get_workspace_with_latest_run(org: str, workspace: str, token: str, base_url: str) -> Dict:
    path = f"/api/v2/organizations/{parse.quote(org)}/workspaces/{parse.quote(workspace)}"
    url = _build_url(base_url, path, {"include": "latest-run"})
    return _api_get(url, token)


def _get_latest_run_via_workspace_runs(workspace_id: str, token: str, base_url: str) -> Dict:
    path = f"/api/v2/workspaces/{parse.quote(workspace_id)}/runs"
    url = _build_url(base_url, path, {"page[size]": "1", "include": "created-by,vcs-repo"})
    return _api_get(url, token)


def get_latest_run_info(org: str, workspace: str, token: str, base_url: str = DEFAULT_BASE_URL) -> RunInfo:
    ws_resp = _get_workspace_with_latest_run(org, workspace, token, base_url)

    if "data" not in ws_resp:
        raise TFCError("Malformed response: missing 'data'")

    ws_data = ws_resp["data"]
    workspace_id = ws_data.get("id")
    if not workspace_id:
        raise TFCError("Workspace ID not found in response")

    run_obj: Optional[Dict] = None
    included = ws_resp.get("included", []) or []
    for inc in included:
        if inc.get("type") == "runs":
            run_obj = inc
            break

    if run_obj is None:
        runs_resp = _get_latest_run_via_workspace_runs(workspace_id, token, base_url)
        runs = runs_resp.get("data", [])
        if not runs:
            raise TFCError("No runs found for workspace")
        run_obj = runs[0]
        included = runs_resp.get("included", []) or []

    run_id = run_obj.get("id")
    attrs = run_obj.get("attributes", {})
    status = attrs.get("status", "unknown")
    message = attrs.get("message", None)

    triggered_by = None
    vcs_sha = None
    vcs_branch = None

    for inc in included:
        if inc.get("type") == "users" and inc.get("id") == run_obj.get("relationships", {}).get("created-by", {}).get("data", {}).get("id"):
            triggered_by = inc.get("attributes", {}).get("username")
        if inc.get("type") == "vcs-repos":
            vcs_attrs = inc.get("attributes", {})
            vcs_sha = vcs_attrs.get("commit-sha")
            vcs_branch = vcs_attrs.get("branch")

    human_run_url = (
        f"{base_url.rstrip('/')}/app/{parse.quote(org)}/workspaces/"
        f"{parse.quote(workspace)}/runs/{parse.quote(run_id)}"
    )

    return RunInfo(
        run_id=run_id,
        status=status,
        run_url=human_run_url,
        workspace_id=workspace_id,
        workspace_name=workspace,
        organization=org,
        triggered_by=triggered_by,
        vcs_sha=vcs_sha,
        vcs_branch=vcs_branch,
        message=message,
    )


def check_workspace_status(org: str, workspace: str, token: Optional[str] = None, base_url: Optional[str] = None) -> Dict[str, object]:
    if token is None:
        token = os.getenv("TFC_TOKEN")
    if not token:
        raise TFCError("Terraform API token not provided. Use --token or set $TFC_TOKEN.")

    if base_url is None:
        base_url = os.getenv("TFC_BASE_URL", DEFAULT_BASE_URL)

    info = get_latest_run_info(org, workspace, token, base_url=base_url)
    status = info.status
    is_success = status in SUCCESS_TERMINAL
    is_failed = status in FAILURE_TERMINAL
    is_terminal = is_success or is_failed

    return {
        "organization": info.organization,
        "workspace": info.workspace_name,
        "workspace_id": info.workspace_id,
        "status": status,
        "run_id": info.run_id,
        "run_url": info.run_url,
        "triggered_by": info.triggered_by,
        "vcs_sha": info.vcs_sha,
        "vcs_branch": info.vcs_branch,
        "message": info.message,
        "is_success": is_success,
        "is_failed": is_failed,
        "is_terminal": is_terminal,
    }


def _exit_code_for_status(status: str) -> int:
    if status in SUCCESS_TERMINAL:
        return 0
    if status in FAILURE_TERMINAL:
        return 1
    return 2


def _print_human_readable(result: Dict[str, object]) -> None:
    print("\nTerraform Workspace Status:")
    print("=" * 40)
    print(f"Organization:  {result['organization']}")
    print(f"Workspace:     {result['workspace']}")
    print(f"Status:        {result['status']}")
    print(f"Run URL:       {result['run_url']}")

    if result.get("triggered_by"):
        print(f"Triggered by:  {result['triggered_by']}")
    if result.get("vcs_branch"):
        print(f"Branch:        {result['vcs_branch']}")
    if result.get("vcs_sha"):
        print(f"Commit SHA:    {result['vcs_sha']}")
    if result.get("message"):
        print(f"Message:       {result['message']}")

    if result["is_success"]:
        print("✅ Run completed successfully.")
    elif result["is_failed"]:
        print("❌ Run failed.")
    elif not result["is_terminal"]:
        print("⏳ Run still in progress or pending.")
    print("=" * 40 + "\n")


def _main() -> int:
    parser = argparse.ArgumentParser(description="Check Terraform workspace build status")
    parser.add_argument("--org", required=True, help="Terraform organization name")
    parser.add_argument("--workspace", required=True, help="Terraform workspace name")
    parser.add_argument("--token", help="Terraform API token (or set $TFC_TOKEN)")
    parser.add_argument("--base-url", dest="base_url", help="Terraform base URL (or set $TFC_BASE_URL)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human readable text")

    args = parser.parse_args()

    try:
        result = check_workspace_status(
            org=args.org,
            workspace=args.workspace,
            token=args.token,
            base_url=args.base_url,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            _print_human_readable(result)
        return _exit_code_for_status(result["status"])
    except TFCError as e:
        print(json.dumps({"error": str(e)}))
        return 2
