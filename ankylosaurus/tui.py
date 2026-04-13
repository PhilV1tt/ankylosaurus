"""TUI — Premium multi-panel dashboard built with Textual."""

from __future__ import annotations

import shutil
import subprocess

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Button, Footer, Label, ListItem, ListView, Static, DataTable

from . import __version__


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

_state_cache: tuple[float, dict] | None = None


def _load_state_summary() -> dict:
    """Load install state and return a structured summary (cached by mtime)."""
    global _state_cache
    from .modules.state import state_exists, load_state, STATE_FILE

    if not state_exists():
        return {}

    try:
        mtime = STATE_FILE.stat().st_mtime
    except OSError:
        return {}
    if _state_cache and _state_cache[0] == mtime:
        return _state_cache[1]

    state = load_state()
    summary: dict = {}

    # Hardware
    hw = state.hardware
    if hw:
        summary["hardware"] = {
            "os": hw.get("os", "?"),
            "cpu": hw.get("cpu", "?"),
            "gpu": hw.get("gpu", "None"),
            "ram_gb": hw.get("ram_gb", "?"),
        }

    # Runtime
    if state.runtime:
        summary["runtime"] = {
            "name": state.runtime,
            "version": state.runtime_version or "?",
            "steps": len(state.steps_completed),
        }

    # Preferences (includes gui_mode)
    if state.preferences:
        summary["preferences"] = state.preferences

    # Models
    summary["models"] = []
    for m in state.models:
        summary["models"].append({
            "role": m.get("role", "?"),
            "repo_id": m.get("repo_id", "?"),
            "name": m.get("ollama_name", "") or m.get("repo_id", "?").split("/")[-1],
            "format": m.get("format", "?"),
            "size_gb": m.get("size_gb", "?"),
            "score": m.get("score", 0),
        })

    # Tools
    summary["tools"] = {k: v for k, v in state.tools.items()}

    # Personas
    summary["personas"] = state.personas or []

    _state_cache = (mtime, summary)
    return summary


def _check_runtime_alive(runtime: str) -> bool:
    """Check if the runtime process is responding."""
    try:
        if runtime == "ollama" and shutil.which("ollama"):
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=3,
            )
            return result.returncode == 0
    except subprocess.TimeoutExpired:
        pass
    return False


def _get_ram_available() -> float:
    """Get available RAM in GB."""
    try:
        import psutil
        return round(psutil.virtual_memory().available / (1024 ** 3), 1)
    except (ImportError, OSError):
        return 0.0


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class BrandHeader(Static):
    """Custom header with brand name, version, runtime indicator, and RAM."""

    runtime_alive = reactive(False)
    ram_available = reactive(0.0)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._runtime_name = ""

    def on_mount(self) -> None:
        summary = _load_state_summary()
        rt = summary.get("runtime", {})
        self._runtime_name = rt.get("name", "")
        self.ram_available = _get_ram_available()
        self.runtime_alive = _check_runtime_alive(self._runtime_name) if self._runtime_name else False
        self.set_interval(30, self._refresh_status)

    def _refresh_status(self) -> None:
        if self._runtime_name:
            self.runtime_alive = _check_runtime_alive(self._runtime_name)
        self.ram_available = _get_ram_available()

    def render(self) -> str:
        left = f" ANKYLOSAURUS  v{__version__}"

        parts = []
        if self._runtime_name:
            dot = "[#22c55e]●[/]" if self.runtime_alive else "[#ef4444]●[/]"
            label = "running" if self.runtime_alive else "stopped"
            parts.append(f"{dot} {self._runtime_name} {label}")
        if self.ram_available:
            parts.append(f"{self.ram_available} GB free")
        right = "   ".join(parts)

        return f"[bold #e66414]{left}[/]{'':>10}{right} "


class SidebarItem(ListItem):
    """Menu item with icon and label."""

    def __init__(self, key: str, icon: str, title: str, is_sep: bool = False) -> None:
        super().__init__()
        self.key = key
        self.icon = icon
        self.title = title
        self.is_sep = is_sep

    def compose(self) -> ComposeResult:
        if self.is_sep:
            yield Label("[#333]────────────────[/]", classes="sep-label")
        else:
            yield Label(f" {self.icon}  {self.title}")


class HomeView(Static):
    """Dashboard home with info panels in a grid."""

    def __init__(self, summary: dict) -> None:
        super().__init__()
        self._summary = summary

    def compose(self) -> ComposeResult:
        s = self._summary
        if not s:
            yield Label(
                "\n  [#e66414]Aucune installation detectee.[/]\n\n"
                "  Selectionne [bold #ffd028]Installer[/] dans le menu pour commencer.\n",
            )
            return

        with Horizontal(classes="panel-row"):
            # Hardware panel
            hw = s.get("hardware", {})
            hw_text = (
                f"[bold #e66414]Hardware[/]\n"
                f"[#999]OS[/]      {hw.get('os', '?')}\n"
                f"[#999]CPU[/]     {hw.get('cpu', '?')}\n"
                f"[#999]GPU[/]     {hw.get('gpu', 'None')}\n"
                f"[#999]RAM[/]     {hw.get('ram_gb', '?')} GB"
            )
            yield Static(hw_text, classes="info-panel")

            # Runtime panel
            rt = s.get("runtime", {})
            prefs = s.get("preferences", {})
            ui_mode = prefs.get("gui_mode", "")
            rt_text = (
                f"[bold #e66414]Runtime[/]\n"
                f"[#999]Engine[/]  {rt.get('name', 'none')}\n"
                f"[#999]Version[/] {rt.get('version', '?')}\n"
                f"[#999]UI[/]      {ui_mode or 'terminal'}\n"
                f"[#999]Steps[/]   {rt.get('steps', 0)} done"
            )
            yield Static(rt_text, classes="info-panel")

        # Models panel
        models = s.get("models", [])
        if models:
            lines = ["[bold #e66414]Models[/]"]
            for m in models:
                role_color = "#22c55e" if m["role"] == "chat" else "#3b82f6"
                lines.append(
                    f"  [{role_color}]{m['role']:8s}[/]  "
                    f"{m['name']}  [#666]{m['format']}  {m['size_gb']} GB[/]"
                )
            yield Static("\n".join(lines), classes="info-panel wide-panel")

        # Tools panel
        tools = s.get("tools", {})
        if tools:
            lines = ["[bold #e66414]Tools[/]"]
            for tool, installed in tools.items():
                icon = "[#22c55e]✓[/]" if installed else "[#ef4444]✗[/]"
                lines.append(f"  {icon}  {tool}")
            personas = s.get("personas", [])
            if personas:
                lines.append(f"\n[bold #e66414]Personas[/]  [#999]{len(personas)} installed[/]")
                lines.append(f"  [#666]{', '.join(personas[:6])}{'...' if len(personas) > 6 else ''}[/]")
            yield Static("\n".join(lines), classes="info-panel wide-panel")


class ModelsView(Static):
    """DataTable view of installed models."""

    def __init__(self, models: list[dict]) -> None:
        super().__init__()
        self._models = models

    def compose(self) -> ComposeResult:
        yield Label("[bold #e66414]  Modeles installes[/]\n")
        if not self._models:
            yield Label("  [#666]Aucun modele installe.[/]")
            return

        table = DataTable(id="models-table")
        yield table

    def on_mount(self) -> None:
        table = self.query_one("#models-table", DataTable)
        table.add_columns("Role", "Modele", "Format", "Taille", "Score")
        for m in self._models:
            score_pct = int(float(m.get("score", 0)) * 100)
            table.add_row(
                m.get("role", "?"),
                m.get("name", m.get("repo_id", "?")),
                m.get("format", "?"),
                f"{m.get('size_gb', '?')} GB",
                f"{score_pct}%",
            )


class PersonasView(Static):
    """List of installed personas."""

    def __init__(self, personas: list[str]) -> None:
        super().__init__()
        self._personas = personas

    def compose(self) -> ComposeResult:
        yield Label("[bold #e66414]  Personas[/]\n")
        if not self._personas:
            yield Label("  [#666]Aucun persona installe.[/]")
            return

        # Try to load persona details
        try:
            from .modules.personas import BUILTIN_PERSONAS
            for name in self._personas:
                info = BUILTIN_PERSONAS.get(name, {})
                desc = info.get("system", "")[:80] if info else ""
                lang = info.get("language", "") if info else ""
                yield Label(
                    f"  [bold #ffd028]{name:14s}[/]  "
                    f"[#999]{lang}[/]  [#666]{desc}[/]"
                )
        except (ImportError, KeyError, TypeError):
            for name in self._personas:
                yield Label(f"  [#ffd028]{name}[/]")


class ToolsView(Static):
    """Status of installed tools."""

    def __init__(self, tools: dict, summary: dict) -> None:
        super().__init__()
        self._tools = tools
        self._summary = summary

    def compose(self) -> ComposeResult:
        yield Label("[bold #e66414]  Outils[/]\n")
        if not self._tools:
            yield Label("  [#666]Aucun outil installe.[/]")
            return

        for tool, installed in self._tools.items():
            icon = "[#22c55e]✓[/]" if installed else "[#ef4444]✗[/]"
            yield Label(f"  {icon}  [bold]{tool}[/]")

        # Show UI mode info
        prefs = self._summary.get("preferences", {})
        ui_mode = prefs.get("gui_mode", "")
        if ui_mode:
            yield Label("\n[bold #e66414]  Interface[/]\n")
            ui_labels = {
                "open-webui": "Open WebUI  [#999](http://localhost:3000)[/]",
                "ollama-cli": "Ollama CLI  [#999](ollama run <model>)[/]",
                "terminal": "Terminal  [#999](ankylosaurus run)[/]",
            }
            yield Label(f"  [#ffd028]{ui_labels.get(ui_mode, ui_mode)}[/]")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

MENU_ITEMS = [
    ("home", "◆", "Home"),
    ("models", "◈", "Models"),
    ("personas", "◉", "Personas"),
    ("tools", "⚙", "Tools"),
    ("---", "", ""),
    ("install", "▶", "Install"),
    ("check", "↻", "Check"),
    ("update", "⇡", "Update"),
    ("run", "▸", "Chat"),
    ("---", "", ""),
    ("uninstall", "✕", "Uninstall"),
    ("quit", "⏻", "Quit"),
]


class AnkylosaurusApp(App):
    """Premium multi-panel dashboard TUI."""

    TITLE = "ANKYLOSAURUS"

    CSS = """
    Screen {
        background: #0d0d0d;
    }

    #brand-header {
        dock: top;
        height: 1;
        background: #1a0a00;
        padding: 0 1;
    }

    #body {
        height: 1fr;
    }

    /* --- Sidebar --- */
    #sidebar {
        width: 24;
        background: #141414;
        border-right: solid #2a1a0a;
        padding: 1 0;
    }

    #sidebar > ListItem {
        padding: 0 1;
        color: #a08060;
        height: 2;
    }

    #sidebar > ListItem.--highlight {
        background: #e66414 15%;
        color: #ffd028;
        text-style: bold;
    }

    .sep-label {
        height: 1;
        color: #333;
    }

    /* --- Main content --- */
    #main {
        padding: 1 2;
        overflow-y: auto;
    }

    /* --- Info panels --- */
    .info-panel {
        border: round #2a1a0a;
        padding: 1 2;
        height: auto;
        margin: 0 1 1 0;
        min-width: 30;
        max-width: 42;
    }

    .wide-panel {
        max-width: 100%;
        width: 100%;
    }

    .panel-row {
        height: auto;
    }

    /* --- DataTable --- */
    DataTable {
        height: auto;
        max-height: 20;
        margin: 0 2;
        background: #141414;
    }

    DataTable > .datatable--header {
        color: #e66414;
        text-style: bold;
        background: #1a0a00;
    }

    DataTable > .datatable--cursor {
        background: #e66414 20%;
        color: #ffd028;
    }

    /* --- Footer --- */
    Footer {
        background: #1a0a00;
        color: #a08060;
    }
    """

    BINDINGS = [
        Binding("q", "quit_app", "Quit"),
        Binding("r", "refresh_all", "Refresh"),
        Binding("1", "goto_home", "Home", show=False),
        Binding("2", "goto_models", "Models", show=False),
        Binding("3", "goto_personas", "Personas", show=False),
        Binding("4", "goto_tools", "Tools", show=False),
        Binding("tab", "toggle_focus", "Focus", show=False),
    ]

    current_view = reactive("home")

    def __init__(self) -> None:
        super().__init__()
        self._summary: dict = {}
        self._suspended = False
        self._wizard_step = -1  # -1 = not in wizard
        self._wizard_profile_data: dict = {}
        self._wizard_selected_personas: list[str] = []
        self._wizard_hw_profile = None

    def compose(self) -> ComposeResult:
        yield BrandHeader(id="brand-header")
        with Horizontal(id="body"):
            yield ListView(
                *[SidebarItem(key, icon, title, is_sep=(key == "---")) for key, icon, title in MENU_ITEMS],
                id="sidebar",
            )
            yield ScrollableContainer(id="main")
        yield Footer()

    def on_mount(self) -> None:
        self._summary = _load_state_summary()
        self._show_view("home")
        self.query_one("#sidebar", ListView).focus()

    # --- View switching ---

    def _show_view(self, view_name: str) -> None:
        main = self.query_one("#main", ScrollableContainer)
        main.remove_children()

        if view_name == "home":
            main.mount(HomeView(self._summary))
        elif view_name == "models":
            main.mount(ModelsView(self._summary.get("models", [])))
        elif view_name == "personas":
            main.mount(PersonasView(self._summary.get("personas", [])))
        elif view_name == "tools":
            main.mount(ToolsView(self._summary.get("tools", {}), self._summary))

        self.current_view = view_name

    def _refresh_and_show(self, view_name: str) -> None:
        self._summary = _load_state_summary()
        self._show_view(view_name)
        # Also refresh the header
        header = self.query_one("#brand-header", BrandHeader)
        header._refresh_status()

    # --- Menu handling ---

    @on(ListView.Selected, "#sidebar")
    def handle_sidebar(self, event: ListView.Selected) -> None:
        if self._suspended:
            return
        item: SidebarItem = event.item  # type: ignore[assignment]
        if item.is_sep:
            return
        self._handle_action(item.key)

    def _handle_action(self, key: str) -> None:
        # In-TUI views
        if key in ("home", "models", "personas", "tools"):
            self._show_view(key)
            return

        # Quit
        if key == "quit":
            self.exit()
            return

        # Install — launch wizard inline
        if key == "install":
            self._start_wizard()
            return

        # Suspend-to-terminal commands
        if key in ("run", "uninstall", "update", "check"):
            self._suspended = True
            with self.suspend():
                subprocess.run(["ankylosaurus", key])
                print("\nPress Enter to return...")
                try:
                    input()
                except (EOFError, KeyboardInterrupt):
                    pass
            self._suspended = False
            self._refresh_and_show(self.current_view)
            return

    # --- Wizard flow ---

    def _start_wizard(self) -> None:
        from .tui_wizard import WelcomeScreen
        self._wizard_step = 0
        main = self.query_one("#main", ScrollableContainer)
        main.remove_children()
        main.mount(WelcomeScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "wizard-next":
            self._wizard_advance()
        elif event.button.id == "wizard-done":
            self._wizard_step = -1
            self._refresh_and_show("home")

    def _wizard_advance(self) -> None:
        main = self.query_one("#main", ScrollableContainer)

        if self._wizard_step == 0:
            # Welcome → Profile
            self._wizard_step = 1
            from .tui_wizard import ProfileScreen
            main.remove_children()
            main.mount(ProfileScreen())

        elif self._wizard_step == 1:
            # Profile → Preview (generate personas from profile)
            from .tui_wizard import ProfileScreen, PreviewScreen
            profile_screen = main.query_one(ProfileScreen)
            self._wizard_profile_data = profile_screen.get_profile_data()

            from .modules.personas import UserProfile, select_personas
            profile = UserProfile(
                occupation=self._wizard_profile_data["occupation"],
                domains=self._wizard_profile_data["domains"],
                languages=[self._wizard_profile_data["language"]],
                primary_language=self._wizard_profile_data["language"],
            )

            templates = select_personas(profile)
            persona_list = [(t.id, t.name_tpl, True) for t in templates]

            self._wizard_step = 2
            main.remove_children()
            main.mount(PreviewScreen(persona_list))

        elif self._wizard_step == 2:
            # Preview → Install
            from .tui_wizard import PreviewScreen, InstallScreen
            preview_screen = main.query_one(PreviewScreen)
            self._wizard_selected_personas = preview_screen.get_selected()

            self._wizard_step = 3
            main.remove_children()
            install_screen = InstallScreen()
            main.mount(install_screen)

            # Run installer in background worker
            self.run_worker(self._run_install_worker, thread=True)

        elif self._wizard_step == 3:
            # Install → Done (auto-advanced from worker)
            pass

    def _run_install_worker(self) -> None:
        """Run the full install in a worker thread."""
        from rich.console import Console
        import io

        from .modules.detect import detect_hardware, detect_docker
        from .modules.decision import decide_runtime
        from .modules.personas import UserProfile, generate_personas
        from .modules.questionnaire import UserPreferences
        from .modules.installer import run_install
        from .modules.state import load_state, save_state

        # Use captured hardware profile or detect fresh
        hw_profile = getattr(self, "_wizard_hw_profile", None)
        if not hw_profile:
            hw_profile = detect_hardware()

        docker_info = detect_docker()
        decision = decide_runtime(hw_profile, docker_info=docker_info)

        state = load_state()
        state.hardware = {
            "os": hw_profile.os_type, "cpu": hw_profile.cpu_brand,
            "gpu": hw_profile.gpu_name, "ram_gb": hw_profile.ram_total_gb,
        }
        state.runtime = decision.runtime

        # Build profile from wizard data
        pd = self._wizard_profile_data
        profile = UserProfile(
            occupation=pd.get("occupation", "other"),
            domains=pd.get("domains", []),
            languages=[pd.get("language", "en")],
            primary_language=pd.get("language", "en"),
        )

        prefs = UserPreferences(
            usage=pd.get("occupation", "general"),
            features=["chat", "rag"],
            disk_budget_gb=pd.get("disk_budget", 30),
            want_gui=pd.get("want_gui", True),
            language=pd.get("language", "en"),
            battery_mode=(hw_profile.os_type == "macOS"),
            gui_mode="open-webui" if pd.get("want_gui", True) and docker_info.get("installed") else "terminal",
            personas=self._wizard_selected_personas,
            profile=profile,
        )

        from dataclasses import asdict
        state.preferences = {
            "usage": prefs.usage, "features": prefs.features,
            "disk_budget_gb": prefs.disk_budget_gb, "want_gui": prefs.want_gui,
            "gui_mode": prefs.gui_mode, "language": prefs.language,
            "battery_mode": prefs.battery_mode,
            "profile": asdict(profile),
        }
        save_state(state)

        # Run install with a null console (output goes to TUI via call_from_thread)
        console = Console(file=io.StringIO())

        try:
            run_install(hw_profile, decision, state, prefs, console)
        except Exception:
            pass  # non-fatal — state already saved

        # Show done screen
        from .modules.guide import save_guide
        try:
            guide_path = str(save_guide(state))
        except Exception:
            guide_path = ""

        def _show_done():
            from .tui_wizard import DoneScreen
            main = self.query_one("#main", ScrollableContainer)
            main.remove_children()
            main.mount(DoneScreen({
                "runtime": state.runtime,
                "model_count": len(state.models),
                "persona_count": len(state.personas),
                "gui_url": "http://localhost:3000" if state.tools.get("openwebui") else "",
                "guide_path": guide_path,
            }))
            self._wizard_step = 4

        self.call_from_thread(_show_done)

    # --- Key bindings ---

    def action_quit_app(self) -> None:
        self.exit()

    def action_refresh_all(self) -> None:
        self._refresh_and_show(self.current_view)

    def action_goto_home(self) -> None:
        self._show_view("home")

    def action_goto_models(self) -> None:
        self._show_view("models")

    def action_goto_personas(self) -> None:
        self._show_view("personas")

    def action_goto_tools(self) -> None:
        self._show_view("tools")

    def action_toggle_focus(self) -> None:
        sidebar = self.query_one("#sidebar", ListView)
        main = self.query_one("#main", ScrollableContainer)
        if sidebar.has_focus:
            main.focus()
        else:
            sidebar.focus()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_tui() -> None:
    """Launch the Textual TUI."""
    try:
        app = AnkylosaurusApp()
        app.run()
    except Exception as e:
        from rich.console import Console
        Console().print(f"\n[yellow]TUI error: {e}[/yellow]")
        Console().print("[dim]Falling back to CLI. Use 'ankylosaurus install' directly.[/dim]\n")
