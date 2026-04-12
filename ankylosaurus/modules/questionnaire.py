"""Interactive questionnaire to capture user preferences."""

from __future__ import annotations

from dataclasses import dataclass
from .detect import HardwareProfile


@dataclass
class UserPreferences:
    usage: str              # "code" | "studies" | "writing" | "general"
    features: list[str]     # ["chat", "rag", "notes", "agents"]
    disk_budget_gb: int
    want_gui: bool
    language: str           # "en" | "fr" | "multi"
    battery_mode: bool
    personas: list[str] = None

    def __post_init__(self):
        if self.personas is None:
            self.personas = []


def run_questionnaire(profile: HardwareProfile) -> UserPreferences:
    from rich.console import Console
    from rich.prompt import Prompt, IntPrompt, Confirm

    console = Console()
    console.print("\n[bold cyan]Configuration[/bold cyan]\n")

    usage = Prompt.ask(
        "Primary usage",
        choices=["code", "studies", "writing", "general"],
        default="general",
    )

    features_raw = Prompt.ask(
        "Features needed (comma-separated)",
        default="chat,rag",
    )
    features = [f.strip() for f in features_raw.split(",") if f.strip()]

    max_disk = min(int(profile.disk_free_gb * 0.5), 100)
    disk_budget = IntPrompt.ask(
        f"Disk budget for models (GB, max ~{max_disk})",
        default=min(30, max_disk),
    )

    want_gui = Confirm.ask("Install GUI apps (Msty, AnythingLLM)?", default=True)

    language = Prompt.ask(
        "Primary language",
        choices=["en", "fr", "multi"],
        default="multi",
    )

    battery_mode = False
    if profile.os_type == "macOS":
        battery_mode = Confirm.ask("Optimize for battery life?", default=False)

    # Persona selection
    from .personas import BUILTIN_PERSONAS
    console.print("\n[bold cyan]Personas[/bold cyan]")
    available = list(BUILTIN_PERSONAS.keys())
    for i, name in enumerate(available):
        desc = BUILTIN_PERSONAS[name]["system"][:60]
        console.print(f"  [bold]{i + 1}[/bold]. {name} — [dim]{desc}...[/dim]")

    personas_raw = Prompt.ask(
        "Install which personas? (comma-separated numbers, 'all', or 0 to skip)",
        default="all",
    )
    if personas_raw.strip().lower() == "all":
        selected_personas = list(available)
    else:
        selected_personas = []
        for num_str in personas_raw.split(","):
            num_str = num_str.strip()
            if num_str.isdigit() and int(num_str) > 0:
                idx = int(num_str) - 1
                if 0 <= idx < len(available):
                    selected_personas.append(available[idx])

    return UserPreferences(
        usage=usage,
        features=features,
        disk_budget_gb=disk_budget,
        want_gui=want_gui,
        language=language,
        battery_mode=battery_mode,
        personas=selected_personas,
    )
