"""Interactive questionnaire to capture user preferences."""

from __future__ import annotations

import secrets
import sys
from dataclasses import dataclass, field
from .detect import HardwareProfile
from .decision import RuntimeDecision
from .personas import UserProfile, select_personas, generate_personas


# Available domain choices for the profiling step
DOMAIN_CHOICES = [
    ("science", "Science & Math"),
    ("code", "Programming"),
    ("writing", "Writing & Communication"),
    ("notes", "Notes & Knowledge Management"),
    ("research", "Academic Research"),
    ("music", "Music"),
    ("sports", "Sports & Fitness"),
    ("health", "Health & Nutrition"),
    ("aviation", "Aviation"),
    ("automotive", "Automotive & Mechanical"),
    ("data", "Data Analysis"),
    ("freelance", "Freelance & Business"),
    ("tech", "Tech Watch & AI"),
    ("debate", "Philosophy & Debate"),
]

# Occupation → implicit use_cases mapping
_OCCUPATION_USE_CASES = {
    "student": ["study"],
    "developer": ["code"],
    "researcher": ["research", "study"],
    "freelancer": ["code", "write"],
    "other": [],
}


@dataclass
class UserPreferences:
    usage: str              # "code" | "studies" | "writing" | "general"
    features: list[str]     # ["chat", "rag", "notes", "agents"]
    disk_budget_gb: int
    want_gui: bool
    language: str           # "en" | "fr" | "multi"
    battery_mode: bool
    gui_mode: str = ""      # "open-webui" | "ollama-cli" | "terminal"
    personas: list[str] = field(default_factory=list)
    profile: UserProfile = field(default_factory=UserProfile)
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


def _build_profile(occupation: str, domains: list[str], language: str) -> UserProfile:
    """Build a UserProfile from questionnaire answers."""
    use_cases = list(_OCCUPATION_USE_CASES.get(occupation, []))
    # Infer use_cases from domains
    if "writing" in domains or "notes" in domains:
        use_cases.append("write")
    if "notes" in domains:
        use_cases.append("organize")

    return UserProfile(
        occupation=occupation,
        domains=domains,
        languages=[language] if language != "multi" else ["en"],
        primary_language=language,
        use_cases=list(set(use_cases)),
    )


def run_questionnaire(
    profile: HardwareProfile,
    decision: RuntimeDecision | None = None,
    yes_mode: bool = False,
) -> UserPreferences:
    from rich.console import Console

    console = Console()

    if yes_mode:
        max_disk = min(int(profile.disk_free_gb * 0.5), 100)
        user_profile = UserProfile()  # defaults: no domains, English
        selected = select_personas(user_profile)
        persona_names = [t.id for t in selected]
        console.print("[dim]Non-interactive mode: using defaults.[/dim]")
        ui_mode = decision.ui if decision else "open-webui"
        want_gui = ui_mode == "open-webui"
        webui_name = "admin" if ui_mode == "open-webui" else ""
        webui_email = "admin@localhost" if ui_mode == "open-webui" else ""
        webui_password = secrets.token_urlsafe(16) if ui_mode == "open-webui" else ""
        return UserPreferences(
            usage="general",
            features=["chat", "rag"],
            disk_budget_gb=min(30, max_disk),
            want_gui=want_gui,
            language="multi",
            battery_mode=False,
            gui_mode=ui_mode,
            personas=persona_names,
            profile=user_profile,
            webui_name=webui_name,
            webui_email=webui_email,
            webui_password=webui_password,
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

    # --- User profiling ---
    console.print("\n[bold cyan]About you[/bold cyan]\n")

    occupation = _ask(questionary.select(
        "What do you do?",
        choices=[
            questionary.Choice("Student", value="student"),
            questionary.Choice("Developer / Engineer", value="developer"),
            questionary.Choice("Researcher", value="researcher"),
            questionary.Choice("Freelancer", value="freelancer"),
            questionary.Choice("Other", value="other"),
        ],
        default="other",
        style=style,
    ), default="other")

    domain_choices = [
        questionary.Choice(label, value=key)
        for key, label in DOMAIN_CHOICES
    ]
    domains = _ask(questionary.checkbox(
        "Your interests (select all that apply):",
        choices=domain_choices,
        style=style,
    ), default=[])

    language = _ask(questionary.select(
        "Primary language:",
        choices=["en", "fr", "multi"],
        default="en",
        style=style,
    ), default="en")

    user_profile = _build_profile(occupation, domains, language)

    # --- Configuration ---
    console.print("\n[bold cyan]Configuration[/bold cyan]\n")

    features = _ask(questionary.checkbox(
        "Features:",
        choices=[
            questionary.Choice("Chat", value="chat", checked=True),
            questionary.Choice("RAG (PDF Q&A)", value="rag", checked=True),
            questionary.Choice("Notes integration", value="notes"),
            questionary.Choice("Agents", value="agents"),
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

    # Smart GUI recommendation based on hardware detection
    if decision and decision.ui == "open-webui":
        gui_hint = "Docker detected — Open WebUI recommended"
    else:
        gui_hint = "Terminal mode (Ollama CLI)"

    gui_default = decision.ui == "open-webui" if decision else True
    want_gui = _ask(questionary.confirm(
        f"Install GUI? ({gui_hint})",
        default=gui_default,
        style=style,
    ), default=gui_default)

    gui_mode = ""
    if want_gui and decision:
        gui_mode = decision.ui
    elif not want_gui:
        gui_mode = "terminal"

    webui_name = ""
    webui_email = ""
    webui_password = ""
    if want_gui and gui_mode == "open-webui":
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

    battery_mode = False
    if profile.os_type == "macOS":
        battery_mode = _ask(questionary.confirm(
            "Optimize for battery life?",
            default=False,
            style=style,
        ), default=False)

    # --- Persona selection from profile ---
    selected_templates = select_personas(user_profile)
    persona_choices = [
        questionary.Choice(
            f"{t.id} — {t.name_tpl}",
            value=t.id,
            checked=True,
        )
        for t in selected_templates
    ]
    selected_personas = _ask(questionary.checkbox(
        "Personas to install:",
        choices=persona_choices,
        style=style,
    ), default=[t.id for t in selected_templates])

    # Map usage to the legacy field
    usage_map = {
        "student": "studies",
        "developer": "code",
        "researcher": "studies",
        "freelancer": "code",
        "other": "general",
    }

    return UserPreferences(
        usage=usage_map.get(occupation, "general"),
        features=features,
        disk_budget_gb=disk_budget,
        want_gui=want_gui,
        language=language,
        battery_mode=battery_mode,
        gui_mode=gui_mode,
        personas=selected_personas,
        profile=user_profile,
        webui_name=webui_name,
        webui_email=webui_email,
        webui_password=webui_password,
    )
