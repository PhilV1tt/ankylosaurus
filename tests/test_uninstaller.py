"""Tests for uninstaller.py — alias removal logic."""

import os
from pathlib import Path

from ankylosaurus.modules.uninstaller import _remove_aliases
from ankylosaurus.modules.state import InstallState


def test_remove_aliases_from_zshrc(tmp_path, monkeypatch):
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text(
        "# existing config\n"
        "export PATH=/usr/bin\n"
        "\n# === ANKYLOSAURUS ===\n"
        'alias q="llm"\n'
        "# === END ANKYLOSAURUS ===\n"
        "# more config\n"
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    from rich.console import Console
    console = Console(file=open(os.devnull, "w", encoding="utf-8"))
    state = InstallState()
    _remove_aliases(state, console)

    content = zshrc.read_text()
    assert "ANKYLOSAURUS" not in content
    assert "existing config" in content
    assert "more config" in content


def test_remove_aliases_no_marker(tmp_path, monkeypatch):
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("# just config\n")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    from rich.console import Console
    console = Console(file=open(os.devnull, "w", encoding="utf-8"))
    state = InstallState()
    _remove_aliases(state, console)

    assert zshrc.read_text() == "# just config\n"
