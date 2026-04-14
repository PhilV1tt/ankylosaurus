"""Extension menu - MCP servers, fabric patterns, additional tools."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

from .state import InstallState, save_state


def show_extension_menu(state: InstallState, console: Console) -> None:
    """Interactive extension picker."""
    console.print("\n[bold cyan]Extensions[/bold cyan]\n")

    categories = [
        ("MCP Servers", _mcp_menu),
        ("Fabric Patterns", _fabric_menu),
        ("Obsidian Plugins", _obsidian_menu),
        ("Additional Tools", _tools_menu),
    ]

    for name, func in categories:
        if Confirm.ask(f"Browse {name}?", default=False):
            func(state, console)

    save_state(state)


def _mcp_menu(state: InstallState, console: Console) -> None:
    servers = _fetch_mcp_servers()
    if not servers:
        console.print("[yellow]Could not fetch MCP server list.[/yellow]")
        return

    table = Table(title="MCP Servers", border_style="dim")
    table.add_column("#", style="bold")
    table.add_column("Name")
    table.add_column("Description")

    for i, s in enumerate(servers):
        table.add_row(str(i + 1), s["name"], s["description"])

    console.print(table)
    choices = Prompt.ask("Install which? (comma-separated numbers, 0 to skip)", default="0")

    for num_str in choices.split(","):
        num_str = num_str.strip()
        if not num_str.isdigit() or int(num_str) == 0:
            continue
        idx = int(num_str) - 1
        if 0 <= idx < len(servers):
            name = servers[idx]["name"]
            pkg = servers[idx]["package"]
            console.print(f"  Installing [bold]{name}[/bold]...")
            try:
                import subprocess
                result = subprocess.run(["npm", "install", "-g", pkg],
                                        capture_output=True, text=True)
                if result.returncode == 0:
                    state.extensions["mcp"].append(name)
                    console.print(f"  [green]✓ {name}[/green]")
                else:
                    console.print(f"  [red]✗ {name}: install failed[/red]")
            except Exception as e:
                console.print(f"  [red]✗ {name}: {e}[/red]")


import time as _time
import threading as _threading

_mcp_cache: tuple[float, list[dict]] | None = None
_MCP_CACHE_TTL = 300  # 5 minutes


def _fetch_mcp_servers() -> list[dict]:
    """Fetch MCP server list from GitHub registry (cached with TTL)."""
    global _mcp_cache
    if _mcp_cache and (_time.monotonic() - _mcp_cache[0]) < _MCP_CACHE_TTL:
        return _mcp_cache[1]
    try:
        import httpx
        resp = httpx.get(
            "https://api.github.com/repos/modelcontextprotocol/servers/contents/src",
            timeout=5,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        if resp.status_code != 200:
            return _fallback_mcp_list()

        entries = resp.json()
        servers = []
        for entry in entries:
            if entry.get("type") == "dir":
                name = entry["name"]
                servers.append({
                    "name": name,
                    "description": f"MCP {name} server",
                    "package": f"@modelcontextprotocol/server-{name}",
                })
        result = servers[:20]
        _mcp_cache = (_time.monotonic(), result)
        return result
    except Exception:
        return _fallback_mcp_list()


def _fallback_mcp_list() -> list[dict]:
    """Minimal fallback if GitHub API is unreachable."""
    names = ["filesystem", "memory", "brave-search", "sequential-thinking", "fetch"]
    return [
        {"name": n, "description": f"MCP {n} server",
         "package": f"@modelcontextprotocol/server-{n}"}
        for n in names
    ]


FABRIC_PATTERNS = [
    ("summarize", "Summarize a text"),
    ("extract_wisdom", "Extract key ideas"),
    ("explain_code", "Explain code step by step"),
    ("create_quiz", "Generate a quiz"),
    ("write_essay", "Draft an essay"),
    ("analyze_claims", "Analyze arguments"),
    ("improve_writing", "Improve text quality"),
    ("create_flashcards", "Generate flashcards"),
    ("rate_value", "Evaluate an idea"),
    ("ask_uncle_duke", "Direct advice, no filter"),
]


def _fabric_menu(state: InstallState, console: Console) -> None:
    import subprocess
    import shutil
    if not shutil.which("fabric-ai"):
        console.print("[yellow]fabric-ai not installed - skipping.[/yellow]")
        return

    table = Table(title="Fabric Patterns", border_style="dim")
    table.add_column("#", style="bold")
    table.add_column("Pattern")
    table.add_column("Description")

    for i, (name, desc) in enumerate(FABRIC_PATTERNS):
        table.add_row(str(i + 1), name, desc)

    console.print(table)
    choices = Prompt.ask("Install which? (comma-separated, 0 to skip, 'all' for all)", default="all")

    if choices.strip().lower() == "all":
        selected = [name for name, _ in FABRIC_PATTERNS]
    else:
        selected = []
        for num_str in choices.split(","):
            num_str = num_str.strip()
            if num_str.isdigit() and 1 <= int(num_str) <= len(FABRIC_PATTERNS):
                selected.append(FABRIC_PATTERNS[int(num_str) - 1][0])

    if not selected:
        return

    console.print("  Updating fabric patterns (background)...")

    def _update():
        r = subprocess.run(
            ["fabric-ai", "--updatepatterns"], capture_output=True, text=True
        )
        if r.returncode == 0:
            state.extensions["fabric_patterns"] = selected
            console.print(f"  [green]✓ {len(selected)} patterns configured[/green]")
        else:
            console.print(f"  [yellow]Pattern update failed: {r.stderr[:100]}[/yellow]")

    _threading.Thread(target=_update, daemon=True).start()


OBSIDIAN_PLUGINS = [
    ("copilot", "Copilot", "Chat with vault + flashcards"),
    ("smart-connections", "Smart Connections", "Semantic links auto"),
    ("note-companion", "Note Companion", "Auto-organize notes"),
    ("templater-obsidian", "Templater", "Dynamic templates"),
    ("dataview", "Dataview", "SQL-like queries on vault"),
]


def _obsidian_menu(state: InstallState, console: Console) -> None:
    table = Table(title="Obsidian Plugins", border_style="dim")
    table.add_column("#", style="bold")
    table.add_column("Plugin")
    table.add_column("Description")

    for i, (_, name, desc) in enumerate(OBSIDIAN_PLUGINS):
        table.add_row(str(i + 1), name, desc)

    console.print(table)
    console.print("[dim]Obsidian plugins must be installed from within Obsidian.[/dim]")
    choices = Prompt.ask("Note which for guide? (comma-separated, 0 to skip, 'all' for all)", default="0")

    if choices.strip().lower() == "all":
        selected = [pid for pid, _, _ in OBSIDIAN_PLUGINS]
    else:
        selected = []
        for num_str in choices.split(","):
            num_str = num_str.strip()
            if num_str.isdigit() and 1 <= int(num_str) <= len(OBSIDIAN_PLUGINS):
                selected.append(OBSIDIAN_PLUGINS[int(num_str) - 1][0])

    if selected:
        state.extensions["obsidian"] = selected
        console.print(f"  [green]✓ {len(selected)} plugins noted - install guide in GUIDE.md[/green]")


def _tools_menu(state: InstallState, console: Console) -> None:
    import platform
    is_mac = platform.system() == "Darwin"

    tools = []
    if is_mac:
        tools.append(("Raycast AI", "raycast", "brew install --cask raycast"))
    tools.append(("Obsidian", "obsidian",
                  "brew install --cask obsidian" if is_mac else "flatpak install flathub md.obsidian.Obsidian"))

    if not tools:
        console.print("  [dim]No additional tools available for this platform.[/dim]")
        return

    table = Table(title="Additional Tools", border_style="dim")
    table.add_column("#", style="bold")
    table.add_column("Tool")

    for i, (name, _, _) in enumerate(tools):
        table.add_row(str(i + 1), name)

    console.print(table)
    choices = Prompt.ask("Install which? (comma-separated, 0 to skip)", default="0")

    for num_str in choices.split(","):
        num_str = num_str.strip()
        if not num_str.isdigit() or int(num_str) == 0:
            continue
        idx = int(num_str) - 1
        if 0 <= idx < len(tools):
            name, key, cmd = tools[idx]
            console.print(f"  Installing [bold]{name}[/bold]...")
            try:
                import shlex
                import subprocess
                subprocess.run(shlex.split(cmd), check=True, capture_output=True, text=True)
                state.extensions["tools"].append(key)
                console.print(f"  [green]✓ {name}[/green]")
            except Exception as e:
                console.print(f"  [red]✗ {name}: {e}[/red]")
