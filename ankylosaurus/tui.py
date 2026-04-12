"""TUI — Textual-based interactive interface."""

from __future__ import annotations

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from . import __version__


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

def _load_status() -> dict:
    """Read install state and return summary dict."""
    from .modules.state import state_exists, load_state

    if not state_exists():
        return {}

    state = load_state()
    info = {}
    if state.runtime:
        info["runtime"] = state.runtime
    for m in state.models:
        role = m.get("role", "?")
        name = m.get("ollama_name", "") or m.get("repo_id", "?").split("/")[-1]
        size = m.get("size_gb", "?")
        info[role] = f"{name} ({size} GB)"
    tools = [k for k, v in state.tools.items() if v]
    if tools:
        info["outils"] = ", ".join(tools)
    if state.personas:
        info["personas"] = f"{len(state.personas)} installes"
    return info


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class Logo(Static):
    """Colored ASCII logo."""

    LOGO = (
        "    _   _  _ _  ___   _ _    ___   _   _  _ ___ _   _ ___ \n"
        "   /_\\ | \\| | |/ / | / | |  / _ \\ / __| /_\\ | | | | _ | | | / __|\n"
        "  / _ \\| .` |   <  |_\\ | |_| (_) |\\__ \\/ _ \\| |_| |   | |_| \\__ \\\n"
        " /_/ \\_|_|\\_|_|\\_\\__/ |____\\___/ |___/_/ \\_\\___/|_|_|\\___/|___/\n"
    )

    def render(self) -> str:
        return self.LOGO


class StatusPanel(Static):
    """Show current install state."""

    def compose(self) -> ComposeResult:
        info = _load_status()
        if not info:
            yield Label("[#e66414]Aucune installation.[/#e66414] Lance [bold]Installer[/bold] pour commencer.", id="status-empty")
        else:
            lines = []
            for key, val in info.items():
                lines.append(f"[bold #ffd028]{key.capitalize():12s}[/bold #ffd028] [#e66414]{val}[/#e66414]")
            yield Label("\n".join(lines), id="status-info")


class MenuOption(ListItem):
    """A single menu entry."""

    def __init__(self, key: str, title: str, desc: str) -> None:
        super().__init__()
        self.key = key
        self.title = title
        self.desc = desc

    def compose(self) -> ComposeResult:
        yield Label(f"[bold]{self.title}[/bold]  [dim]{self.desc}[/dim]")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def _build_menu_items() -> list[tuple[str, str, str]]:
    from .modules.state import state_exists

    installed = state_exists()
    items = []
    if installed:
        items.append(("run", "Discuter", "Poser une question au modele"))
        items.append(("status", "Tableau de bord", "Voir l'etat de l'installation"))
        items.append(("install", "Reinstaller", "Relancer l'installation"))
        items.append(("check", "Verifier", "Chercher des mises a jour"))
        items.append(("update", "Mettre a jour", "Mettre a jour les composants"))
        items.append(("personas", "Personas", "Gerer les personnalites"))
        items.append(("uninstall", "Desinstaller", "Supprimer les composants"))
    else:
        items.append(("install", "Installer", "Detecter le materiel et installer un modele"))
        items.append(("status", "Tableau de bord", "Voir l'etat"))
    items.append(("quit", "Quitter", ""))
    return items


class AnkylosaurusApp(App):
    """Main TUI application."""

    TITLE = "ANKYLOSAURUS"
    CSS = """
    Screen {
        background: #111;
    }

    Header {
        background: #1a0a00;
        color: #e66414;
    }

    #logo {
        width: 100%;
        content-align: center middle;
        color: #e66414;
        text-style: bold;
        margin-top: 1;
    }

    #subtitle {
        width: 100%;
        text-align: center;
        color: #a06020;
        margin-bottom: 1;
    }

    #status-panel {
        width: 60;
        margin: 0 auto;
        padding: 1 2;
        border: round #c04010;
        margin-bottom: 1;
    }

    #status-empty {
        text-align: center;
    }

    #menu {
        width: 60;
        margin: 0 auto;
        height: auto;
        max-height: 16;
        border: round #c04010;
        padding: 0 1;
        background: #1a0a00;
    }

    #menu > ListItem {
        padding: 0 2;
        color: #ffd028;
    }

    #menu > ListItem.--highlight {
        background: #c04010 40%;
        color: #ffe060;
    }

    Footer {
        background: #1a0a00;
        color: #e66414;
    }
    """

    BINDINGS = [
        Binding("q", "quit_app", "Quitter"),
        Binding("enter", "select_item", "Choisir", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Logo(id="logo")
            yield Label(
                f"v{__version__} -- ton assistant IA local",
                id="subtitle",
            )
            yield StatusPanel(id="status-panel")
            menu = ListView(id="menu")
            for key, title, desc in _build_menu_items():
                menu.append(MenuOption(key, title, desc))
            yield menu
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#menu", ListView).focus()

    @on(ListView.Selected, "#menu")
    def handle_menu(self, event: ListView.Selected) -> None:
        item: MenuOption = event.item  # type: ignore[assignment]
        self._execute(item.key)

    def action_quit_app(self) -> None:
        self.exit()

    def action_select_item(self) -> None:
        menu = self.query_one("#menu", ListView)
        if menu.highlighted_child is not None:
            item: MenuOption = menu.highlighted_child  # type: ignore[assignment]
            self._execute(item.key)

    def _execute(self, cmd: str) -> None:
        if cmd == "quit":
            self.exit()
            return

        # Suspend the TUI, run the command in the terminal, then resume
        with self.suspend():
            _run_command(cmd)

        # Refresh status after command
        panel = self.query_one("#status-panel", StatusPanel)
        panel.remove_children()
        info = _load_status()
        if not info:
            panel.mount(Label("[#e66414]Aucune installation.[/#e66414] Lance [bold]Installer[/bold] pour commencer.", id="status-empty"))
        else:
            lines = []
            for key, val in info.items():
                lines.append(f"[bold #ffd028]{key.capitalize():12s}[/bold #ffd028] [#e66414]{val}[/#e66414]")
            panel.mount(Label("\n".join(lines), id="status-info"))

        # Rebuild menu (options may change after install/uninstall)
        menu = self.query_one("#menu", ListView)
        menu.clear()
        for key, title, desc in _build_menu_items():
            menu.append(MenuOption(key, title, desc))


# ---------------------------------------------------------------------------
# Command runner (runs in suspended terminal)
# ---------------------------------------------------------------------------

def _run_command(cmd: str) -> None:
    from rich.console import Console
    from .modules.state import load_state, state_exists, save_state

    console = Console()

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

    console.print("\n[dim]Appuie sur Entree pour revenir...[/dim]")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_tui() -> None:
    """Launch the Textual TUI."""
    app = AnkylosaurusApp()
    app.run()
