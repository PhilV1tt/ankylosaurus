"""TUI — friendly interactive menu with arrow-key navigation."""

from __future__ import annotations

import os

import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__
from .splash import _color_at

console = Console()

Q_STYLE = Style([
    ("qmark", "fg:cyan bold"),
    ("question", "bold"),
    ("pointer", "fg:cyan bold"),
    ("highlighted", "fg:cyan bold"),
    ("selected", "fg:green"),
    ("answer", "fg:green bold"),
])

# Menu adapts to installation state — defined in _build_menu()

LOGO = r"""
     ___    _   _ _  ____   ___     ___
    / _ \  | \ | | |/ /\ \ / / |   / _ \
   / /_\ \ |  \| |   /  \ V /| |  / /_\ \
   |  _  | | . ` |  |    \ / | |  |  _  |
   |_| |_| |_|\_|_|\_\   |_| |_|__|_| |_|
                     S A U R U S
"""


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def _colored_logo() -> Text:
    """Render the ASCII logo with the green/brown gradient."""
    text = Text()
    lines = LOGO.strip("\n").split("\n")
    total_chars = sum(len(line) for line in lines)
    char_idx = 0
    for line in lines:
        for ch in line:
            pos = char_idx / max(total_chars, 1)
            r, g, b = _color_at(pos)
            if ch.isalpha() or ch in "/_\\|":
                text.append(ch, style=f"bold rgb({r},{g},{b})")
            else:
                text.append(ch)
            char_idx += 1
        text.append("\n")
    return text


def _status_panel() -> Panel | None:
    """Build a panel showing current install state, or None if not installed."""
    from .modules.state import state_exists, load_state

    if not state_exists():
        return Panel(
            "[dim]Aucune installation trouvee.\n"
            "Selectionne [bold]Installer[/bold] pour commencer.[/dim]",
            title="[yellow]Etat[/yellow]",
            border_style="yellow",
            padding=(0, 2),
        )

    state = load_state()
    table = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
    table.add_column(style="bold", width=12)
    table.add_column()

    if state.runtime:
        table.add_row("Runtime", f"[green]{state.runtime}[/green]")

    if state.models:
        for m in state.models:
            role = m.get("role", "?")
            name = m.get("ollama_name", "") or m.get("repo_id", "?").split("/")[-1]
            size = m.get("size_gb", "?")
            table.add_row(
                role.capitalize(),
                f"[green]{name}[/green] [dim]({size} GB)[/dim]",
            )

    tools = [k for k, v in state.tools.items() if v]
    if tools:
        table.add_row("Outils", "[green]" + ", ".join(tools) + "[/green]")

    if state.personas:
        table.add_row("Personas", f"[green]{len(state.personas)} installes[/green]")

    return Panel(
        table,
        title="[green]Etat actuel[/green]",
        border_style="green",
        padding=(0, 2),
    )


def _build_menu() -> list[tuple[str, str, str]]:
    """Return menu items as (value, label, description).

    Order and availability adapt to install state.
    """
    from .modules.state import state_exists

    installed = state_exists()

    items = []
    if installed:
        items.append(("run", "Discuter", "Lancer le modele et poser une question"))
        items.append(("status", "Tableau de bord", "Voir l'etat de l'installation"))
        items.append(("install", "Reinstaller", "Relancer l'installation complete"))
        items.append(("check", "Verifier", "Chercher des mises a jour et nouveaux modeles"))
        items.append(("update", "Mettre a jour", "Mettre a jour les composants"))
        items.append(("personas", "Personas", "Gerer les personnalites du modele"))
        items.append(("uninstall", "Desinstaller", "Supprimer les composants"))
    else:
        items.append(("install", "Installer", "Detecter le materiel, choisir et installer un modele"))
        items.append(("status", "Tableau de bord", "Voir l'etat de l'installation"))

    items.append(("quit", "Quitter", ""))
    return items


def _run_command(cmd: str) -> None:
    """Execute a menu action."""
    from .modules.state import load_state, state_exists, save_state

    console.print()

    if cmd == "run":
        if not state_exists():
            console.print("[yellow]Aucune installation trouvee.[/yellow]")
        else:
            from .modules.runner import run_model
            run_model(load_state(), console=console)
            return

    elif cmd == "install":
        from .modules.detect import detect_hardware, display_hardware
        from .modules.decision import decide_runtime, display_decision
        from .modules.questionnaire import run_questionnaire
        from .modules.models import find_chat_models, find_embedding_models, display_candidates
        from .modules.installer import run_install
        from .modules.guide import save_guide

        state = load_state()
        profile = detect_hardware()
        display_hardware(profile)
        state.hardware = {
            "os": profile.os_type, "cpu": profile.cpu_brand,
            "gpu": profile.gpu_name, "ram_gb": profile.ram_total_gb,
        }
        decision = decide_runtime(profile)
        display_decision(decision)
        state.runtime = decision.runtime

        prefs = run_questionnaire(profile)
        state.preferences = {
            "usage": prefs.usage, "features": prefs.features,
            "disk_budget_gb": prefs.disk_budget_gb, "want_gui": prefs.want_gui,
            "language": prefs.language, "battery_mode": prefs.battery_mode,
        }

        console.print("\n[bold]Recherche de modeles chat...[/bold]")
        chat_candidates = find_chat_models(decision, profile, prefs)
        chat_choice = display_candidates(chat_candidates, "Chat Models")
        if chat_choice >= 0:
            state.models.append({"role": "chat", **chat_candidates[chat_choice].__dict__})

        console.print("\n[bold]Recherche de modeles embedding...[/bold]")
        emb_candidates = find_embedding_models(decision, profile)
        emb_choice = display_candidates(emb_candidates, "Embedding Models")
        if emb_choice >= 0:
            state.models.append({"role": "embedding", **emb_candidates[emb_choice].__dict__})

        save_state(state)
        run_install(profile, decision, state, prefs, console)
        guide_path = save_guide(state)
        console.print(f"\n[bold green]Guide enregistre : {guide_path}[/bold green]")

    elif cmd == "status":
        from .modules.status import show_status
        show_status(console)

    elif cmd == "check":
        if not state_exists():
            console.print("[yellow]Aucune installation trouvee.[/yellow]")
        else:
            from .modules.checker import run_check
            run_check(load_state(), console)

    elif cmd == "update":
        if not state_exists():
            console.print("[yellow]Aucune installation trouvee.[/yellow]")
        else:
            from .modules.updater import run_update
            run_update(load_state(), console)

    elif cmd == "personas":
        from .modules.personas import list_personas
        list_personas(load_state(), console)

    elif cmd == "uninstall":
        if not state_exists():
            console.print("[yellow]Aucune installation trouvee.[/yellow]")
        else:
            from .modules.uninstaller import run_uninstall
            run_uninstall(load_state(), console)

    console.print("\n[dim]Appuie sur Entree pour revenir au menu...[/dim]")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


def run_tui() -> None:
    """Main TUI loop."""
    while True:
        _clear()

        # Logo
        console.print(_colored_logo(), justify="center")
        console.print(
            f"[dim]v{__version__} -- ton assistant IA local[/dim]",
            justify="center",
        )
        console.print()

        # Status panel
        panel = _status_panel()
        if panel:
            console.print(panel)
            console.print()

        # Menu
        menu = _build_menu()
        choices = []
        for value, label, desc in menu:
            if desc:
                display = f"{label}  [dim]{desc}[/dim]" if console.is_terminal else f"{label} -- {desc}"
            else:
                display = label
            choices.append(questionary.Choice(display, value=value))

        choice = questionary.select(
            "",
            choices=choices,
            style=Q_STYLE,
            qmark="",
            instruction="[fleches haut/bas + Entree]",
        ).ask()

        if choice is None or choice == "quit":
            _clear()
            console.print("[dim]A bientot.[/dim]\n")
            break

        _run_command(choice)
