from __future__ import annotations

from argparse import ArgumentParser
import os
import sys
from typing import Iterable

from tkts.trello.client import TrelloClient, TrelloCredentials, TrelloError


def _env_str(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _render_boards(boards: Iterable[dict]) -> None:
    for board in boards:
        name = str(board.get("name") or "").strip()
        board_id = str(board.get("id") or "").strip()
        short_link = str(board.get("shortLink") or "").strip()
        url = str(board.get("url") or "").strip()
        closed = board.get("closed") is True
        status = "closed" if closed else "open"
        summary = f"{name} | id={board_id} | shortLink={short_link} | {status}"
        if url:
            summary = f"{summary} | url={url}"
        print(summary)


def _render_cards(cards: Iterable[dict]) -> None:
    for card in cards:
        name = str(card.get("name") or "").strip()
        card_id = str(card.get("id") or "").strip()
        short_link = str(card.get("shortLink") or "").strip()
        url = str(card.get("url") or "").strip()
        summary = f"{name} | id={card_id} | shortLink={short_link}"
        if url:
            summary = f"{summary} | url={url}"
        print(summary)


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(
        prog="python -m tkts.trello",
        description="Test Trello connectivity, list boards, or list cards by Trello list name.",
    )
    parser.add_argument(
        "--include-closed",
        action="store_true",
        help="Include closed boards or archived cards in the listing.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of boards or cards to print.",
    )
    parser.add_argument(
        "--board-id",
        default=None,
        help="Trello board id (defaults to TRELLO_BOARD_ID).",
    )
    parser.add_argument(
        "--list-name",
        default=None,
        help="If set, list cards from the Trello list with this name.",
    )
    args = parser.parse_args(argv)

    try:
        credentials = TrelloCredentials.from_env()
        client = TrelloClient(credentials=credentials)
        me = client.get_me(fields="id,username,fullName")
        identity = str(me.get("fullName") or me.get("username") or me.get("id") or "unknown")
        print(f"Connected to Trello as {identity}.")

        filter_value = "all" if args.include_closed else "open"
        if args.list_name:
            board_id = args.board_id or _env_str("TRELLO_BOARD_ID")
            if not board_id:
                print("Missing board id. Set --board-id or TRELLO_BOARD_ID.", file=sys.stderr)
                return 2
            cards = client.list_board_cards(
                board_id,
                fields="id,name,shortLink,url",
                filter=filter_value,
                include_members=False,
                list_name=args.list_name,
            ) or []
            if args.limit is not None and args.limit >= 0:
                cards = cards[: args.limit]
            if not cards:
                print("No cards found.")
                return 0
            print("Cards:")
            _render_cards(cards)
            return 0

        boards = client.list_boards(filter=filter_value, fields="id,name,shortLink,url,closed") or []
        if args.limit is not None and args.limit >= 0:
            boards = boards[: args.limit]
        if not boards:
            print("No boards found.")
            return 0

        print("Boards:")
        _render_boards(boards)
        return 0
    except TrelloError as exc:
        print(f"Trello error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
