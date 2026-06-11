"""
Syndicate

multi-publish status updates, news, or notifications across mediums.

https://github.com/sphinx-contrib/confluencebuilder
"""

from __future__ import annotations

import argparse
from typing import Iterable

from syndicate.sheets.__main__ import main as sheets_main


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m syndicate",
        description="Syndicate content across supported destinations.",
    )
    subparsers = parser.add_subparsers(dest="verb", required=True)

    sheets_parser = subparsers.add_parser(
        "sheets",
        help="Publish CSV/TSV sources to Google Sheets.",
    )
    sheets_parser.add_argument("args", nargs=argparse.REMAINDER)

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.verb == "sheets":
        forwarded = args.args
        if forwarded and forwarded[0] == "--":
            forwarded = forwarded[1:]
        return sheets_main(forwarded)

    parser.error(f"unknown verb: {args.verb}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
