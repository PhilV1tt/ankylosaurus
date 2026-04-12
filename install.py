"""ANKYLOSAURUS — automated local LLM setup CLI."""

from __future__ import annotations

import typer
from rich.console import Console

from splash import show_splash

app = typer.Typer(
    name="ankylosaurus",
    no_args_is_help=True,
    help="🦕 ANKYLOSAURUS — automated local LLM setup for any machine",
)
console = Console()


@app.command()
def install():
    """Full interactive installation: detect hardware, pick runtime & models, install everything."""
    show_splash()
    from modules.detect import detect_hardware, display_hardware
    from modules.decision import decide_runtime, display_decision
    from modules.questionnaire import run_questionnaire
    from modules.models import find_chat_models, find_embedding_models, display_candidates
    from modules.installer import run_install
    from modules.extensions import show_extension_menu
    from modules.personas import install_builtin_personas
    from modules.guide import save_guide
    from modules.state import load_state, save_state

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
    prefs = run_questionnaire(profile)
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

    # 6. Personas
    install_builtin_personas(state)
    save_state(state)

    # 7. Extensions (optional)
    show_extension_menu(state, console)

    # 8. Generate guide
    guide_path = save_guide(state)
    console.print(f"\n[bold green]📖 Guide saved to {guide_path}[/bold green]")
    console.print("[bold]Done! Your local LLM stack is ready.[/bold]")


@app.command()
def uninstall():
    """Remove installed components cleanly."""
    show_splash()
    from modules.state import load_state, state_exists
    from modules.uninstaller import run_uninstall

    if not state_exists():
        console.print("[yellow]No installation found.[/yellow]")
        raise typer.Exit()

    run_uninstall(load_state(), console)


@app.command()
def update():
    """Update installed components to latest versions."""
    show_splash()
    from modules.state import load_state, state_exists
    from modules.updater import run_update

    if not state_exists():
        console.print("[yellow]No installation found.[/yellow]")
        raise typer.Exit()

    run_update(load_state(), console)


@app.command()
def status():
    """Show dashboard of current installation state."""
    show_splash()
    from modules.status import show_status
    show_status(console)


@app.command()
def check():
    """Check for available updates and new models."""
    show_splash()
    from modules.state import load_state, state_exists
    from modules.checker import run_check

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
    from modules.state import load_state
    from modules.personas import list_personas, create_persona, edit_persona, delete_persona

    state = load_state()

    if action == "list":
        list_personas(state, console)
    elif action == "create":
        persona = create_persona(console)
        if persona["name"] not in state.personas:
            state.personas.append(persona["name"])
            from modules.state import save_state
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
