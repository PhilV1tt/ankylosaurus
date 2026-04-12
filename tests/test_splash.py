"""Tests for splash module."""

from splash import _build_frame, _color_at


def test_build_frame_returns_text():
    frame = _build_frame(0, 24)
    assert str(frame) == "ANKYLOSAURUS"


def test_color_at_boundaries():
    c0 = _color_at(0.0)
    assert all(0 <= v <= 255 for v in c0)
    c1 = _color_at(0.99)
    assert all(0 <= v <= 255 for v in c1)


def test_frames_differ():
    f1 = _build_frame(0, 24)
    f2 = _build_frame(3, 24)
    assert f1._spans != f2._spans
