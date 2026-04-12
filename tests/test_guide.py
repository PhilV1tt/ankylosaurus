"""Tests for guide.py — personalized GUIDE.md generation."""

from ankylosaurus.modules.guide import save_guide
from ankylosaurus.modules.state import InstallState


def test_guide_header(tmp_path):
    state = InstallState()
    path = save_guide(state, output=tmp_path / "GUIDE.md")
    content = path.read_text()
    assert "ANKYLOSAURUS" in content
    assert "ankylosaurus status" in content


def test_guide_ollama_section(tmp_path):
    state = InstallState(runtime="ollama")
    path = save_guide(state, output=tmp_path / "GUIDE.md")
    content = path.read_text()
    assert "Ollama" in content
    assert "ollama serve" in content


def test_guide_lmstudio_section(tmp_path):
    state = InstallState(runtime="lm-studio")
    path = save_guide(state, output=tmp_path / "GUIDE.md")
    content = path.read_text()
    assert "LM Studio" in content
    assert "lms" in content


def test_guide_models_section(tmp_path):
    state = InstallState(models=[{"role": "chat", "repo_id": "test/model", "size_gb": 4.2}])
    path = save_guide(state, output=tmp_path / "GUIDE.md")
    content = path.read_text()
    assert "test/model" in content
    assert "4.2" in content


def test_guide_llm_cli_section(tmp_path):
    state = InstallState(tools={"llm_cli": True})
    path = save_guide(state, output=tmp_path / "GUIDE.md")
    content = path.read_text()
    assert "llm" in content


def test_guide_fabric_section(tmp_path):
    state = InstallState(tools={"fabric": True})
    path = save_guide(state, output=tmp_path / "GUIDE.md")
    content = path.read_text()
    assert "fabric-ai" in content


def test_guide_personas_section(tmp_path):
    state = InstallState(personas=["coder", "tutor"])
    path = save_guide(state, output=tmp_path / "GUIDE.md")
    content = path.read_text()
    assert "coder" in content
    assert "tutor" in content


def test_guide_empty_state_no_crash(tmp_path):
    state = InstallState()
    path = save_guide(state, output=tmp_path / "GUIDE.md")
    assert path.exists()
    assert len(path.read_text()) > 50
