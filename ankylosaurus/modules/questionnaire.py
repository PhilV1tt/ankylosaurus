"""Interactive questionnaire to capture user preferences."""

from __future__ import annotations

import secrets
import sys
from dataclasses import dataclass, field
from .detect import HardwareProfile


@dataclass
class UserPreferences:
    usage: str              # "code" | "studies" | "writing" | "general"
    features: list[str]     # ["chat", "rag", "notes", "agents"]
    disk_budget_gb: int
    want_gui: bool
    language: str           # "en" | "fr" | "multi"
    battery_mode: bool
    personas: list[str] = field(default_factory=list)
    webui_name: str = ""
    webui_email: str = ""
    webui_password: str = field(default="", repr=False)  # ephemeral — never persist


def _ask(question, default=None):
    """Wrap questionary .ask() with Ctrl-C safety."""
    result = question.ask()
    if result is None:
        if default is not None:
            return default
        print("\nAborted.")
        sys.exit(130)
    return result


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
            webui_name="admin",
            webui_email="admin@localhost",
            webui_password=secrets.token_urlsafe(16),
        )

    import questionary
    from questionary import Style

    style = Style([
        ("qmark", "fg:#e66414 bold"),
        ("question", "bold"),
        ("pointer", "fg:#e66414 bold"),
        ("highlighted", "fg:#ffd028 bold"),
        ("selected", "fg:#e66414"),
        ("answer", "fg:#e66414 bold"),
        ("checkbox", "fg:#e66414"),
        ("checkbox-selected", "fg:#e66414 bold"),
    ])

    console.print("\n[bold cyan]Configuration[/bold cyan]\n")

    usage = _ask(questionary.select(
        "Primary usage:",
        choices=["general", "code", "studies", "writing"],
        default="general",
        style=style,
    ), default="general")

    features = _ask(questionary.checkbox(
        "Features:",
        choices=[
            questionary.Choice("chat", checked=True),
            questionary.Choice("rag", checked=True),
            questionary.Choice("notes"),
            questionary.Choice("agents"),
        ],
        style=style,
    ), default=["chat"])
    if not features:
        features = ["chat"]

    max_disk = min(int(profile.disk_free_gb * 0.5), 100)
    disk_budget = _ask(questionary.text(
        f"Disk budget for models in GB (max ~{max_disk}):",
        default=str(min(30, max_disk)),
        validate=lambda v: v.isdigit() and 0 < int(v) <= max_disk,
        style=style,
    ), default=str(min(30, max_disk)))
    disk_budget = int(disk_budget)

    want_gui = _ask(questionary.confirm(
        "Install GUI apps (Open WebUI, AnythingLLM)?",
        default=True,
        style=style,
    ), default=True)

    webui_name = ""
    webui_email = ""
    webui_password = ""
    if want_gui:
        console.print("\n[bold cyan]Open WebUI account[/bold cyan]")
        webui_name = _ask(questionary.text(
            "Display name:",
            default="admin",
            style=style,
        ), default="admin")
        webui_email = _ask(questionary.text(
            "Email:",
            default="admin@localhost",
            style=style,
        ), default="admin@localhost")
        webui_password = _ask(questionary.password(
            "Password:",
            style=style,
        ), default="")
        if not webui_password:
            webui_password = secrets.token_urlsafe(16)
            console.print(f"  [dim]Generated password: {webui_password}[/dim]")

    language = _ask(questionary.select(
        "Primary language:",
        choices=["multi", "en", "fr"],
        default="multi",
        style=style,
    ), default="multi")

    battery_mode = False
    if profile.os_type == "macOS":
        battery_mode = _ask(questionary.confirm(
            "Optimize for battery life?",
            default=False,
            style=style,
        ), default=False)

    # Persona selection
    from .personas import BUILTIN_PERSONAS

    persona_choices = [
        questionary.Choice(
            f"{name} ({data['language']})",
            value=name,
            checked=True,
        )
        for name, data in BUILTIN_PERSONAS.items()
    ]

    selected_personas = _ask(questionary.checkbox(
        "Personas to install:",
        choices=persona_choices,
        style=style,
    ), default=list(BUILTIN_PERSONAS.keys()))

    return UserPreferences(
        usage=usage,
        features=features,
        disk_budget_gb=disk_budget,
        want_gui=want_gui,
        language=language,
        battery_mode=battery_mode,
        personas=selected_personas,
        webui_name=webui_name,
        webui_email=webui_email,
        webui_password=webui_password,
    )
