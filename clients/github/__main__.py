import os
import argparse

from . import GithubPRClient

GITHUB_USERNAME = os.getenv("GITHUB_USER", "trevorgrayson-earnin")
GITHUB_TOKEN = os.getenv("GH_TOKEN", os.getenv("GITHUB_TOKEN"))


def _format_checks(checks: dict) -> str:
    state = checks.get("state", "unknown")
    counts = checks.get("counts") or {}
    if counts:
        counts_text = ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
    else:
        counts_text = "none"
    return f"{state} ({counts_text})"


def cmd_prs(args: argparse.Namespace) -> int:
    client = GithubPRClient(args.token, args.user)
    prs = client.load_prs()
    for pr in prs:
        checks = pr.get("checks") or {}
        print(pr["title"])
        print(f"  url: {pr['url']}")
        print(f"  status: {pr['status']}")
        print(f"  review: {pr['review_status']}")
        print(f"  checks: {_format_checks(checks)}")
        print(f"  open comments: {pr.get('open_comment_count', 0)}")
        for comment in pr.get("open_comments", []):
            print(f"    - {comment}")
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    client = GithubPRClient(args.token, args.user)
    prs = client.load_prs()
    for pr in prs:
        print(pr["full_text"])
        for item in pr.get("action_items", []):
            print(f"  - {item}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GitHub PR helper (lists open PRs and action items).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m clients.github prs\n"
            "  python -m clients.github summary\n"
            "  python -m clients.github prs --user octocat\n"
            "  python -m clients.github prs --token $GH_TOKEN\n"
        ),
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help="Command to run.",
    )

    prs_parser = subparsers.add_parser(
        "prs",
        help="Show detailed status for open PRs (checks + comments).",
        description=(
            "Show detailed status for open PRs, including checks and open comments."
        ),
    )
    prs_parser.add_argument(
        "--user",
        default=GITHUB_USERNAME,
        help="GitHub username to query (default: %(default)s).",
    )
    prs_parser.add_argument(
        "--token",
        default=GITHUB_TOKEN,
        help="GitHub token (default: $GH_TOKEN or $GITHUB_TOKEN).",
    )
    prs_parser.set_defaults(func=cmd_prs)

    summary_parser = subparsers.add_parser(
        "summary",
        help="List open PRs with action items (summary view).",
        description=(
            "List open PRs for a user and print action items derived from reviews/comments."
        ),
    )
    summary_parser.add_argument(
        "--user",
        default=GITHUB_USERNAME,
        help="GitHub username to query (default: %(default)s).",
    )
    summary_parser.add_argument(
        "--token",
        default=GITHUB_TOKEN,
        help="GitHub token (default: $GH_TOKEN or $GITHUB_TOKEN).",
    )
    summary_parser.set_defaults(func=cmd_summary)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
