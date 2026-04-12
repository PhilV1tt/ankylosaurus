"""Generate personalized GUIDE.md based on install state."""

from __future__ import annotations

from pathlib import Path

from modules.state import InstallState


def save_guide(state: InstallState, output: Path | None = None) -> Path:
    """Generate GUIDE.md tailored to what was installed."""
    path = output or Path.home() / ".ankylosaurus" / "GUIDE.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    sections = [_header()]

    if state.runtime:
        sections.append(_runtime_section(state))

    if state.models:
        sections.append(_models_section(state))

    if state.tools.get("llm_cli"):
        sections.append(_llm_cli_section())

    if state.tools.get("fabric"):
        sections.append(_fabric_section())

    if state.tools.get("msty"):
        sections.append(_msty_section())

    if state.tools.get("anythingllm"):
        sections.append(_anythingllm_section())

    if state.personas:
        sections.append(_personas_section(state))

    sections.append(_management_section())

    path.write_text("\n\n".join(sections) + "\n")
    return path


def _header() -> str:
    return """# 🦕 ANKYLOSAURUS — Your Local LLM Setup Guide

This guide was generated based on your specific installation.
Run `python install.py status` to see your current setup."""


def _runtime_section(state: InstallState) -> str:
    rt = state.runtime
    if rt == "lm-studio":
        return """## Runtime: LM Studio

- **Start server**: Open LM Studio app or `lms server start`
- **API endpoint**: `http://localhost:1234/v1`
- **Load model**: Select model in LM Studio UI or `lms load <model>`
- **Check loaded**: `lms ps`"""
    else:
        return """## Runtime: Ollama

- **Start server**: `ollama serve` (or it may auto-start)
- **API endpoint**: `http://localhost:11434`
- **List models**: `ollama list`
- **Run model**: `ollama run <model>`"""


def _models_section(state: InstallState) -> str:
    lines = ["## Installed Models\n"]
    for m in state.models:
        lines.append(f"- **{m.get('role', '?')}**: `{m.get('repo_id', '?')}` ({m.get('size_gb', '?')} GB)")
    return "\n".join(lines)


def _llm_cli_section() -> str:
    return """## llm CLI (Simon Willison)

- **Quick chat**: `llm "your question"`
- **With model alias**: `llm -m q27 "your question"`
- **List models**: `llm models`
- **Templates**: `llm templates`
- **Pipe input**: `cat file.py | llm "explain this code"`"""


def _fabric_section() -> str:
    return """## fabric-ai

- **Summarize**: `fabric-ai -p summarize < article.txt`
- **Explain code**: `fabric-ai -p explain_code < script.py`
- **Extract wisdom**: `fabric-ai -p extract_wisdom < transcript.txt`
- **List patterns**: `fabric-ai --listpatterns`
- **Update patterns**: `fabric-ai --updatepatterns`"""


def _msty_section() -> str:
    return """## Msty Studio

- **Open**: Launch Msty Studio from Applications
- **Connect**: Settings → Add LM Studio backend (localhost:1234)
- **Personas**: Use Persona Studio for custom chat profiles
- **Modes**: Try Zen/Focus modes for distraction-free chat"""


def _anythingllm_section() -> str:
    return """## AnythingLLM

- **Open**: Launch AnythingLLM from Applications
- **Setup**: Connect to LM Studio (localhost:1234) as LLM provider
- **Embedding**: Configure embedding model in Settings
- **RAG**: Create workspaces, upload documents, chat with context"""


def _personas_section(state: InstallState) -> str:
    lines = ["## Personas\n", f"Available: {', '.join(state.personas)}\n"]
    lines.append("- **List**: `python install.py personas`")
    lines.append("- **Templates**: `templates/personas/*.json`")
    return "\n".join(lines)


def _management_section() -> str:
    return """## Management Commands

| Command | What it does |
|---------|-------------|
| `python install.py status` | Show installation dashboard |
| `python install.py check` | Check for updates & new models |
| `python install.py update` | Update all components |
| `python install.py personas` | Manage LLM personas |
| `python install.py uninstall` | Clean removal |"""
