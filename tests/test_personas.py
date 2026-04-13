"""Tests for personas.py — CRUD + built-in templates."""

import json
import os

from ankylosaurus.modules.personas import (
    BUILTIN_PERSONAS,
    install_builtin_personas,
    delete_persona,
)
from ankylosaurus.modules.state import InstallState


def test_builtin_personas_not_empty():
    assert len(BUILTIN_PERSONAS) >= 8


def test_builtin_personas_have_required_fields():
    for name, p in BUILTIN_PERSONAS.items():
        assert "name" in p
        assert "system" in p
        assert "language" in p
        assert p["name"] == name


def test_install_builtin_personas_creates_files(tmp_path, monkeypatch):
    monkeypatch.setattr("ankylosaurus.modules.personas.TEMPLATES_DIR", tmp_path)
    state = InstallState()
    install_builtin_personas(state)

    for name in BUILTIN_PERSONAS:
        path = tmp_path / f"{name}.json"
        assert path.exists(), f"Missing {name}.json"
        data = json.loads(path.read_text())
        assert data["name"] == name

    assert set(state.personas) == set(BUILTIN_PERSONAS.keys())


def test_install_builtin_personas_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr("ankylosaurus.modules.personas.TEMPLATES_DIR", tmp_path)
    state = InstallState()
    install_builtin_personas(state)
    # Write custom content to one file
    custom = tmp_path / "general.json"
    custom.write_text('{"name": "general", "system": "custom", "language": "en"}')
    # Re-install should not overwrite
    install_builtin_personas(state)
    data = json.loads(custom.read_text())
    assert data["system"] == "custom"


def test_delete_builtin_persona_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr("ankylosaurus.modules.personas.TEMPLATES_DIR", tmp_path)
    from rich.console import Console
    console = Console(file=open(os.devnull, "w", encoding="utf-8"))
    state = InstallState(personas=["coder"])
    delete_persona("coder", state, console)
    assert "coder" in state.personas  # should NOT be removed


def test_delete_custom_persona(tmp_path, monkeypatch):
    monkeypatch.setattr("ankylosaurus.modules.personas.TEMPLATES_DIR", tmp_path)
    # Create a custom persona
    path = tmp_path / "my_persona.json"
    path.write_text('{"name": "my_persona", "system": "test", "language": "en"}')

    from rich.console import Console
    console = Console(file=open(os.devnull, "w", encoding="utf-8"))
    state = InstallState(personas=["my_persona"])
    delete_persona("my_persona", state, console)

    assert not path.exists()
    assert "my_persona" not in state.personas


def test_export_persona_msty(tmp_path, monkeypatch):
    monkeypatch.setattr("ankylosaurus.modules.personas.TEMPLATES_DIR", tmp_path)
    from ankylosaurus.modules.personas import export_persona_msty
    path = export_persona_msty("coder", output_dir=tmp_path)
    assert path is not None
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["name"] == "coder"
    assert "systemPrompt" in data
    assert data["systemPrompt"] == BUILTIN_PERSONAS["coder"]["system"]


def test_export_persona_ollama(tmp_path, monkeypatch):
    monkeypatch.setattr("ankylosaurus.modules.personas.TEMPLATES_DIR", tmp_path)
    from ankylosaurus.modules.personas import export_persona_ollama
    path = export_persona_ollama("coder", output_dir=tmp_path)
    assert path is not None
    assert path.exists()
    content = path.read_text()
    assert content.startswith("FROM {}")
    assert "SYSTEM" in content


def test_export_persona_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr("ankylosaurus.modules.personas.TEMPLATES_DIR", tmp_path)
    from ankylosaurus.modules.personas import export_persona_msty
    result = export_persona_msty("nonexistent", output_dir=tmp_path)
    assert result is None


def test_export_persona_custom(tmp_path, monkeypatch):
    monkeypatch.setattr("ankylosaurus.modules.personas.TEMPLATES_DIR", tmp_path)
    # Create a custom persona file
    custom = tmp_path / "my_bot.json"
    custom.write_text('{"name": "my_bot", "system": "You are my bot", "language": "en"}')
    from ankylosaurus.modules.personas import export_persona_msty
    path = export_persona_msty("my_bot", output_dir=tmp_path)
    assert path is not None
    data = json.loads(path.read_text())
    assert data["name"] == "my_bot"
    assert data["systemPrompt"] == "You are my bot"
