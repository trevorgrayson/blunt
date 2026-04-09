from __future__ import annotations

import os
import sys
import types

import pytest

from tkts.__main__ import main


def _run_cli(args: list[str], tmp_path: os.PathLike[str], monkeypatch) -> int:
    monkeypatch.setenv("TKTS_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["tkts", *args])
    return main()


def test_cli_tui_watch_defaults_to_5_seconds(tmp_path: os.PathLike[str], monkeypatch) -> None:
    called: dict[str, float | None] = {"watch": None}

    mod = types.ModuleType("tkts.ncurses_tui")

    def run_tui(*, watch=None) -> int:  # type: ignore[no-untyped-def]
        called["watch"] = watch
        return 0

    mod.run_tui = run_tui  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tkts.ncurses_tui", mod)

    assert _run_cli(["tui", "--watch"], tmp_path, monkeypatch) == 0
    assert called["watch"] == 5.0


def test_cli_tui_watch_accepts_custom_seconds(tmp_path: os.PathLike[str], monkeypatch) -> None:
    called: dict[str, float | None] = {"watch": None}

    mod = types.ModuleType("tkts.ncurses_tui")

    def run_tui(*, watch=None) -> int:  # type: ignore[no-untyped-def]
        called["watch"] = watch
        return 0

    mod.run_tui = run_tui  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tkts.ncurses_tui", mod)

    assert _run_cli(["tui", "--watch", "2.5"], tmp_path, monkeypatch) == 0
    assert called["watch"] == 2.5


def test_cli_tui_watch_rejects_non_positive(tmp_path: os.PathLike[str], monkeypatch) -> None:
    mod = types.ModuleType("tkts.ncurses_tui")
    mod.run_tui = lambda *, watch=None: 0  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tkts.ncurses_tui", mod)

    with pytest.raises(SystemExit, match="--watch must be > 0 seconds\\."):
        _run_cli(["tui", "--watch", "0"], tmp_path, monkeypatch)

