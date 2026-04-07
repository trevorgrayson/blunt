from __future__ import annotations

import sys
from types import SimpleNamespace

import tkts.__main__ as main_mod


def test_cli_exec_uses_default_agent(monkeypatch) -> None:
    captured = {}

    def _fake_run(args, check=False):
        captured["args"] = args
        captured["check"] = check
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(main_mod.subprocess, "run", _fake_run)
    monkeypatch.setattr(sys, "argv", ["tkts", "exec"])

    assert main_mod.main() == 0

    assert captured["args"] == [
        "codex",
        "exec",
        "--sandbox",
        "workspace-write",
        main_mod._EXEC_PROMPT,
    ]
    assert captured["check"] is False


def test_cli_exec_accepts_custom_agent(monkeypatch) -> None:
    captured = {}

    def _fake_run(args, check=False):
        captured["args"] = args
        captured["check"] = check
        return SimpleNamespace(returncode=3)

    monkeypatch.setattr(main_mod.subprocess, "run", _fake_run)
    monkeypatch.setattr(sys, "argv", ["tkts", "exec", "agent-bin", "--flag"])

    assert main_mod.main() == 3
    assert captured["args"] == ["agent-bin", "--flag", main_mod._EXEC_PROMPT]
    assert captured["check"] is False
