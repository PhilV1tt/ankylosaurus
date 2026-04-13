"""Persona manager — CRUD + built-in templates."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from .state import InstallState, save_state

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "personas"

# Personas that benefit from reasoning/thinking models (Qwen)
# All others use fast chat models (Gemma)
REASONING_PERSONAS = {
    "coder", "researcher", "tutor", "analyst",
    "tuteur-maths", "dev-web", "philosophe",
}

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


_custom_persona_cache: dict[str, tuple[float, dict]] = {}


def _load_custom_persona(path: Path) -> dict | None:
    """Load a custom persona JSON with mtime-based cache."""
    key = str(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    cached = _custom_persona_cache.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        data = json.loads(path.read_text())
        _custom_persona_cache[key] = (mtime, data)
        return data
    except (json.JSONDecodeError, OSError):
        return None


def list_personas(state: InstallState, console: Console) -> None:
    """Display all personas (built-in + custom)."""
    table = Table(title="Personas", border_style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Language")
    table.add_column("Preview")

    for name, p in BUILTIN_PERSONAS.items():
        preview = p["system"][:60] + ("..." if len(p["system"]) > 60 else "")
        table.add_row(name, "[dim]built-in[/dim]", p["language"], preview)

    # Custom personas from templates dir (cached by mtime)
    for f in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            data = _load_custom_persona(f)
            if data is None:
                continue
            name = data.get("name", f.stem)
            if name not in BUILTIN_PERSONAS:
                sys_prompt = data.get("system", "")
                preview = sys_prompt[:60] + ("..." if len(sys_prompt) > 60 else "")
                table.add_row(
                    name, "[cyan]custom[/cyan]",
                    data.get("language", "?"),
                    preview,
                )
        except (json.JSONDecodeError, KeyError):
            pass

    console.print(table)


def _sanitize_persona_name(name: str) -> str:
    """Validate and sanitize persona name for safe filesystem use."""
    import re
    name = name.strip()
    # Strip path separators
    name = Path(name).name
    # Only allow alphanumeric, hyphens, underscores
    name = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    if not name:
        raise ValueError("Persona name must contain at least one alphanumeric character.")
    if len(name) > 64:
        raise ValueError("Persona name must be 64 characters or less.")
    return name


def create_persona(console: Console) -> dict:
    """Interactively create a new persona."""
    raw_name = Prompt.ask("Persona name")
    try:
        name = _sanitize_persona_name(raw_name)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return {"name": ""}

    system = Prompt.ask("System prompt")
    if len(system) > 10000:
        console.print("[yellow]System prompt truncated to 10,000 characters.[/yellow]")
        system = system[:10000]

    language = Prompt.ask("Language", choices=["en", "fr", "multi"], default="en")

    persona = {"name": name, "system": system, "language": language}

    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    path = TEMPLATES_DIR / f"{name}.json"
    # Verify path stays within templates dir
    if not path.resolve().is_relative_to(TEMPLATES_DIR.resolve()):
        console.print("[red]Invalid persona name.[/red]")
        return {"name": ""}
    path.write_text(json.dumps(persona, indent=2, ensure_ascii=False))
    console.print(f"[green]✓ Persona '{name}' saved to {path}[/green]")
    return persona


def edit_persona(name: str, console: Console) -> dict | None:
    """Edit an existing custom persona."""
    name = Path(name).name  # strip path components
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
    name = Path(name).name  # strip path components
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


def _load_persona(name: str) -> dict | None:
    """Load a persona by name (built-in or custom file)."""
    if name in BUILTIN_PERSONAS:
        return BUILTIN_PERSONAS[name]
    path = TEMPLATES_DIR / f"{name}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def export_persona_msty(name: str, output_dir: Path | None = None) -> Path | None:
    """Export a persona as Msty-compatible JSON."""
    persona = _load_persona(name)
    if not persona:
        return None

    msty_data = {
        "name": persona["name"],
        "description": f"ANKYLOSAURUS persona: {persona['name']}",
        "systemPrompt": persona["system"],
        "language": persona.get("language", "en"),
        "temperature": 0.7,
        "maxTokens": 4096,
    }

    out = (output_dir or Path.cwd()) / f"{name}_msty.json"
    out.write_text(json.dumps(msty_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def export_persona_ollama(name: str, output_dir: Path | None = None) -> Path | None:
    """Export a persona as Ollama Modelfile."""
    persona = _load_persona(name)
    if not persona:
        return None

    # Escape quotes in system prompt for Modelfile
    system = persona["system"].replace('"', '\\"')
    modelfile = f'FROM {{}}\nSYSTEM "{system}"\n'

    out = (output_dir or Path.cwd()) / f"{name}.Modelfile"
    out.write_text(modelfile, encoding="utf-8")
    return out


def export_persona(name: str, console: Console, output_dir: Path | None = None) -> None:
    """Export a persona to both Msty JSON and Ollama Modelfile formats."""
    name = Path(name).name  # strip path components

    persona = _load_persona(name)
    if not persona:
        console.print(f"[red]Persona '{name}' not found.[/red]")
        return

    msty_path = export_persona_msty(name, output_dir)
    if msty_path:
        console.print(f"[green]✓ Msty JSON: {msty_path}[/green]")

    ollama_path = export_persona_ollama(name, output_dir)
    if ollama_path:
        console.print(f"[green]✓ Ollama Modelfile: {ollama_path}[/green]")
        console.print(f"  [dim]Usage: ollama create {name} -f {ollama_path}[/dim]")
