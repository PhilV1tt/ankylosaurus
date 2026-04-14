"""Tests for personas.py - catalog, selection, CRUD + templates."""

import json
import os

from ankylosaurus.modules.personas import (
    BUILTIN_PERSONAS,
    PERSONA_CATALOG,
    PersonaTemplate,
    UserProfile,
    select_personas,
    instantiate_persona,
    generate_personas,
    install_builtin_personas,
    delete_persona,
)
from ankylosaurus.modules.state import InstallState


# --- Catalog structure ---

def test_catalog_not_empty():
    assert len(PERSONA_CATALOG) >= 15


def test_catalog_entries_are_templates():
    for t in PERSONA_CATALOG:
        assert isinstance(t, PersonaTemplate)
        assert t.id
        assert t.category in ("learning", "productivity", "domain", "system")
        assert t.model_tier in ("reasoning", "fast", "uncensored")
        assert "{lang_instruction}" in t.system_tpl or t.id == "general-uncensored"


def test_catalog_ids_unique():
    ids = [t.id for t in PERSONA_CATALOG]
    assert len(ids) == len(set(ids))


# --- Selection ---

def test_select_default_only():
    profile = UserProfile()  # no domains, no use_cases
    selected = select_personas(profile)
    ids = {t.id for t in selected}
    # Should include default_active personas
    assert "general" in ids
    assert "translator" in ids
    assert "summarizer" in ids
    # Should NOT include domain-specific
    assert "coach-sport" not in ids
    assert "music-teacher" not in ids


def test_select_with_domains():
    profile = UserProfile(domains=["music", "sports"])
    selected = select_personas(profile)
    ids = {t.id for t in selected}
    assert "music-teacher" in ids
    assert "coach-sport" in ids


def test_select_student():
    profile = UserProfile(occupation="student", use_cases=["study", "code"])
    selected = select_personas(profile)
    ids = {t.id for t in selected}
    assert "tutor-science" in ids
    assert "tutor-code" in ids
    assert "study-buddy" in ids


# --- Instantiation ---

def test_instantiate_french():
    tpl = PERSONA_CATALOG[0]  # tutor-science
    profile = UserProfile(primary_language="fr")
    persona = instantiate_persona(tpl, profile)
    assert persona["name"] == tpl.id
    assert "francais" in persona["system"]
    assert persona["language"] == "fr"


def test_instantiate_english():
    tpl = PERSONA_CATALOG[0]
    profile = UserProfile(primary_language="en")
    persona = instantiate_persona(tpl, profile)
    assert "Respond in English" in persona["system"]


def test_instantiate_with_model_map():
    tpl = PERSONA_CATALOG[0]  # reasoning tier
    profile = UserProfile(primary_language="en")
    model_map = {"reasoning": "my-model", "fast": "my-fast"}
    persona = instantiate_persona(tpl, profile, model_map)
    assert persona["model"] == "my-model"


# --- Generate ---

def test_generate_returns_dict():
    profile = UserProfile(occupation="developer", use_cases=["code"])
    result = generate_personas(profile)
    assert isinstance(result, dict)
    assert "general" in result  # default_active
    for name, p in result.items():
        assert p["name"] == name
        assert "system" in p
        assert "language" in p


# --- Backward compat: BUILTIN_PERSONAS ---

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
    state = InstallState(personas=["tutor-code"])
    delete_persona("tutor-code", state, console)
    assert "tutor-code" in state.personas  # should NOT be removed


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
    path = export_persona_msty("tutor-code", output_dir=tmp_path)
    assert path is not None
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["name"] == "tutor-code"
    assert "systemPrompt" in data
    assert data["systemPrompt"] == BUILTIN_PERSONAS["tutor-code"]["system"]


def test_export_persona_ollama(tmp_path, monkeypatch):
    monkeypatch.setattr("ankylosaurus.modules.personas.TEMPLATES_DIR", tmp_path)
    from ankylosaurus.modules.personas import export_persona_ollama
    path = export_persona_ollama("tutor-code", output_dir=tmp_path)
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
