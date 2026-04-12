"""Animated ANKYLOSAURUS splash text using Rich."""

from __future__ import annotations

import time

TITLE = "ANKYLOSAURUS"
VERSION = "1.0"
HEADER = f"🦕 ANKYLOSAURUS v{VERSION} — local-llm-setup"

# Gradient palette: orange-red → dark orange → gold → near-black
PALETTE = [
    (255, 69, 0),    # orange-red
    (255, 120, 0),   # mid orange
    (255, 140, 0),   # dark orange
    (255, 180, 0),   # amber
    (255, 200, 0),   # gold
    (200, 150, 0),   # dim gold
    (120, 80, 0),    # brown
    (40, 40, 40),    # near-black
]


def _interpolate(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _color_at(position: float) -> tuple[int, int, int]:
    """Get color from palette at a normalized position [0, 1)."""
    n = len(PALETTE)
    scaled = position * (n - 1)
    idx = int(scaled)
    frac = scaled - idx
    if idx >= n - 1:
        return PALETTE[-1]
    return _interpolate(PALETTE[idx], PALETTE[idx + 1], frac)


def _build_frame(tick: int, total_ticks: int) -> "Text":
    from rich.text import Text

    text = Text(TITLE, justify="center")
    wave_speed = 2.0
    offset = tick / total_ticks * wave_speed

    for i in range(len(TITLE)):
        pos = ((i / len(TITLE)) + offset) % 1.0
        r, g, b = _color_at(pos)
        text.stylize(f"bold rgb({r},{g},{b})", i, i + 1)

    return text


def show_splash(duration: float = 1.5) -> None:
    """Display animated ANKYLOSAURUS text, then print header."""
    try:
        from rich.live import Live
        from rich.console import Console
        from rich.text import Text

        console = Console()
        total_frames = 24
        interval = duration / total_frames

        with Live(console=console, refresh_per_second=20, transient=True) as live:
            for tick in range(total_frames):
                frame = _build_frame(tick, total_frames)
                live.update(frame)
                time.sleep(interval)

        console.print(Text(HEADER, justify="center", style="bold"))
        console.print()

    except ImportError:
        _fallback_splash()


def _fallback_splash() -> None:
    print(f"\n  {TITLE}\n  {HEADER}\n")


if __name__ == "__main__":
    show_splash()
