"""Persona manager — CRUD + built-in templates."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from .state import InstallState, save_state

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "personas"

BUILTIN_PERSONAS = {
    "coder": {
        "name": "coder",
        "system": "You are an expert programmer. Write clean, efficient, well-tested code. Explain your reasoning. Use best practices for the language at hand.",
        "language": "en",
    },
    "researcher": {
        "name": "researcher",
        "system": "You are a research assistant. Analyze topics thoroughly, cite sources when possible, identify gaps in knowledge, and present balanced perspectives.",
        "language": "en",
    },
    "writer": {
        "name": "writer",
        "system": "You are a skilled writer. Help with drafting, editing, and structuring text. Adapt tone and style to the context. Be concise but thorough.",
        "language": "en",
    },
    "tutor": {
        "name": "tutor",
        "system": "You are a patient tutor. Explain concepts step by step, use analogies, check understanding, and adapt to the student's level. Use Socratic method when appropriate.",
        "language": "en",
    },
    "analyst": {
        "name": "analyst",
        "system": "You are a data analyst. Help interpret data, suggest visualizations, write analysis code (Python/pandas/SQL), and explain statistical concepts clearly.",
        "language": "en",
    },
    "translator": {
        "name": "translator",
        "system": "You are a professional translator. Translate accurately while preserving tone, idioms, and cultural context. Flag ambiguities. Support all major languages.",
        "language": "multi",
    },
    "summarizer": {
        "name": "summarizer",
        "system": "You are a summarization expert. Extract key points, create structured summaries (bullet points, TL;DR, executive summary), and highlight actionable items.",
        "language": "en",
    },
    "general": {
        "name": "general",
        "system": "You are a helpful, knowledgeable assistant. Answer clearly and concisely. Ask for clarification when needed.",
        "language": "en",
    },
}


def list_personas(state: InstallState, console: Console) -> None:
    """Display all personas (built-in + custom)."""
    table = Table(title="Personas", border_style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Language")
    table.add_column("Preview")

    for name, p in BUILTIN_PERSONAS.items():
        table.add_row(name, "[dim]built-in[/dim]", p["language"], p["system"][:60] + "...")

    # Custom personas from templates dir
    for f in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            name = data.get("name", f.stem)
            if name not in BUILTIN_PERSONAS:
                table.add_row(
                    name, "[cyan]custom[/cyan]",
                    data.get("language", "?"),
                    data.get("system", "")[:60] + "...",
                )
        except (json.JSONDecodeError, KeyError):
            pass

    console.print(table)


def create_persona(console: Console) -> dict:
    """Interactively create a new persona."""
    name = Prompt.ask("Persona name")
    system = Prompt.ask("System prompt")
    language = Prompt.ask("Language", choices=["en", "fr", "multi"], default="en")

    persona = {"name": name, "system": system, "language": language}

    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    path = TEMPLATES_DIR / f"{name}.json"
    path.write_text(json.dumps(persona, indent=2, ensure_ascii=False))
    console.print(f"[green]✓ Persona '{name}' saved to {path}[/green]")
    return persona


def edit_persona(name: str, console: Console) -> dict | None:
    """Edit an existing custom persona."""
    path = TEMPLATES_DIR / f"{name}.json"
    if not path.exists():
        console.print(f"[red]Persona '{name}' not found.[/red]")
        return None

    data = json.loads(path.read_text())
    console.print(f"Current system prompt: [dim]{data.get('system', '')}[/dim]")
    new_system = Prompt.ask("New system prompt (enter to keep)", default=data.get("system", ""))
    data["system"] = new_system

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    console.print(f"[green]✓ Persona '{name}' updated.[/green]")
    return data


def delete_persona(name: str, state: InstallState, console: Console) -> None:
    """Delete a custom persona."""
    if name in BUILTIN_PERSONAS:
        console.print(f"[yellow]Cannot delete built-in persona '{name}'.[/yellow]")
        return

    path = TEMPLATES_DIR / f"{name}.json"
    if not path.exists():
        console.print(f"[red]Persona '{name}' not found.[/red]")
        return

    path.unlink()
    if name in state.personas:
        state.personas.remove(name)
        save_state(state)
    console.print(f"[green]✓ Persona '{name}' deleted.[/green]")


def install_builtin_personas(state: InstallState) -> None:
    """Write all built-in persona templates to disk."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in BUILTIN_PERSONAS.items():
        path = TEMPLATES_DIR / f"{name}.json"
        if not path.exists():
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    state.personas = list(BUILTIN_PERSONAS.keys())
