"""Component updater — update without breaking config."""

from __future__ import annotations

import shutil
import subprocess

from rich.console import Console
from rich.prompt import Confirm

from modules.state import InstallState, save_state


def run_update(state: InstallState, console: Console) -> None:
    """Update installed components one by one."""
    console.print("\n[bold cyan]Update Components[/bold cyan]\n")

    updated = False

    # Runtime
    if state.runtime == "lm-studio" and shutil.which("brew"):
        if Confirm.ask("Update LM Studio?", default=True):
            _brew_upgrade("lm-studio", console, cask=True)
            updated = True
    elif state.runtime == "ollama" and shutil.which("ollama"):
        if Confirm.ask("Update Ollama?", default=True):
            if shutil.which("brew"):
                _brew_upgrade("ollama", console)
            updated = True

    # pip packages
    for pkg in ["llm", "fabric-ai"]:
        if state.tools.get(pkg.replace("-", "_"), False) or shutil.which(pkg):
            if Confirm.ask(f"Update {pkg}?", default=True):
                _pip_upgrade(pkg, console)
                updated = True

    # GUI apps
    if state.tools.get("msty") and shutil.which("brew"):
        if Confirm.ask("Update Msty Studio?", default=True):
            _brew_upgrade("mstystudio", console, cask=True)
            updated = True

    if state.tools.get("anythingllm") and shutil.which("brew"):
        if Confirm.ask("Update AnythingLLM?", default=True):
            _brew_upgrade("anythingllm", console, cask=True)
            updated = True

    if updated:
        save_state(state)
        console.print("\n[bold green]✓ Updates complete.[/bold green]")
    else:
        console.print("\n[dim]Nothing to update.[/dim]")


def _brew_upgrade(name: str, console: Console, cask: bool = False) -> None:
    cmd = ["brew", "upgrade"]
    if cask:
        cmd.append("--cask")
    cmd.append(name)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        console.print(f"  [green]✓ {name} updated[/green]")
    else:
        console.print(f"  [dim]{name} already up to date or not installed via brew[/dim]")


def _pip_upgrade(pkg: str, console: Console) -> None:
    result = subprocess.run(
        ["pip3", "install", "--upgrade", pkg],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        console.print(f"  [green]✓ {pkg} updated[/green]")
    else:
        console.print(f"  [red]✗ {pkg} update failed[/red]")
