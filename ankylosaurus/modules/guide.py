"""Generate personalized GUIDE.md based on install state."""

from __future__ import annotations

from pathlib import Path

from .state import InstallState


def save_guide(state: InstallState, output: Path | None = None) -> Path:
    """Generate GUIDE.md tailored to what was installed."""
    path = output or Path.home() / ".ankylosaurus" / "GUIDE.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    sections = [_header()]

    # Quick start section with actual model names
    sections.append(_quickstart_section(state))

    if state.runtime:
        sections.append(_runtime_section(state))

    if state.models:
        sections.append(_models_section(state))

    if state.tools.get("llm_cli"):
        sections.append(_llm_cli_section())

    if state.tools.get("fabric"):
        sections.append(_fabric_section())

    if state.tools.get("openwebui"):
        sections.append(_openwebui_section())

    if state.tools.get("anythingllm"):
        sections.append(_anythingllm_section())

    if state.personas:
        sections.append(_personas_section(state))

    sections.append(_management_section())

    path.write_text("\n\n".join(sections) + "\n")
    return path


def _header() -> str:
    return """# ANKYLOSAURUS -- Your Local LLM Setup Guide

This guide was generated based on your specific installation.
Run `ankylosaurus status` to see your current setup."""


def _quickstart_section(state: InstallState) -> str:
    lines = ["## Quick Start\n"]

    # Find chat model
    chat_model = None
    for m in state.models:
        if m.get("role") == "chat":
            chat_model = m
            break

    if chat_model:
        ollama_name = chat_model.get("ollama_name", "")
        repo_id = chat_model.get("repo_id", "?")

        lines.append(f"Your chat model: **{repo_id}**\n")

        if state.runtime == "ollama" and ollama_name:
            lines.append("```bash")
            lines.append("# Direct with Ollama")
            lines.append(f"ollama run {ollama_name}")
            lines.append("")
            lines.append("# Via ankylosaurus (supports personas)")
            lines.append('ankylosaurus run "hello"')
            lines.append('ankylosaurus run --persona coder "write a fibonacci function"')
            lines.append("")
            lines.append("# Interactive mode")
            lines.append("ankylosaurus run")
            lines.append("```")
        elif state.runtime == "lm-studio":
            lines.append("```bash")
            lines.append("# Start the server")
            lines.append("lms server start")
            lines.append("")
            lines.append("# Chat via ankylosaurus")
            lines.append('ankylosaurus run "hello"')
            lines.append("ankylosaurus run  # interactive mode")
            lines.append("```")
        else:
            lines.append('```bash\nankylosaurus run "hello"\n```')
    else:
        lines.append("No chat model installed yet. Run `ankylosaurus install`.")

    return "\n".join(lines)


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
        ollama_name = m.get("ollama_name", "")
        name_str = f" (ollama: `{ollama_name}`)" if ollama_name else ""
        lines.append(f"- **{m.get('role', '?')}**: `{m.get('repo_id', '?')}` ({m.get('size_gb', '?')} GB){name_str}")
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


def _openwebui_section() -> str:
    return """## Open WebUI

- **Open**: http://localhost:3000
- **Start/Stop**: `docker start open-webui` / `docker stop open-webui`
- **Connected to**: Ollama (auto-detected)
- **Features**: Chat, RAG (upload docs), model management, personas
- **Docs**: https://docs.openwebui.com"""


def _anythingllm_section() -> str:
    return """## AnythingLLM

- **Open**: Launch AnythingLLM from Applications
- **Setup**: Connect to LM Studio (localhost:1234) as LLM provider
- **Embedding**: Configure embedding model in Settings
- **RAG**: Create workspaces, upload documents, chat with context"""


def _personas_section(state: InstallState) -> str:
    lines = ["## Personas\n", f"Available: {', '.join(state.personas)}\n"]
    lines.append("- **List**: `ankylosaurus personas`")
    lines.append("- **Templates**: `templates/personas/*.json`")
    return "\n".join(lines)


def _management_section() -> str:
    return """## Management Commands

| Command | What it does |
|---------|-------------|
| `ankylosaurus run` | Chat with your model (interactive) |
| `ankylosaurus run "question"` | One-shot query |
| `ankylosaurus run -p coder "..."` | Chat with a persona |
| `ankylosaurus status` | Show installation dashboard |
| `ankylosaurus check` | Check for updates & new models |
| `ankylosaurus update` | Update all components |
| `ankylosaurus personas` | Manage LLM personas |
| `ankylosaurus uninstall` | Clean removal |"""
