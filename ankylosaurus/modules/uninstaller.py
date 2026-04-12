"""Clean uninstallation — reverse order, confirmation before each step."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm

from .state import InstallState, STATE_FILE


def run_uninstall(
    state: InstallState,
    console: Console,
    remove_all: bool = False,
    models_only: bool = False,
    keep_notes: bool = False,
) -> None:
    """Remove installed components in reverse order."""
    console.print("\n[bold red]Uninstall ANKYLOSAURUS stack[/bold red]\n")

    if models_only:
        _remove_models(state, console)
        console.print("\n[bold]Models removed.[/bold]")
        return

    steps = [
        ("aliases", "Shell aliases", _remove_aliases),
        ("anythingllm", "AnythingLLM", _remove_cask, "anythingllm"),
        ("openwebui", "Open WebUI", _remove_docker, "open-webui"),
        ("fabric", "fabric-ai", _remove_pip, "fabric-ai"),
        ("llm_cli", "llm CLI", _remove_pip, "llm"),
        ("runtime", "Runtime ({})".format(state.runtime), _remove_runtime),
    ]

    for step in steps:
        _, label = step[0], step[1]
        if not remove_all and not Confirm.ask(f"Remove {label}?", default=False):
            console.print(f"  [dim]Skipped {label}[/dim]")
            continue

        try:
            if len(step) == 4:
                step[2](step[3], state, console)
            else:
                step[2](state, console)
            console.print(f"  [green]Removed {label}[/green]")
        except Exception as e:
            console.print(f"  [red]{label}: {e}[/red]")

    if not keep_notes:
        guide = Path.home() / ".ankylosaurus" / "GUIDE.md"
        if guide.exists():
            guide.unlink()
            console.print("  [green]Removed GUIDE.md[/green]")

    if remove_all or Confirm.ask("Remove ANKYLOSAURUS state file?", default=False):
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            console.print("  [green]State file removed[/green]")

    # Show reclaimed space estimate
    _show_reclaimed(state, console)
    console.print("\n[bold]Uninstall complete.[/bold]")


def _remove_aliases(state: InstallState, console: Console) -> None:
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


def _remove_docker(container: str, state: InstallState, console: Console) -> None:
    if shutil.which("docker"):
        subprocess.run(["docker", "stop", container], capture_output=True, text=True)
        subprocess.run(["docker", "rm", container], capture_output=True, text=True)


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


def _remove_models(state: InstallState, console: Console) -> None:
    """Remove downloaded models only."""
    if not state.models:
        console.print("[dim]No models recorded in state.[/dim]")
        return
    for m in state.models:
        repo_id = m.get("repo_id", "")
        console.print(f"  Removing {repo_id}...")
        # Try ollama rm
        if state.runtime == "ollama" and shutil.which("ollama"):
            name = m.get("ollama_name", "") or repo_id.split("/")[-1].lower()
            subprocess.run(["ollama", "rm", name], capture_output=True, text=True)
    state.models.clear()
    from .state import save_state
    save_state(state)
    console.print("  [green]Models removed from state.[/green]")


def _show_reclaimed(state: InstallState, console: Console) -> None:
    """Estimate disk space reclaimed from removed models."""
    total_gb = sum(m.get("size_gb", 0) for m in state.models)
    if total_gb > 0:
        console.print(f"\n[bold]Estimated space reclaimed: ~{total_gb:.1f} GB[/bold]")
