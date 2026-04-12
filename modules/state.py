"""InstallState — single source of truth for ANKYLOSAURUS installations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path.home() / ".ankylosaurus" / "install_state.json"


@dataclass
class InstallState:
    hardware: dict = field(default_factory=dict)
    runtime: str = ""                          # "lm-studio" | "ollama"
    runtime_version: str = ""
    models: list[dict] = field(default_factory=list)
    tools: dict = field(default_factory=dict)   # {llm_cli: bool, fabric: bool, ...}
    extensions: dict = field(default_factory=lambda: {
        "mcp": [], "fabric_patterns": [], "obsidian": [], "tools": [],
    })
    personas: list[str] = field(default_factory=list)
    preferences: dict = field(default_factory=dict)
    steps_completed: list[str] = field(default_factory=list)
    installed_at: str = ""
    last_updated: str = ""

    def mark_step(self, step_id: str) -> None:
        if step_id not in self.steps_completed:
            self.steps_completed.append(step_id)
            self.last_updated = datetime.now(timezone.utc).isoformat()
            save_state(self)

    def is_done(self, step_id: str) -> bool:
        return step_id in self.steps_completed


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_exists() -> bool:
    return STATE_FILE.exists()


def load_state() -> InstallState:
    if not STATE_FILE.exists():
        return InstallState(installed_at=_now_iso(), last_updated=_now_iso())
    data = json.loads(STATE_FILE.read_text())
    return InstallState(**{k: v for k, v in data.items() if k in InstallState.__dataclass_fields__})


def save_state(state: InstallState) -> None:
    state.last_updated = _now_iso()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(asdict(state), indent=2, ensure_ascii=False))
