"""TUI install wizard - 5-screen flow inside the Textual app."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button, Checkbox, Input, Label, ProgressBar, Select, Static,
)
from textual.widget import Widget


# ---------------------------------------------------------------------------
# Screen 1: Welcome - hardware auto-detection
# ---------------------------------------------------------------------------

class WelcomeScreen(Static):
    """Auto-detect hardware and show results."""

    def __init__(self) -> None:
        super().__init__()
        self._hw: dict = {}

    def compose(self) -> ComposeResult:
        yield Label("[bold #e66414]  Welcome to Ankylosaurus[/]\n")
        yield Label("  Detecting your hardware...\n", id="hw-status")
        yield Label("", id="hw-details")
        yield Label("")
        yield Button("Continue", id="wizard-next", variant="primary")

    def on_mount(self) -> None:
        self._detect()

    def _detect(self) -> None:
        from .modules.detect import detect_hardware
        profile = detect_hardware()
        self._hw = {
            "os": profile.os_type,
            "cpu": profile.cpu_brand,
            "gpu": profile.gpu_name or "None",
            "ram_gb": profile.ram_total_gb,
            "disk_free_gb": profile.disk_free_gb,
        }
        self.app._wizard_hw_profile = profile  # type: ignore[attr-defined]

        status = self.query_one("#hw-status", Label)
        status.update("[green]  Hardware detected[/]\n")

        details = self.query_one("#hw-details", Label)
        details.update(
            f"  [#999]OS[/]      {self._hw['os']}\n"
            f"  [#999]CPU[/]     {self._hw['cpu']}\n"
            f"  [#999]GPU[/]     {self._hw['gpu']}\n"
            f"  [#999]RAM[/]     {self._hw['ram_gb']} GB\n"
            f"  [#999]Disk[/]    {self._hw['disk_free_gb']:.0f} GB free"
        )


# ---------------------------------------------------------------------------
# Screen 2: Profile - who are you?
# ---------------------------------------------------------------------------

DOMAIN_OPTIONS = [
    ("science", "Science & Math"),
    ("code", "Programming"),
    ("writing", "Writing"),
    ("notes", "Notes & Knowledge"),
    ("research", "Academic Research"),
    ("music", "Music"),
    ("sports", "Sports & Fitness"),
    ("health", "Health & Nutrition"),
    ("aviation", "Aviation"),
    ("automotive", "Automotive"),
    ("data", "Data Analysis"),
    ("freelance", "Freelance & Business"),
    ("tech", "Tech Watch & AI"),
    ("debate", "Philosophy & Debate"),
]


class ProfileScreen(Static):
    """User profiling: occupation, domains, language."""

    def compose(self) -> ComposeResult:
        yield Label("[bold #e66414]  About you[/]\n")

        yield Label("  Occupation:")
        yield Select(
            [(v, k) for k, v in [
                ("student", "Student"),
                ("developer", "Developer / Engineer"),
                ("researcher", "Researcher"),
                ("freelancer", "Freelancer"),
                ("other", "Other"),
            ]],
            id="occupation",
            value="other",
        )

        yield Label("\n  Your interests:")
        for key, label in DOMAIN_OPTIONS:
            yield Checkbox(label, id=f"domain-{key}")

        yield Label("\n  Primary language:")
        yield Select(
            [("English", "en"), ("Francais", "fr"), ("Auto-detect", "multi")],
            id="language",
            value="en",
        )

        yield Label("\n  Disk budget for models (GB):")
        yield Input(value="30", id="disk-budget", type="integer")

        yield Label("\n  Install GUI (Open WebUI)?")
        yield Checkbox("Yes, install Open WebUI", id="want-gui", value=True)

        yield Label("")
        yield Button("Continue", id="wizard-next", variant="primary")

    def get_profile_data(self) -> dict:
        """Extract form values."""
        occupation = self.query_one("#occupation", Select).value
        domains = []
        for key, _ in DOMAIN_OPTIONS:
            cb = self.query_one(f"#domain-{key}", Checkbox)
            if cb.value:
                domains.append(key)
        language = self.query_one("#language", Select).value
        disk = self.query_one("#disk-budget", Input).value
        want_gui = self.query_one("#want-gui", Checkbox).value

        return {
            "occupation": occupation or "other",
            "domains": domains,
            "language": language or "en",
            "disk_budget": int(disk) if disk.isdigit() else 30,
            "want_gui": want_gui,
        }


# ---------------------------------------------------------------------------
# Screen 3: Preview - selected personas
# ---------------------------------------------------------------------------

class PreviewScreen(Static):
    """Show generated personas, let user toggle them."""

    def __init__(self, personas: list[tuple[str, str, bool]]) -> None:
        super().__init__()
        self._personas = personas  # [(id, display_name, active)]

    def compose(self) -> ComposeResult:
        yield Label("[bold #e66414]  Your personas[/]\n")
        yield Label("  [dim]Toggle personas on/off before installing.[/]\n")

        for pid, name, active in self._personas:
            yield Checkbox(f"{pid} - {name}", id=f"persona-{pid}", value=active)

        yield Label("")
        yield Button("Install", id="wizard-next", variant="primary")

    def get_selected(self) -> list[str]:
        selected = []
        for pid, _, _ in self._personas:
            cb = self.query_one(f"#persona-{pid}", Checkbox)
            if cb.value:
                selected.append(pid)
        return selected


# ---------------------------------------------------------------------------
# Screen 4: Install - progress
# ---------------------------------------------------------------------------

class InstallScreen(Static):
    """Live install progress."""

    def compose(self) -> ComposeResult:
        yield Label("[bold #e66414]  Installing...[/]\n")
        yield Label("", id="install-step")
        yield ProgressBar(id="install-progress", total=100, show_eta=False)
        yield Label("", id="install-log")

    def update_step(self, step: str, pct: int) -> None:
        self.query_one("#install-step", Label).update(f"  [bold]{step}[/]")
        self.query_one("#install-progress", ProgressBar).update(progress=pct)

    def append_log(self, msg: str) -> None:
        log = self.query_one("#install-log", Label)
        current = str(log.renderable) if log.renderable else ""
        # Keep last 10 lines
        lines = current.split("\n")
        lines.append(f"  [dim]{msg}[/]")
        log.update("\n".join(lines[-10:]))

    def show_done(self) -> None:
        self.query_one("#install-step", Label).update(
            "  [bold green]Installation complete![/]"
        )
        self.query_one("#install-progress", ProgressBar).update(progress=100)


# ---------------------------------------------------------------------------
# Screen 5: Done
# ---------------------------------------------------------------------------

class DoneScreen(Static):
    """Summary and quick-start."""

    def __init__(self, summary: dict) -> None:
        super().__init__()
        self._summary = summary

    def compose(self) -> ComposeResult:
        s = self._summary
        yield Label("[bold #e66414]  Setup complete![/]\n")

        yield Label(f"  [#999]Runtime[/]    {s.get('runtime', 'ollama')}")
        yield Label(f"  [#999]Models[/]     {s.get('model_count', 0)}")
        yield Label(f"  [#999]Personas[/]   {s.get('persona_count', 0)}")

        if s.get("gui_url"):
            yield Label(f"\n  [bold]Open WebUI:[/] {s['gui_url']}")

        yield Label("\n  [bold]Quick start:[/]")
        yield Label("    ollama run <model>")
        yield Label("    ankylosaurus run")
        if s.get("guide_path"):
            yield Label(f"\n  [dim]Full guide: {s['guide_path']}[/]")

        yield Label("")
        yield Button("Back to dashboard", id="wizard-done", variant="primary")
