"""Lightweight TUI — interactive menu using Rich."""

from __future__ import annotations

import os

from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import __version__
from .splash import _color_at

console = Console()

MENU_ITEMS = [
    ("install", "Full setup: detect hardware, pick models, install everything"),
    ("status", "Dashboard of current installation"),
    ("check", "Check for updates and new models"),
    ("update", "Update installed components"),
    ("personas", "Manage LLM personas"),
    ("uninstall", "Remove installed components"),
    ("quit", "Exit"),
]


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def _render_header() -> Text:
    """Animated-style colored header."""
    title = "ANKYLOSAURUS"
    text = Text(justify="center")
    for i, ch in enumerate(title):
        pos = i / len(title)
        r, g, b = _color_at(pos)
        text.append(ch, style=f"bold rgb({r},{g},{b})")
    text.append(f"  v{__version__}", style="dim")
    return text


def _render_menu(selected: int) -> Table:
    """Render menu with highlighted selection."""
    table = Table(
        show_header=False, show_edge=False, box=None,
        pad_edge=False, padding=(0, 2),
    )
    table.add_column(width=3)
    table.add_column()
    table.add_column(style="dim")

    for i, (label, desc) in enumerate(MENU_ITEMS):
        if i == selected:
            marker = ">"
            style = "bold cyan"
        else:
            marker = " "
            style = ""
        table.add_row(marker, label, desc, style=style)

    return table


def _render_status_bar() -> Text:
    """Quick status line from state."""
    from .modules.state import state_exists, load_state

    if not state_exists():
        return Text("  No installation found", style="dim yellow")

    state = load_state()
    parts = []
    if state.runtime:
        parts.append(f"runtime: {state.runtime}")
    if state.models:
        parts.append(f"models: {len(state.models)}")
    if state.personas:
        parts.append(f"personas: {len(state.personas)}")
    tools_count = sum(1 for v in state.tools.values() if v)
    if tools_count:
        parts.append(f"tools: {tools_count}")

    return Text("  " + " | ".join(parts), style="dim green")


def _run_command(cmd: str) -> None:
    """Execute a CLI command and wait for user to continue."""
    from .modules.state import load_state, state_exists, save_state

    console.print()

    if cmd == "install":
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
        run_install(profile, decision, state, prefs, console)

        guide_path = save_guide(state)
        console.print(f"\n[bold green]Guide saved to {guide_path}[/bold green]")

    elif cmd == "status":
        from .modules.status import show_status
        show_status(console)

    elif cmd == "check":
        if not state_exists():
            console.print("[yellow]No installation found.[/yellow]")
        else:
            from .modules.checker import run_check
            run_check(load_state(), console)

    elif cmd == "update":
        if not state_exists():
            console.print("[yellow]No installation found.[/yellow]")
        else:
            from .modules.updater import run_update
            run_update(load_state(), console)

    elif cmd == "personas":
        from .modules.personas import list_personas
        state = load_state()
        list_personas(state, console)

    elif cmd == "uninstall":
        if not state_exists():
            console.print("[yellow]No installation found.[/yellow]")
        else:
            from .modules.uninstaller import run_uninstall
            run_uninstall(load_state(), console)

    console.print("\n[dim]Press Enter to return...[/dim]")
    input()


def run_tui() -> None:
    """Main TUI loop."""
    selected = 0

    while True:
        _clear()

        # Header
        console.print()
        console.print(_render_header())
        console.print(_render_status_bar())
        console.print()

        # Menu
        console.print(_render_menu(selected))
        console.print()

        # Input
        try:
            choice = console.input("[dim]Enter command (or number 1-7): [/dim]").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        # Handle numeric input
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(MENU_ITEMS):
                cmd = MENU_ITEMS[idx][0]
                if cmd == "quit":
                    break
                selected = idx
                _run_command(cmd)
                continue

        # Handle text input
        if choice in ("q", "quit", "exit"):
            break

        for i, (label, _) in enumerate(MENU_ITEMS):
            if choice == label:
                if label == "quit":
                    break
                selected = i
                _run_command(label)
                break
        else:
            if choice:
                console.print(f"[red]Unknown: {choice}[/red]")
                import time
                time.sleep(0.5)
