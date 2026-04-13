"""Run LLM models directly from ankylosaurus."""

from __future__ import annotations

import subprocess
import sys

from rich.console import Console

from .state import InstallState


def run_model(
    state: InstallState,
    prompt: str | None = None,
    persona: str | None = None,
    console: Console | None = None,
) -> None:
    """Run the installed chat model. Interactive if no prompt given."""
    if console is None:
        console = Console()

    # Find chat model
    chat_model = None
    for m in state.models:
        if m.get("role") == "chat":
            chat_model = m
            break

    if not chat_model:
        console.print("[red]No chat model installed. Run 'ankylosaurus install' first.[/red]")
        sys.exit(1)

    runtime = state.runtime

    if runtime == "ollama":
        _run_ollama(chat_model, prompt, persona, state, console)
    else:
        console.print(f"[red]Unknown runtime: {runtime}[/red]")
        sys.exit(1)


def _run_ollama(
    model: dict,
    prompt: str | None,
    persona: str | None,
    state: InstallState,
    console: Console,
) -> None:
    ollama_name = model.get("ollama_name", "")
    if not ollama_name:
        # Fallback: try repo_id short name
        ollama_name = model.get("repo_id", "").split("/")[-1].lower()

    system_prompt = _get_system_prompt(persona, state)

    cmd = ["ollama", "run", ollama_name]
    if system_prompt:
        cmd.extend(["--system", system_prompt])

    if prompt:
        cmd.append(prompt)
    elif system_prompt:
        console.print(f"[dim]Persona: {persona}[/dim]")

    result = subprocess.run(cmd, capture_output=not sys.stdin.isatty())
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode(errors="replace")
        if "500" in stderr or "failed to load" in stderr.lower():
            console.print(
                f"[red]Model '{ollama_name}' failed to load.[/red]\n"
                "[dim]This usually means not enough VRAM/RAM. Try a smaller model or quant.[/dim]"
            )
        elif stderr.strip():
            console.print(f"[red]Ollama error: {stderr.strip()[:200]}[/red]")


_persona_cache: dict[str, str | None] = {}


def _get_system_prompt(persona: str | None, state: InstallState) -> str | None:
    if not persona:
        return None

    if persona in _persona_cache:
        return _persona_cache[persona]

    from .personas import BUILTIN_PERSONAS, TEMPLATES_DIR
    import json

    if persona in BUILTIN_PERSONAS:
        result = BUILTIN_PERSONAS[persona]["system"]
        _persona_cache[persona] = result
        return result

    # Check custom personas
    path = TEMPLATES_DIR / f"{persona}.json"
    if path.exists():
        data = json.loads(path.read_text())
        result = data.get("system")
        _persona_cache[persona] = result
        return result

    _persona_cache[persona] = None
    return None
