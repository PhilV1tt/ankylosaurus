"""Extension menu — MCP servers, fabric patterns, additional tools."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

from modules.state import InstallState, save_state


def show_extension_menu(state: InstallState, console: Console) -> None:
    """Interactive extension picker."""
    console.print("\n[bold cyan]Extensions[/bold cyan]\n")

    categories = [
        ("MCP Servers", _mcp_menu),
        ("Fabric Patterns", _fabric_menu),
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
                subprocess.run(["npm", "install", "-g", pkg], check=True,
                               capture_output=True, text=True)
                state.extensions["mcp"].append(name)
                console.print(f"  [green]✓ {name}[/green]")
            except Exception as e:
                console.print(f"  [red]✗ {name}: {e}[/red]")


def _fetch_mcp_servers() -> list[dict]:
    """Fetch MCP server list from GitHub registry."""
    try:
        import httpx
        resp = httpx.get(
            "https://api.github.com/repos/modelcontextprotocol/servers/contents/src",
            timeout=10,
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
        return servers[:20]
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


def _fabric_menu(state: InstallState, console: Console) -> None:
    import subprocess
    import shutil
    if not shutil.which("fabric-ai"):
        console.print("[yellow]fabric-ai not installed — skipping.[/yellow]")
        return

    console.print("  Updating fabric patterns...")
    result = subprocess.run(
        ["fabric-ai", "--updatepatterns"], capture_output=True, text=True
    )
    if result.returncode == 0:
        state.extensions["fabric_patterns"] = ["updated"]
        console.print("  [green]✓ Patterns updated[/green]")
    else:
        console.print(f"  [yellow]Pattern update failed: {result.stderr[:100]}[/yellow]")


def _tools_menu(state: InstallState, console: Console) -> None:
    tools = [
        ("Raycast AI", "raycast", "brew install --cask raycast"),
        ("Obsidian", "obsidian", "brew install --cask obsidian"),
    ]

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
                import subprocess
                subprocess.run(cmd.split(), check=True, capture_output=True, text=True)
                state.extensions["tools"].append(key)
                console.print(f"  [green]✓ {name}[/green]")
            except Exception as e:
                console.print(f"  [red]✗ {name}: {e}[/red]")
