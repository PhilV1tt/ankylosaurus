"""Animated ANKYLOSAURUS splash text using Rich."""

from __future__ import annotations

import time

from . import __version__

HEADER = "ANKYLOSAURUS v{} -- local-llm-setup".format(__version__)

# Gradient palette: dark green -> green -> yellow/brown -> dark
PALETTE = [
    (30, 80, 30),
    (50, 120, 50),
    (70, 140, 70),
    (120, 140, 50),
    (180, 140, 60),
    (160, 120, 40),
    (100, 80, 30),
    (40, 40, 40),
]


def _interpolate(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _color_at(position: float) -> tuple[int, int, int]:
    n = len(PALETTE)
    scaled = position * (n - 1)
    idx = int(scaled)
    frac = scaled - idx
    if idx >= n - 1:
        return PALETTE[-1]
    return _interpolate(PALETTE[idx], PALETTE[idx + 1], frac)


def _build_frame(tick: int, total_ticks: int):
    from rich.text import Text

    title = "ANKYLOSAURUS"
    text = Text(title, justify="center")
    wave_speed = 2.0
    offset = tick / total_ticks * wave_speed

    for i in range(len(title)):
        pos = ((i / len(title)) + offset) % 1.0
        r, g, b = _color_at(pos)
        text.stylize("bold rgb({},{},{})".format(r, g, b), i, i + 1)

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

        console.print(Text(HEADER, justify="center", style="bold rgb(50,120,50)"))
        console.print()

    except ImportError:
        _fallback_splash()


def _fallback_splash() -> None:
    print("\n  ANKYLOSAURUS\n  {}\n".format(HEADER))


if __name__ == "__main__":
    show_splash()
