"""Status dashboard - Rich multi-panel view of installation state."""

from __future__ import annotations

import shutil
import subprocess

from rich.console import Console
from rich.panel import Panel

from .state import state_exists, load_state


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

    # Live resource usage panel
    res_lines = _get_resource_usage(state)
    if res_lines:
        panels.append(Panel("\n".join(res_lines), title="Resources (live)", border_style="red"))

    # Loaded model panel
    loaded = _get_loaded_model(state)
    if loaded:
        panels.append(Panel(loaded, title="Active Model", border_style="green"))

    for p in panels:
        console.print(p)

    console.print(f"\n[dim]Last updated: {state.last_updated}[/dim]")


def _get_resource_usage(state) -> list[str]:
    """Get live RAM and disk usage."""
    lines = []
    try:
        import psutil
        mem = psutil.virtual_memory()
        ram_used = round(mem.used / (1024 ** 3), 1)
        ram_total = round(mem.total / (1024 ** 3), 1)
        ram_pct = mem.percent
        lines.append(f"RAM: {ram_used}/{ram_total} GB ({ram_pct}% used)")
    except ImportError:
        pass

    # Disk used by models
    model_disk = _estimate_model_disk(state)
    if model_disk > 0:
        lines.append(f"Models on disk: ~{model_disk:.1f} GB")

    try:
        import psutil
        disk = psutil.disk_usage("/")
        disk_free = round(disk.free / (1024 ** 3), 1)
        lines.append(f"Disk free: {disk_free} GB")
    except ImportError:
        pass

    return lines


def _estimate_model_disk(state) -> float:
    """Sum up size_gb from installed models."""
    total = 0.0
    for m in state.models:
        total += m.get("size_gb", 0) or 0
    return total


def _get_loaded_model(state) -> str:
    """Detect currently loaded model via Ollama."""
    runtime = state.runtime or ""

    if "ollama" in runtime.lower():
        if shutil.which("ollama"):
            try:
                result = subprocess.run(
                    ["ollama", "ps"], capture_output=True, text=True, timeout=5,
                )
                lines = result.stdout.strip().splitlines()
                if len(lines) > 1:
                    # First line is header, rest are loaded models
                    models = [l.split()[0] for l in lines[1:] if l.strip()]
                    if models:
                        return "[bold]" + ", ".join(models) + "[/bold] (loaded)"
            except (subprocess.TimeoutExpired, OSError):
                pass
        return "[dim]idle (no model loaded)[/dim]"

    return ""
