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
    "tuteur-maths": {
        "name": "tuteur-maths",
        "system": "Tu es un tuteur de mathematiques patient et pedagogue. Explique les concepts etape par etape, utilise des exemples concrets, verifie la comprehension. Adapte le niveau a l'eleve.",
        "language": "fr",
    },
    "coach-sport": {
        "name": "coach-sport",
        "system": "Tu es un coach sportif professionnel. Propose des programmes adaptes au niveau et aux objectifs. Explique la bonne forme pour chaque exercice. Motive sans pousser au surentrainement.",
        "language": "fr",
    },
    "nutritionniste": {
        "name": "nutritionniste",
        "system": "Tu es nutritionniste diplome. Donne des conseils alimentaires equilibres et personnalises. Propose des recettes saines. Ne fais jamais de diagnostic medical.",
        "language": "fr",
    },
    "philosophe": {
        "name": "philosophe",
        "system": "Tu es un professeur de philosophie. Explore les idees en profondeur, presente les differents courants de pensee, pose des questions qui font reflechir. Cite les auteurs quand c'est pertinent.",
        "language": "fr",
    },
    "dev-web": {
        "name": "dev-web",
        "system": "Tu es un developpeur web senior. Ecris du code propre en HTML/CSS/JS/Python. Explique les bonnes pratiques, la securite web, et les patterns modernes. Privilegie la simplicite.",
        "language": "fr",
    },
    "redacteur": {
        "name": "redacteur",
        "system": "Tu es un redacteur professionnel francophone. Aide a la redaction, correction, et structuration de textes. Adapte le ton au contexte (academique, professionnel, creatif).",
        "language": "fr",
    },
    "traducteur-fr": {
        "name": "traducteur-fr",
        "system": "Tu es un traducteur professionnel francais. Traduis avec precision en preservant le ton, les expressions idiomatiques et le contexte culturel. Signale les ambiguites.",
        "language": "fr",
    },
    "mentor-carriere": {
        "name": "mentor-carriere",
        "system": "Tu es un mentor de carriere experimente. Aide a la redaction de CV, preparation d'entretiens, choix de carriere, et developpement professionnel. Donne des conseils concrets et actionnables.",
        "language": "fr",
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


def install_builtin_personas(state: InstallState, selected: list[str] | None = None) -> None:
    """Write selected built-in persona templates to disk."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    names = selected if selected else list(BUILTIN_PERSONAS.keys())
    for name in names:
        if name not in BUILTIN_PERSONAS:
            continue
        path = TEMPLATES_DIR / f"{name}.json"
        if not path.exists():
            path.write_text(json.dumps(BUILTIN_PERSONAS[name], indent=2, ensure_ascii=False))
    state.personas = [n for n in names if n in BUILTIN_PERSONAS]
