"""ANKYLOSAURUS — automated local LLM setup CLI."""

from __future__ import annotations

import signal
import sys
from typing import Optional

import typer
from rich.console import Console

from . import __version__
from .splash import show_splash

# Global non-interactive flag
_yes_mode = False


def _version_callback(value: bool) -> None:
    if value:
        print("ankylosaurus {}".format(__version__))
        raise typer.Exit()


def _yes_callback(value: bool) -> None:
    global _yes_mode
    if value:
        _yes_mode = True


def _sigint_handler(sig, frame):
    console = Console()
    console.print("\n[yellow]Interrupted. Re-run 'ankylosaurus install' to resume.[/yellow]")
    sys.exit(130)


signal.signal(signal.SIGINT, _sigint_handler)

app = typer.Typer(
    name="ankylosaurus",
    invoke_without_command=True,
    help="ANKYLOSAURUS -- automated local LLM setup for any machine",
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
    yes: Optional[bool] = typer.Option(
        None, "--yes", "-y", callback=_yes_callback, is_eager=True,
        help="Non-interactive mode: accept all defaults.",
    ),
) -> None:
    if ctx.invoked_subcommand is None:
        from .tui import run_tui
        run_tui()


console = Console()


@app.command()
def tui():
    """Interactive menu interface."""
    from .tui import run_tui
    run_tui()


@app.command()
def install():
    """Full interactive installation: detect hardware, pick runtime & models, install everything."""
    show_splash()
    from .modules.detect import detect_hardware, display_hardware
    from .modules.decision import decide_runtime, display_decision
    from .modules.questionnaire import run_questionnaire
    from .modules.models import find_chat_models, find_embedding_models, display_candidates
    from .modules.installer import run_install
    from .modules.extensions import show_extension_menu
    from .modules.guide import save_guide
    from .modules.state import load_state, save_state

    state = load_state()

    # 1. Detect hardware
    profile = detect_hardware()
    display_hardware(profile)
    state.hardware = {
        "os": profile.os_type, "cpu": profile.cpu_brand,
        "gpu": profile.gpu_name, "ram_gb": profile.ram_total_gb,
    }

    # 2. Decide runtime + backend
    decision = decide_runtime(profile)
    display_decision(decision)
    state.runtime = decision.runtime

    # 3. Questionnaire
    prefs = run_questionnaire(profile, yes_mode=_yes_mode)
    state.preferences = {
        "usage": prefs.usage, "features": prefs.features,
        "disk_budget_gb": prefs.disk_budget_gb, "want_gui": prefs.want_gui,
        "language": prefs.language, "battery_mode": prefs.battery_mode,
    }

    # 4. Model selection
    console.print("\n[bold]Searching for chat models...[/bold]")
    chat_candidates = find_chat_models(decision, profile, prefs)
    chat_choice = display_candidates(chat_candidates, "Chat Models")
    if chat_choice >= 0:
        state.models.append({"role": "chat", **chat_candidates[chat_choice].__dict__})

    console.print("\n[bold]Searching for embedding models...[/bold]")
    emb_candidates = find_embedding_models(decision, profile)
    emb_choice = display_candidates(emb_candidates, "Embedding Models")
    if emb_choice >= 0:
        state.models.append({"role": "embedding", **emb_candidates[emb_choice].__dict__})

    save_state(state)

    # 5. Install components
    run_install(profile, decision, state, prefs, console)

    # 6. Extensions (optional)
    show_extension_menu(state, console)

    # 7. Generate guide
    guide_path = save_guide(state)
    console.print(f"\n[bold green]Guide saved to {guide_path}[/bold green]")
    console.print("[bold]Done! Your local LLM stack is ready.[/bold]")


@app.command()
def uninstall(
    all_: bool = typer.Option(False, "--all", help="Remove everything without asking."),
    models_only: bool = typer.Option(False, "--models-only", help="Remove only downloaded models."),
    keep_notes: bool = typer.Option(False, "--keep-notes", help="Keep guides and notes."),
):
    """Remove installed components cleanly."""
    show_splash()
    from .modules.state import load_state, state_exists
    from .modules.uninstaller import run_uninstall

    if not state_exists():
        console.print("[yellow]No installation found.[/yellow]")
        raise typer.Exit()

    run_uninstall(
        load_state(), console,
        remove_all=all_, models_only=models_only, keep_notes=keep_notes,
    )


@app.command()
def update():
    """Update installed components to latest versions."""
    show_splash()
    from .modules.state import load_state, state_exists
    from .modules.updater import run_update

    if not state_exists():
        console.print("[yellow]No installation found.[/yellow]")
        raise typer.Exit()

    run_update(load_state(), console)


@app.command()
def status():
    """Show dashboard of current installation state."""
    show_splash()
    from .modules.status import show_status
    show_status(console)


@app.command()
def check():
    """Check for available updates and new models."""
    show_splash()
    from .modules.state import load_state, state_exists
    from .modules.checker import run_check

    if not state_exists():
        console.print("[yellow]No installation found.[/yellow]")
        raise typer.Exit()

    run_check(load_state(), console)


@app.command()
def personas(
    action: str = typer.Argument("list", help="list | create | edit | delete"),
    name: str = typer.Argument(None, help="Persona name (for edit/delete)"),
):
    """Manage LLM personas (list, create, edit, delete)."""
    show_splash()
    from .modules.state import load_state
    from .modules.personas import list_personas, create_persona, edit_persona, delete_persona

    state = load_state()

    if action == "list":
        list_personas(state, console)
    elif action == "create":
        persona = create_persona(console)
        if persona["name"] not in state.personas:
            state.personas.append(persona["name"])
            from .modules.state import save_state
            save_state(state)
    elif action == "edit":
        if not name:
            console.print("[red]Usage: personas edit <name>[/red]")
            raise typer.Exit(1)
        edit_persona(name, console)
    elif action == "delete":
        if not name:
            console.print("[red]Usage: personas delete <name>[/red]")
            raise typer.Exit(1)
        delete_persona(name, state, console)
    else:
        console.print(f"[red]Unknown action: {action}. Use list|create|edit|delete[/red]")


if __name__ == "__main__":
    app()
