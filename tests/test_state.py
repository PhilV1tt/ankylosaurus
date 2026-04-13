"""Tests for state persistence."""


from ankylosaurus.modules.state import InstallState, save_state, load_state


def test_roundtrip(tmp_path, monkeypatch):
    test_file = tmp_path / "state.json"
    monkeypatch.setattr("ankylosaurus.modules.state.STATE_FILE", test_file)

    state = InstallState(runtime="ollama", runtime_version="0.5.0")
    state.mark_step("runtime_installed")
    save_state(state)

    loaded = load_state()
    assert loaded.runtime == "ollama"
    assert loaded.is_done("runtime_installed")
    assert not loaded.is_done("models_downloaded")


def test_mark_step_idempotent(tmp_path, monkeypatch):
    test_file = tmp_path / "state.json"
    monkeypatch.setattr("ankylosaurus.modules.state.STATE_FILE", test_file)

    state = InstallState()
    state.mark_step("step1")
    state.mark_step("step1")
    assert state.steps_completed.count("step1") == 1
