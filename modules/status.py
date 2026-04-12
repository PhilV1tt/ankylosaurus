"""Status dashboard — Rich multi-panel view of installation state."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from modules.state import state_exists, load_state


def show_status(console: Console) -> None:
    """Display full installation dashboard."""
    if not state_exists():
        console.print("[yellow]No installation found. Run 'ankylosaurus install' first.[/yellow]")
        return

    state = load_state()

    panels = []

    # Runtime panel
    rt_lines = [
        f"Runtime: [bold]{state.runtime or 'none'}[/bold]",
        f"Version: {state.runtime_version or '?'}",
        f"Steps done: {len(state.steps_completed)}",
    ]
    panels.append(Panel("\n".join(rt_lines), title="Runtime", border_style="cyan"))

    # Models panel
    if state.models:
        model_lines = []
        for m in state.models:
            role = m.get("role", "?")
            repo = m.get("repo_id", "?")
            size = m.get("size_gb", "?")
            model_lines.append(f"[bold]{role}[/bold]: {repo} ({size} GB)")
        panels.append(Panel("\n".join(model_lines), title="Models", border_style="green"))

    # Tools panel
    if state.tools:
        tool_lines = []
        for tool, installed in state.tools.items():
            icon = "[green]✓[/green]" if installed else "[red]✗[/red]"
            tool_lines.append(f"{icon} {tool}")
        panels.append(Panel("\n".join(tool_lines), title="Tools", border_style="yellow"))

    # Extensions panel
    exts = []
    for cat, items in state.extensions.items():
        if items:
            exts.append(f"[bold]{cat}[/bold]: {', '.join(str(i) for i in items)}")
    if exts:
        panels.append(Panel("\n".join(exts), title="Extensions", border_style="magenta"))

    # Personas panel
    if state.personas:
        panels.append(Panel(", ".join(state.personas), title="Personas", border_style="blue"))

    # Hardware panel
    if state.hardware:
        hw = state.hardware
        hw_lines = [
            f"OS: {hw.get('os', '?')}",
            f"CPU: {hw.get('cpu', '?')}",
            f"GPU: {hw.get('gpu', '?')}",
            f"RAM: {hw.get('ram_gb', '?')} GB",
        ]
        panels.append(Panel("\n".join(hw_lines), title="Hardware", border_style="dim"))

    for p in panels:
        console.print(p)

    console.print(f"\n[dim]Last updated: {state.last_updated}[/dim]")
