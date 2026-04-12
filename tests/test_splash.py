"""Tests for splash module."""

from splash import _build_frame, BODY_LINES, EYES_OPEN, EYES_SHUT, TAIL_FRAMES


def test_build_frame_contains_body():
    frame = _build_frame(0, 24)
    text = str(frame)
    assert "(====)" in text
    assert "[###]" in text


def test_tail_appears_in_frame():
    frame = _build_frame(0, 24)
    text = str(frame)
    assert "~~~<@" in text


def test_eyes_blink_mid_animation():
    total = 24
    blink_tick = int(total * 0.45)
    frame = _build_frame(blink_tick, total)
    text = str(frame)
    assert EYES_SHUT in text


def test_eyes_open_at_start():
    frame = _build_frame(0, 24)
    text = str(frame)
    assert EYES_OPEN in text


def test_tail_swings():
    texts = [str(_build_frame(t, 24)) for t in range(4)]
    # At least 2 different tail positions in 4 frames
    unique = set()
    for t in texts:
        for tail in TAIL_FRAMES:
            if tail in t:
                unique.add(tail)
    assert len(unique) >= 2
