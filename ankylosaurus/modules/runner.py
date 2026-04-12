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
    elif runtime == "lm-studio":
        _run_lmstudio(chat_model, prompt, persona, state, console)
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

    if prompt:
        # One-shot mode
        cmd = ["ollama", "run", ollama_name]
        if system_prompt:
            cmd.extend(["--system", system_prompt])
        cmd.append(prompt)
        subprocess.run(cmd)
    else:
        # Interactive mode
        if system_prompt:
            console.print(f"[dim]Persona: {persona}[/dim]")
        cmd = ["ollama", "run", ollama_name]
        if system_prompt:
            cmd.extend(["--system", system_prompt])
        subprocess.run(cmd)


def _run_lmstudio(
    model: dict,
    prompt: str | None,
    persona: str | None,
    state: InstallState,
    console: Console,
) -> None:
    try:
        import importlib.util
        if importlib.util.find_spec("httpx") is None:
            raise ImportError
    except ImportError:
        console.print("[red]httpx required for LM Studio. pip install httpx[/red]")
        sys.exit(1)

    system_prompt = _get_system_prompt(persona, state) or "You are a helpful assistant."

    if not prompt:
        # Interactive loop
        console.print("[dim]Chat with LM Studio (Ctrl-C to quit)[/dim]")
        while True:
            try:
                prompt = input("\n> ")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Bye.[/dim]")
                break
            if not prompt.strip():
                continue
            _lmstudio_query(prompt, system_prompt, console)
    else:
        _lmstudio_query(prompt, system_prompt, console)


def _lmstudio_query(prompt: str, system_prompt: str, console: Console) -> None:
    import httpx

    try:
        resp = httpx.post(
            "http://localhost:1234/v1/chat/completions",
            json={
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
            timeout=120,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            console.print(content)
        else:
            console.print(f"[red]LM Studio error: {resp.status_code}[/red]")
    except httpx.ConnectError:
        console.print("[red]Cannot connect to LM Studio (localhost:1234).[/red]")
        console.print("[dim]Start it with: lms server start[/dim]")


def _get_system_prompt(persona: str | None, state: InstallState) -> str | None:
    if not persona:
        return None

    from .personas import BUILTIN_PERSONAS, TEMPLATES_DIR
    import json

    if persona in BUILTIN_PERSONAS:
        return BUILTIN_PERSONAS[persona]["system"]

    # Check custom personas
    path = TEMPLATES_DIR / f"{persona}.json"
    if path.exists():
        data = json.loads(path.read_text())
        return data.get("system")

    return None
