"""Animated ankylosaur ASCII art splash screen using Rich."""

from __future__ import annotations

import time

VERSION = "1.0"
HEADER = "ANKYLOSAURUS v{} -- local-llm-setup".format(VERSION)

# fmt: off
BODY_LINES = [
    "         .--~~--.",
    "        /  @  @  \\",
    "       |  (====)  |",
    "        \\  \\__/  /",
    "    .----`------'----.",
    "   /  /#\\  /#\\  /#\\  \\",
    "  |  [###][###][###]  |",
    "  |   \\#/  \\#/  \\#/   |",
    "   \\_                _/",
    "     |  |      |  |",
    "     |__|      |__|",
]
# fmt: on

# Tail attaches to line 4 (the back ridge)
TAIL_LINE = 4
TAIL_FRAMES = [
    "~~~<@",
    " ~~~<@",
    "  ~~~<@",
    " ~~~<@",
]

EYES_OPEN = "@  @"
EYES_SHUT = "-  -"

# Color map
COLORS = {
    "#": "rgb(180,140,60)",
    "@": "rgb(200,200,200)",
    "~": "rgb(120,120,120)",
    "<": "rgb(120,120,120)",
    "/": "rgb(50,120,50)",
    "\\": "rgb(50,120,50)",
    "|": "rgb(50,120,50)",
    ".": "rgb(50,120,50)",
    "-": "rgb(50,120,50)",
    "'": "rgb(50,120,50)",
    "`": "rgb(50,120,50)",
    "_": "rgb(50,120,50)",
    "(": "rgb(70,140,70)",
    ")": "rgb(70,140,70)",
    "=": "rgb(70,140,70)",
    "[": "rgb(160,120,40)",
    "]": "rgb(160,120,40)",
}


def _colorize_line(line: str) -> "Text":
    from rich.text import Text
    text = Text(line)
    for i, ch in enumerate(line):
        style = COLORS.get(ch)
        if style:
            text.stylize(style, i, i + 1)
    return text


def _build_frame(tick: int, total_ticks: int) -> "Text":
    from rich.text import Text

    tail_idx = tick % len(TAIL_FRAMES)
    tail = TAIL_FRAMES[tail_idx]

    blink_start = int(total_ticks * 0.4)
    blink_end = int(total_ticks * 0.5)
    blink = blink_start <= tick < blink_end

    result = Text()
    for i, line in enumerate(BODY_LINES):
        if blink:
            line = line.replace(EYES_OPEN, EYES_SHUT)
        if i == TAIL_LINE:
            line = line + tail
        result.append(_colorize_line(line))
        result.append("\n")

    return result


def show_splash(duration: float = 1.5) -> None:
    """Display animated ankylosaur, then print header."""
    try:
        from rich.live import Live
        from rich.console import Console
        from rich.text import Text

        console = Console()
        total_frames = 24
        interval = duration / total_frames

        with Live(console=console, refresh_per_second=16, transient=True) as live:
            for tick in range(total_frames):
                frame = _build_frame(tick, total_frames)
                live.update(frame)
                time.sleep(interval)

        final = _build_frame(total_frames - 1, total_frames)
        console.print(final)
        console.print(Text(HEADER, justify="center", style="bold rgb(50,120,50)"))
        console.print()

    except ImportError:
        _fallback_splash()


def _fallback_splash() -> None:
    print()
    for line in BODY_LINES:
        print(line)
    print("\n  {}\n".format(HEADER))


if __name__ == "__main__":
    show_splash()
