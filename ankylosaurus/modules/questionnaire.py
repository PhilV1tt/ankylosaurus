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


def run_questionnaire(profile: HardwareProfile, yes_mode: bool = False) -> UserPreferences:
    from rich.console import Console

    console = Console()

    if yes_mode:
        max_disk = min(int(profile.disk_free_gb * 0.5), 100)
        from .personas import BUILTIN_PERSONAS
        console.print("[dim]Non-interactive mode: using defaults.[/dim]")
        return UserPreferences(
            usage="general",
            features=["chat", "rag"],
            disk_budget_gb=min(30, max_disk),
            want_gui=True,
            language="multi",
            battery_mode=False,
            personas=list(BUILTIN_PERSONAS.keys()),
        )

    import questionary
    from questionary import Style

    style = Style([
        ("qmark", "fg:cyan bold"),
        ("question", "bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("answer", "fg:green bold"),
    ])

    console.print("\n[bold cyan]Configuration[/bold cyan]\n")

    usage = questionary.select(
        "Primary usage:",
        choices=["general", "code", "studies", "writing"],
        default="general",
        style=style,
    ).ask()

    features = questionary.checkbox(
        "Features:",
        choices=[
            questionary.Choice("chat", checked=True),
            questionary.Choice("rag", checked=True),
            questionary.Choice("notes"),
            questionary.Choice("agents"),
        ],
        style=style,
    ).ask()
    if not features:
        features = ["chat"]

    max_disk = min(int(profile.disk_free_gb * 0.5), 100)
    disk_budget = questionary.text(
        f"Disk budget for models in GB (max ~{max_disk}):",
        default=str(min(30, max_disk)),
        validate=lambda v: v.isdigit() and 0 < int(v) <= max_disk,
        style=style,
    ).ask()
    disk_budget = int(disk_budget)

    want_gui = questionary.confirm(
        "Install GUI apps (Msty, AnythingLLM)?",
        default=True,
        style=style,
    ).ask()

    language = questionary.select(
        "Primary language:",
        choices=["multi", "en", "fr"],
        default="multi",
        style=style,
    ).ask()

    battery_mode = False
    if profile.os_type == "macOS":
        battery_mode = questionary.confirm(
            "Optimize for battery life?",
            default=False,
            style=style,
        ).ask()

    # Persona selection
    from .personas import BUILTIN_PERSONAS

    persona_choices = [
        questionary.Choice(
            f"{name} -- {data['system'][:50]}...",
            value=name,
            checked=True,
        )
        for name, data in BUILTIN_PERSONAS.items()
    ]

    selected_personas = questionary.checkbox(
        "Personas to install:",
        choices=persona_choices,
        style=style,
    ).ask()
    if selected_personas is None:
        selected_personas = []

    return UserPreferences(
        usage=usage,
        features=features,
        disk_budget_gb=disk_budget,
        want_gui=want_gui,
        language=language,
        battery_mode=battery_mode,
        personas=selected_personas,
    )
