"""Clean uninstallation — reverse order, confirmation before each step."""

from __future__ import annotations

import shutil
import subprocess

from rich.console import Console
from rich.prompt import Confirm

from .state import InstallState, STATE_FILE


def run_uninstall(state: InstallState, console: Console) -> None:
    """Remove installed components in reverse order."""
    console.print("\n[bold red]Uninstall ANKYLOSAURUS stack[/bold red]\n")

    steps = [
        ("aliases", "Shell aliases", _remove_aliases),
        ("anythingllm", "AnythingLLM", _remove_cask, "anythingllm"),
        ("msty", "Msty Studio", _remove_cask, "mstystudio"),
        ("fabric", "fabric-ai", _remove_pip, "fabric-ai"),
        ("llm_cli", "llm CLI", _remove_pip, "llm"),
        ("runtime", "Runtime ({})".format(state.runtime), _remove_runtime),
    ]

    for step in steps:
        _, label = step[0], step[1]
        if not Confirm.ask(f"Remove {label}?", default=False):
            console.print(f"  [dim]Skipped {label}[/dim]")
            continue

        try:
            if len(step) == 4:
                step[2](step[3], state, console)
            else:
                step[2](state, console)
            console.print(f"  [green]✓ Removed {label}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {label}: {e}[/red]")

    if Confirm.ask("Remove ANKYLOSAURUS state file?", default=False):
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            console.print("  [green]✓ State file removed[/green]")

    console.print("\n[bold]Uninstall complete.[/bold]")


def _remove_aliases(state: InstallState, console: Console) -> None:
    from pathlib import Path
    for rc in [Path.home() / ".zshrc", Path.home() / ".bashrc"]:
        if not rc.exists():
            continue
        content = rc.read_text()
        start = content.find("# === ANKYLOSAURUS ===")
        end = content.find("# === END ANKYLOSAURUS ===")
        if start != -1 and end != -1:
            end += len("# === END ANKYLOSAURUS ===\n")
            rc.write_text(content[:start] + content[end:])


def _remove_cask(cask_name: str, state: InstallState, console: Console) -> None:
    if shutil.which("brew"):
        subprocess.run(["brew", "uninstall", "--cask", cask_name],
                       capture_output=True, text=True)


def _remove_pip(pkg: str, state: InstallState, console: Console) -> None:
    subprocess.run(["pip3", "uninstall", "-y", pkg], capture_output=True, text=True)


def _remove_runtime(state: InstallState, console: Console) -> None:
    rt = state.runtime
    if rt == "lm-studio" and shutil.which("brew"):
        subprocess.run(["brew", "uninstall", "--cask", "lm-studio"],
                       capture_output=True, text=True)
    elif rt == "ollama":
        if shutil.which("brew"):
            subprocess.run(["brew", "uninstall", "ollama"],
                           capture_output=True, text=True)
        else:
            console.print("  [dim]Remove Ollama manually if needed.[/dim]")
