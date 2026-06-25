#!/usr/bin/env python3
"""
Publish CSV/TSV files to Google Sheets, idempotently.

    python -m syndicate.sheets PATH [--credentials credentials.json] [--folder DRIVE_FOLDER_ID]

PATH is a single .csv/.tsv file (-> one spreadsheet, one tab) or a directory
of them (-> one spreadsheet, one tab per file). Re-running mirrors the source.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable

from . import load_credentials, publish


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m syndicate.sheets",
        description="Publish a CSV/TSV file or directory to Google Sheets (idempotent).",
    )
    parser.add_argument("path", help="A .csv/.tsv file, or a directory of them.")
    parser.add_argument(
        "--credentials",
        default=os.getenv("GOOGLE_CREDENTIALS", "~/.gcloud/credentials.json"),
        help="OAuth client file (defaults to $GOOGLE_CREDENTIALS or ~/.gcloud/credentials.json).",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GOOGLE_TOKEN"),
        help="Where to cache the OAuth token (defaults to token.json next to --credentials).",
    )
    parser.add_argument(
        "--folder",
        default=os.getenv("GOOGLE_DRIVE_FOLDER"),
        help="Drive folder id to create/sync the spreadsheet in "
        "(defaults to $GOOGLE_DRIVE_FOLDER, else My Drive root).",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Override the spreadsheet title (instead of deriving it from the path).",
    )
    parser.add_argument(
        "--name-prefix",
        default=None,
        dest="name_prefix",
        help="Prepend a prefix to the derived spreadsheet title.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        creds = load_credentials(args.credentials, args.token)
        url = publish(creds, args.path, folder_id=args.folder, name=args.name, name_prefix=args.name_prefix)
    except (RuntimeError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
