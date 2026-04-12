"""Tests for installer step resume logic."""

from ankylosaurus.modules.state import InstallState
from ankylosaurus.modules.installer import _build_steps
from ankylosaurus.modules.questionnaire import UserPreferences


def _make_prefs(**overrides):
    defaults = dict(
        usage="general", features=["chat"], disk_budget_gb=30,
        want_gui=False, language="en", battery_mode=False,
    )
    defaults.update(overrides)
    return UserPreferences(**defaults)


def test_build_steps_base():
    prefs = _make_prefs()
    steps = _build_steps(prefs)
    ids = [s[0] for s in steps]
    assert "runtime_installed" in ids
    assert "models_downloaded" in ids
    assert "openwebui_installed" not in ids
    assert "anythingllm_installed" not in ids


def test_build_steps_with_gui():
    prefs = _make_prefs(want_gui=True)
    steps = _build_steps(prefs)
    ids = [s[0] for s in steps]
    assert "openwebui_installed" in ids


def test_build_steps_with_rag():
    prefs = _make_prefs(features=["chat", "rag"])
    steps = _build_steps(prefs)
    ids = [s[0] for s in steps]
    assert "anythingllm_installed" in ids


def test_step_resume_skips_done():
    state = InstallState()
    state.steps_completed = ["runtime_installed", "models_downloaded"]
    assert state.is_done("runtime_installed")
    assert not state.is_done("llm_cli_installed")
