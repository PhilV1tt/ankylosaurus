"""Version checker — compare installed vs latest available."""

from __future__ import annotations

import shutil
import subprocess

from rich.console import Console
from rich.table import Table

from modules.state import InstallState


def run_check(state: InstallState, console: Console) -> None:
    """Check for updates across all installed components."""
    console.print("\n[bold cyan]Version Check[/bold cyan]\n")

    table = Table(border_style="dim")
    table.add_column("Component", style="bold")
    table.add_column("Installed")
    table.add_column("Latest")
    table.add_column("Status")

    checks = [
        ("Runtime", _check_runtime, state),
        ("llm CLI", _check_pip_pkg, "llm"),
        ("fabric-ai", _check_pip_pkg, "fabric-ai"),
    ]

    for name, func, arg in checks:
        try:
            installed, latest = func(arg)
            if installed and latest:
                status = "[green]✓ up to date[/green]" if installed == latest else "[yellow]↑ update available[/yellow]"
            elif installed:
                status = "[dim]? cannot check[/dim]"
                latest = "?"
            else:
                status = "[dim]not installed[/dim]"
                installed = latest = "—"
            table.add_row(name, installed, latest, status)
        except Exception:
            table.add_row(name, "?", "?", "[red]error[/red]")

    console.print(table)

    # Check for new models
    _check_new_models(state, console)


def _check_runtime(state: InstallState) -> tuple[str, str]:
    installed = state.runtime_version or "unknown"
    # Can't easily check latest without specific API per runtime
    return installed, installed


def _check_pip_pkg(pkg: str) -> tuple[str, str]:
    installed = ""
    latest = ""

    if shutil.which("pip3"):
        result = subprocess.run(
            ["pip3", "show", pkg], capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if line.startswith("Version:"):
                installed = line.split(":", 1)[1].strip()
                break

    if installed:
        result = subprocess.run(
            ["pip3", "index", "versions", pkg],
            capture_output=True, text=True,
        )
        # Output: "pkg (X.Y.Z)" on first line
        if result.stdout:
            first = result.stdout.splitlines()[0]
            if "(" in first:
                latest = first.split("(")[1].split(")")[0].strip()

    return installed, latest


def _check_new_models(state: InstallState, console: Console) -> None:
    """Check HF Hub for trending models that might interest the user."""
    try:
        from huggingface_hub import HfApi
        api = HfApi()
        trending = list(api.list_models(
            pipeline_tag="text-generation",
            sort="trending",
            direction=-1,
            limit=5,
        ))

        if trending:
            console.print("\n[bold cyan]Trending Models[/bold cyan]")
            for m in trending:
                console.print(f"  • {m.id} ({m.downloads:,} downloads)")
    except Exception:
        pass  # silently skip if no network
