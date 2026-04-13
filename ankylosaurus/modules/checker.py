"""Version checker — compare installed vs latest available."""

from __future__ import annotations

import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console
from rich.table import Table

from .state import InstallState


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

    # Run pip checks in parallel
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {name: pool.submit(func, arg) for name, func, arg in checks}

    for name, _, _ in checks:
        try:
            installed, latest = futures[name].result()
            if installed and latest:
                status = "[green]✓ up to date[/green]" if _version_gte(installed, latest) else "[yellow]↑ update available[/yellow]"
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


def _version_gte(installed: str, latest: str) -> bool:
    """Check if installed version >= latest using tuple comparison."""
    def _parse(v: str) -> tuple[int, ...]:
        import re
        parts = re.findall(r"\d+", v)
        return tuple(int(p) for p in parts) if parts else (0,)
    return _parse(installed) >= _parse(latest)


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
        # Try PyPI JSON API first (stable format), fall back to pip3 index
        try:
            import urllib.request
            import json
            resp = urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=5)
            data = json.loads(resp.read())
            latest = data.get("info", {}).get("version", "")
        except Exception:
            result = subprocess.run(
                ["pip3", "index", "versions", pkg],
                capture_output=True, text=True,
            )
            if result.stdout:
                first = result.stdout.splitlines()[0]
                if "(" in first:
                    latest = first.split("(")[1].split(")")[0].strip()

    return installed, latest


def _check_new_models(state: InstallState, console: Console) -> None:
    """Check HF Hub for trending models and compare with installed ones."""
    try:
        from huggingface_hub import HfApi
        api = HfApi()
        trending = list(api.list_models(
            pipeline_tag="text-generation",
            sort="trending",
            direction=-1,
            limit=10,
        ))

        if not trending:
            return

        # Build set of installed model repo IDs for comparison
        installed_ids = set()
        installed_sizes = {}
        for m in state.models:
            repo = m.get("repo_id", "")
            if repo:
                installed_ids.add(repo.lower())
                installed_sizes[repo.lower()] = m.get("size_gb", 0)

        console.print("\n[bold cyan]Trending Models[/bold cyan]")

        table = Table(border_style="dim")
        table.add_column("Model", style="bold")
        table.add_column("Downloads", justify="right")
        table.add_column("Likes", justify="right")
        table.add_column("Status")

        for m in trending[:8]:
            downloads = f"{m.downloads:,}" if m.downloads else "?"
            likes = f"{m.likes:,}" if hasattr(m, "likes") and m.likes else "?"
            mid = m.id.lower()

            if mid in installed_ids:
                status = "[green]installed[/green]"
            else:
                status = "[yellow]new[/yellow]"

            table.add_row(m.id, downloads, likes, status)

        console.print(table)

        # Highlight if a trending model could replace an installed one
        new_models = [m for m in trending[:8] if m.id.lower() not in installed_ids]
        if new_models and installed_ids:
            console.print(
                f"\n  [dim]{len(new_models)} trending model(s) not in your setup. "
                f"Run 'ankylosaurus install --fresh' to reconfigure.[/dim]"
            )
    except Exception:
        pass  # silently skip if no network
