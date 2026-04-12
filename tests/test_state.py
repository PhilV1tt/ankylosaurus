"""Tests for state persistence."""


from modules.state import InstallState, save_state, load_state


def test_roundtrip(tmp_path, monkeypatch):
    test_file = tmp_path / "state.json"
    monkeypatch.setattr("modules.state.STATE_FILE", test_file)

    state = InstallState(runtime="lm-studio", runtime_version="0.4.10")
    state.mark_step("runtime_installed")
    save_state(state)

    loaded = load_state()
    assert loaded.runtime == "lm-studio"
    assert loaded.is_done("runtime_installed")
    assert not loaded.is_done("models_downloaded")


def test_mark_step_idempotent(tmp_path, monkeypatch):
    test_file = tmp_path / "state.json"
    monkeypatch.setattr("modules.state.STATE_FILE", test_file)

    state = InstallState()
    state.mark_step("step1")
    state.mark_step("step1")
    assert state.steps_completed.count("step1") == 1
