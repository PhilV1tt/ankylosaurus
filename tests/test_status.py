"""Tests for status.py — dashboard display."""

import os

from ankylosaurus.modules.status import show_status
from rich.console import Console


def test_show_status_no_state_no_crash(monkeypatch):
    monkeypatch.setattr("ankylosaurus.modules.status.state_exists", lambda: False)
    console = Console(file=open(os.devnull, "w", encoding="utf-8"))
    show_status(console)  # should not raise


def test_show_status_with_state_no_crash(monkeypatch):
    from ankylosaurus.modules.state import InstallState
    state = InstallState(
        runtime="ollama",
        runtime_version="0.5.0",
        tools={"llm_cli": True, "fabric": False},
        personas=["coder", "tutor"],
        hardware={"os": "macOS", "cpu": "M5", "gpu": "Apple M5", "ram_gb": 24},
        models=[{"role": "chat", "repo_id": "test/model", "size_gb": 4.0}],
    )
    monkeypatch.setattr("ankylosaurus.modules.status.state_exists", lambda: True)
    monkeypatch.setattr("ankylosaurus.modules.status.load_state", lambda: state)
    console = Console(file=open(os.devnull, "w", encoding="utf-8"))
    show_status(console)  # should not raise
