"""Component installer with auto-resume via steps_completed."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from rich.console import Console

from .state import InstallState
from .decision import RuntimeDecision
from .detect import HardwareProfile
from .questionnaire import UserPreferences


def run_install(
    profile: HardwareProfile,
    decision: RuntimeDecision,
    state: InstallState,
    prefs: UserPreferences,
    console: Console,
) -> InstallState:
    """Run all install steps, skipping already-completed ones."""
    steps = _build_steps(prefs)

    total = len(steps)
    done = sum(1 for sid, _, _ in steps if state.is_done(sid))
    if done > 0:
        console.print(f"\n[dim]Resuming — {done}/{total} steps already done.[/dim]")

    for step_id, label, func in steps:
        if state.is_done(step_id):
            console.print(f"  [dim]✓ {label} (already done)[/dim]")
            continue

        console.print(f"\n[bold cyan]→ {label}[/bold cyan]")
        try:
            func(profile, decision, state, prefs, console)
            state.mark_step(step_id)
            console.print(f"  [green]✓ {label}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {label}: {e}[/red]")
            console.print("[yellow]You can re-run 'ankylosaurus install' to resume.[/yellow]")
            return state

    console.print("\n[bold green]✓ Installation complete![/bold green]")
    return state


def _build_steps(prefs: UserPreferences) -> list[tuple[str, str, callable]]:
    steps = [
        ("runtime_installed", "Install runtime", _install_runtime),
        ("models_downloaded", "Download models", _download_models),
        ("llm_cli_installed", "Install llm CLI", _install_llm_cli),
        ("fabric_installed", "Install fabric-ai", _install_fabric),
    ]
    if prefs.want_gui:
        steps.append(("msty_installed", "Install Msty Studio", _install_msty))
    if "rag" in prefs.features:
        steps.append(("anythingllm_installed", "Install AnythingLLM", _install_anythingllm))
    steps += [
        ("runtime_configured", "Configure runtime", _configure_runtime),
        ("aliases_configured", "Configure shell aliases", _configure_aliases),
    ]
    return steps


# --- Individual step implementations ---

def _run_cmd(cmd: list[str], console: Console, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        console.print(f"[dim]{' '.join(cmd)}[/dim]")
        if result.stderr:
            console.print(f"[dim]{result.stderr.strip()[:200]}[/dim]")
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result


def _has_brew() -> bool:
    return shutil.which("brew") is not None


def _install_runtime(profile, decision, state, prefs, console):
    rt = decision.runtime

    if rt == "lm-studio":
        if shutil.which("lms"):
            console.print("  [dim]LM Studio already installed.[/dim]")
            state.runtime_version = _get_version(["lms", "--version"])
            return

        if profile.os_type == "macOS" and _has_brew():
            _run_cmd(["brew", "install", "--cask", "lm-studio"], console)
        elif profile.os_type == "Windows":
            raise RuntimeError(
                "Please install LM Studio manually from https://lmstudio.ai and re-run."
            )
        else:
            raise RuntimeError(
                "Please install LM Studio manually from https://lmstudio.ai and re-run."
            )
        state.runtime_version = _get_version(["lms", "--version"])

    elif rt == "ollama":
        if shutil.which("ollama"):
            console.print("  [dim]Ollama already installed.[/dim]")
            state.runtime_version = _get_version(["ollama", "--version"])
            return

        if profile.os_type == "macOS" and _has_brew():
            _run_cmd(["brew", "install", "ollama"], console)
        elif profile.os_type == "Linux":
            _run_cmd(["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"], console)
        else:
            raise RuntimeError(
                "Please install Ollama manually from https://ollama.com and re-run."
            )
        state.runtime_version = _get_version(["ollama", "--version"])


def _download_models(profile, decision, state, prefs, console):
    if not state.models:
        console.print("  [yellow]No models selected — skipping download.[/yellow]")
        return

    for model in state.models:
        repo_id = model.get("repo_id", "")
        if not repo_id:
            continue

        console.print(f"  Downloading [bold]{repo_id}[/bold]...")

        if decision.runtime == "ollama" and model.get("format") != "mlx":
            # For Ollama, try ollama pull if model is on Ollama registry
            name = repo_id.split("/")[-1].lower()
            result = subprocess.run(
                ["ollama", "pull", name], capture_output=True, text=True
            )
            if result.returncode == 0:
                continue

        # Fallback: huggingface_hub download
        try:
            from huggingface_hub import snapshot_download
            snapshot_download(
                repo_id,
                local_dir_use_symlinks=False,
            )
            console.print(f"  [green]Downloaded {repo_id}[/green]")
        except Exception as e:
            console.print(f"  [yellow]Download failed for {repo_id}: {e}[/yellow]")
            console.print(f"  [dim]You can download manually: hf download {repo_id}[/dim]")


def _install_llm_cli(profile, decision, state, prefs, console):
    if shutil.which("llm"):
        console.print("  [dim]llm CLI already installed.[/dim]")
        state.tools["llm_cli"] = True
        return

    _run_cmd(["pip3", "install", "llm"], console)
    # Install OpenAI-compatible plugin for LM Studio
    _run_cmd(["llm", "install", "llm-openai-plugin"], console, check=False)
    state.tools["llm_cli"] = True


def _install_fabric(profile, decision, state, prefs, console):
    if shutil.which("fabric-ai"):
        console.print("  [dim]fabric-ai already installed.[/dim]")
        state.tools["fabric"] = True
        return

    _run_cmd(["pip3", "install", "fabric-ai"], console)
    state.tools["fabric"] = True


def _install_msty(profile, decision, state, prefs, console):
    if profile.os_type == "macOS" and _has_brew():
        # Check if already installed
        result = subprocess.run(
            ["brew", "list", "--cask", "mstystudio"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            console.print("  [dim]Msty Studio already installed.[/dim]")
            state.tools["msty"] = True
            return
        _run_cmd(["brew", "install", "--cask", "mstystudio"], console)
    else:
        console.print("  [yellow]Install Msty Studio manually from https://msty.app[/yellow]")
    state.tools["msty"] = True


def _install_anythingllm(profile, decision, state, prefs, console):
    if profile.os_type == "macOS" and _has_brew():
        result = subprocess.run(
            ["brew", "list", "--cask", "anythingllm"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            console.print("  [dim]AnythingLLM already installed.[/dim]")
            state.tools["anythingllm"] = True
            return
        _run_cmd(["brew", "install", "--cask", "anythingllm"], console)
    elif profile.os_type == "Linux":
        console.print("  [dim]AnythingLLM on Linux: clone from GitHub and build.[/dim]")
        console.print("  [dim]See https://github.com/Mintplex-Labs/anything-llm[/dim]")
    else:
        console.print("  [yellow]Install AnythingLLM manually from https://anythingllm.com[/yellow]")
    state.tools["anythingllm"] = True


def _configure_runtime(profile, decision, state, prefs, console):
    """Configure runtime with model paths and settings."""
    if decision.runtime == "lm-studio" and shutil.which("lms"):
        # Ensure LM Studio server is loadable
        console.print("  [dim]LM Studio configured. Start it manually or via 'lms server start'.[/dim]")
    elif decision.runtime == "ollama" and shutil.which("ollama"):
        console.print("  [dim]Ollama configured. Models available via 'ollama list'.[/dim]")


def _configure_aliases(profile, decision, state, prefs, console):
    """Add shell aliases for quick LLM access."""
    shell_rc = _get_shell_rc(profile)
    if not shell_rc:
        console.print("  [yellow]Could not detect shell config file — skipping aliases.[/yellow]")
        return

    marker = "# === ANKYLOSAURUS ==="
    try:
        content = shell_rc.read_text()
    except FileNotFoundError:
        content = ""

    if marker in content:
        console.print("  [dim]Aliases already configured.[/dim]")
        return

    # Build alias block based on installed tools
    lines = [f"\n{marker}"]
    if state.tools.get("llm_cli"):
        lines.append('alias q="llm"')
    if state.tools.get("fabric"):
        lines.append("alias fabric='fabric-ai'")
        lines.append("alias summarize='fabric-ai -p summarize'")
        lines.append("alias explain='fabric-ai -p explain_code'")
    lines.append("# === END ANKYLOSAURUS ===\n")

    shell_rc.write_text(content + "\n".join(lines))
    console.print(f"  [dim]Aliases added to {shell_rc}[/dim]")


def _get_shell_rc(profile: HardwareProfile) -> Path | None:
    home = Path.home()
    if profile.os_type == "Windows":
        return None  # PowerShell profile needs special handling
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"
    if zshrc.exists():
        return zshrc
    if bashrc.exists():
        return bashrc
    return zshrc  # default to zsh on macOS


def _get_version(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
