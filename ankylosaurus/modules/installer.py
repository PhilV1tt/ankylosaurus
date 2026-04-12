"""Component installer with auto-resume via steps_completed."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
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
            if step_id in CRITICAL_STEPS:
                console.print("[yellow]You can re-run 'ankylosaurus install' to resume.[/yellow]")
                return state
            console.print("  [dim]Skipping — not critical.[/dim]")
            state.mark_step(step_id)  # mark as done to avoid retry loop

    console.print("\n[bold green]✓ Installation complete![/bold green]")
    return state


CRITICAL_STEPS = {"runtime_installed", "models_downloaded"}


def _build_steps(prefs: UserPreferences) -> list[tuple[str, str, callable]]:
    steps = [
        ("runtime_installed", "Install runtime", _install_runtime),
        ("models_downloaded", "Download models", _download_models),
        ("llm_cli_installed", "Install llm CLI", _install_llm_cli),
        ("fabric_installed", "Install fabric-ai", _install_fabric),
    ]
    if prefs.want_gui:
        steps.append(("openwebui_installed", "Install Open WebUI", _install_openwebui))
        steps.append(("openwebui_configured", "Configure Open WebUI", _configure_openwebui))
    if "rag" in prefs.features:
        steps.append(("anythingllm_installed", "Install AnythingLLM", _install_anythingllm))
    steps += [
        ("personas_installed", "Install personas", _install_personas),
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
            # Try ollama pull first (works for registry models)
            name = repo_id.split("/")[-1].lower()
            result = subprocess.run(
                ["ollama", "pull", name], capture_output=True, text=True
            )
            if result.returncode == 0:
                model["ollama_name"] = name
                console.print(f"  [green]Pulled {name} from Ollama registry[/green]")
                continue

        # Fallback: huggingface_hub download
        try:
            from huggingface_hub import snapshot_download
            local_dir = snapshot_download(repo_id)
            console.print(f"  [green]Downloaded {repo_id}[/green]")

            # Register GGUF in Ollama via Modelfile
            if decision.runtime == "ollama" and model.get("format") != "mlx":
                ollama_name = _register_in_ollama(local_dir, repo_id, console)
                if ollama_name:
                    model["ollama_name"] = ollama_name

        except Exception as e:
            err_str = str(e)
            if "restricted" in err_str or "gated" in err_str or "401" in err_str:
                console.print(f"  [yellow]{repo_id} requires HF authentication.[/yellow]")
                console.print("  [dim]Run: huggingface-cli login, then retry.[/dim]")
            else:
                console.print(f"  [yellow]Download failed for {repo_id}: {e}[/yellow]")
            console.print(f"  [dim]Manual: huggingface-cli download {repo_id}[/dim]")


def _register_in_ollama(local_dir: str, repo_id: str, console: Console) -> str | None:
    """Create an Ollama model from a downloaded GGUF file."""
    import tempfile
    local_path = Path(local_dir)

    # Find the largest .gguf file
    gguf_files = sorted(local_path.rglob("*.gguf"), key=lambda p: p.stat().st_size, reverse=True)
    if not gguf_files:
        console.print("  [dim]No .gguf file found — skipping Ollama registration.[/dim]")
        return None

    gguf_path = gguf_files[0]
    # Derive a short name: "author/model-name-GGUF" -> "model-name"
    ollama_name = repo_id.split("/")[-1].lower()
    for suffix in ["-gguf", "_gguf", "-q4", "-q6", "-q8"]:
        ollama_name = ollama_name.removesuffix(suffix)

    # Write Modelfile
    modelfile_content = f'FROM "{gguf_path}"\n'
    with tempfile.NamedTemporaryFile(mode="w", suffix=".Modelfile", delete=False) as f:
        f.write(modelfile_content)
        modelfile_path = f.name

    try:
        console.print(f"  Registering as [bold]{ollama_name}[/bold] in Ollama...")
        result = subprocess.run(
            ["ollama", "create", ollama_name, "-f", modelfile_path],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            console.print(f"  [green]Registered: ollama run {ollama_name}[/green]")
            return ollama_name
        else:
            console.print(f"  [yellow]Ollama create failed: {result.stderr.strip()[:150]}[/yellow]")
            console.print(f"  [dim]Manual: ollama create {ollama_name} -f <Modelfile>[/dim]")
            return None
    finally:
        Path(modelfile_path).unlink(missing_ok=True)


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
    if shutil.which("fabric-ai") or shutil.which("fabric"):
        console.print("  [dim]fabric already installed.[/dim]")
        state.tools["fabric"] = True
        return

    # Try pip first, fall back to pipx
    result = subprocess.run(
        ["pip3", "install", "fabric-ai"], capture_output=True, text=True
    )
    if result.returncode == 0:
        state.tools["fabric"] = True
        return

    if shutil.which("pipx"):
        result = subprocess.run(
            ["pipx", "install", "fabric-ai"], capture_output=True, text=True
        )
        if result.returncode == 0:
            state.tools["fabric"] = True
            return

    raise RuntimeError("fabric-ai not available via pip or pipx")


def _install_openwebui(profile, decision, state, prefs, console):
    if not shutil.which("docker"):
        console.print("  [yellow]Docker not found. Install Docker Desktop first.[/yellow]")
        state.tools["openwebui"] = False
        return

    # Check if container already exists
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=open-webui", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    if "open-webui" in result.stdout:
        console.print("  [dim]Open WebUI container already exists.[/dim]")
        # Ensure it's running
        subprocess.run(["docker", "start", "open-webui"], capture_output=True)
        state.tools["openwebui"] = True
        return

    # Build env vars based on runtime
    docker_host = "host.docker.internal"
    host_gateway_args = []
    if profile.os_type != "macOS":
        host_gateway_args = ["--add-host", "host.docker.internal:host-gateway"]

    env_args = []
    if decision.runtime == "lm-studio":
        env_args += [
            "-e", f"OPENAI_API_BASE_URL=http://{docker_host}:1234/v1",
            "-e", "OPENAI_API_KEY=lm-studio",
        ]
    else:
        env_args += [
            "-e", f"OLLAMA_BASE_URL=http://{docker_host}:11434",
        ]

    _run_cmd([
        "docker", "run", "-d",
        "--name", "open-webui",
        "-p", "3000:8080",
        *host_gateway_args,
        *env_args,
        "-v", "open-webui:/app/backend/data",
        "--restart", "unless-stopped",
        "ghcr.io/open-webui/open-webui:latest",
    ], console)
    console.print("  [green]Open WebUI available at http://localhost:3000[/green]")
    state.tools["openwebui"] = True


def _pick_base_models(state: InstallState) -> tuple[str, str]:
    """Pick best reasoning and chat base models from installed models."""
    model_ids = [m.get("repo_id", "").split("/")[-1].lower() for m in state.models]

    # Reasoning: prefer Qwen (has thinking), fallback to first available
    reasoning = "qwen3.5-9b-mlx"
    for m in state.models:
        name = m.get("repo_id", "").lower()
        if "qwen" in name and "9b" in name:
            reasoning = m.get("repo_id", "").split("/")[-1]
            break

    # Chat: prefer Gemma 26B-A4B (MoE, best quality), then E4B, fallback to reasoning
    chat = reasoning
    for m in state.models:
        name = m.get("repo_id", "").lower()
        if "gemma" in name and "26b" in name:
            chat = m.get("repo_id", "").split("/")[-1]
            break
    else:
        for m in state.models:
            name = m.get("repo_id", "").lower()
            if "gemma" in name and "e4b" in name:
                chat = m.get("repo_id", "").split("/")[-1]
                break

    return reasoning, chat


def _configure_openwebui(profile, decision, state, prefs, console):
    """Create admin account and personas in Open WebUI via API."""
    if not state.tools.get("openwebui"):
        console.print("  [dim]Open WebUI not installed — skipping configuration.[/dim]")
        return

    if not prefs.webui_email or not prefs.webui_password:
        console.print("  [yellow]No credentials provided — configure Open WebUI manually at http://localhost:3000[/yellow]")
        return

    base = "http://localhost:3000"

    # Wait for Open WebUI to be ready
    console.print("  Waiting for Open WebUI to start...")
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{base}/health", timeout=2)
            break
        except Exception:
            time.sleep(2)
    else:
        console.print("  [yellow]Open WebUI not responding — configure manually at http://localhost:3000[/yellow]")
        return

    name = prefs.webui_name or "admin"
    email = prefs.webui_email
    password = prefs.webui_password

    # 1. Create admin account (signup — first user becomes admin)
    token = None
    try:
        payload = json.dumps({"name": name, "email": email, "password": password}).encode()
        req = urllib.request.Request(
            f"{base}/api/v1/auths/signup",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            token = json.loads(resp.read()).get("token")
        console.print(f"  [green]Admin account created ({email})[/green]")
    except urllib.error.HTTPError:
        # Account may already exist — try signin
        try:
            payload = json.dumps({"email": email, "password": password}).encode()
            req = urllib.request.Request(
                f"{base}/api/v1/auths/signin",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:
                token = json.loads(resp.read()).get("token")
            console.print("  [dim]Admin account already exists — signed in.[/dim]")
        except Exception as e:
            console.print(f"  [yellow]Could not authenticate: {e}[/yellow]")
            return

    # Clear password from prefs now that we have a token
    prefs.webui_password = ""

    if not token:
        console.print("  [yellow]No auth token — skipping persona setup.[/yellow]")
        return

    # 2. Create personas from selected builtin personas
    from .personas import BUILTIN_PERSONAS, REASONING_PERSONAS

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    selected = prefs.personas if prefs.personas else list(BUILTIN_PERSONAS.keys())

    # Detect available models to pick best base for each persona type
    reasoning_model, chat_model = _pick_base_models(state)

    created = 0
    for persona_name in selected:
        persona = BUILTIN_PERSONAS.get(persona_name)
        if not persona:
            continue

        base_model = reasoning_model if persona_name in REASONING_PERSONAS else chat_model

        payload = json.dumps({
            "id": persona_name,
            "name": persona["name"].replace("-", " ").title(),
            "base_model_id": base_model,
            "meta": {"description": persona["system"][:80]},
            "params": {"system": persona["system"]},
        }).encode()

        try:
            req = urllib.request.Request(
                f"{base}/api/v1/models/create",
                data=payload,
                headers=headers,
            )
            urllib.request.urlopen(req)
            created += 1
        except urllib.error.HTTPError as e:
            if e.code not in (400, 401, 409, 422):  # 401=already exists in OWUI
                console.print(f"  [yellow]Persona '{persona_name}' failed (HTTP {e.code})[/yellow]")
        time.sleep(0.3)  # rate limit

    if created:
        console.print(f"  [green]{created} personas created in Open WebUI[/green]")
    else:
        console.print("  [dim]Personas already configured.[/dim]")


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


def _install_personas(profile, decision, state, prefs, console):
    """Install selected personas."""
    from .personas import install_builtin_personas
    selected = prefs.personas if prefs.personas else None
    install_builtin_personas(state, selected=selected)
    if state.personas:
        console.print(f"  [dim]Installed: {', '.join(state.personas)}[/dim]")
    else:
        console.print("  [dim]No personas selected.[/dim]")


def _configure_runtime(profile, decision, state, prefs, console):
    """Configure runtime with model paths and settings."""
    if decision.runtime == "lm-studio" and shutil.which("lms"):
        console.print("  [dim]LM Studio configured. Start it manually or via 'lms server start'.[/dim]")
    elif decision.runtime == "ollama" and shutil.which("ollama"):
        # Show registered models
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            console.print("  [dim]Ollama models:[/dim]")
            for line in result.stdout.strip().split("\n")[:5]:
                console.print(f"    [dim]{line}[/dim]")
        # Show quick-start hint
        for m in state.models:
            name = m.get("ollama_name", "")
            if name and m.get("role") == "chat":
                console.print(f"\n  [bold]Quick start: ollama run {name}[/bold]")
                console.print("  [bold]Or: ankylosaurus run \"your question\"[/bold]")
                break


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
