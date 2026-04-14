"""Tests for checker.py - version checking logic."""

from ankylosaurus.modules.checker import _check_runtime
from ankylosaurus.modules.state import InstallState


def test_check_runtime_with_version():
    state = InstallState(runtime_version="1.2.3")
    installed, latest = _check_runtime(state)
    assert installed == "1.2.3"
    assert latest == "1.2.3"


def test_check_runtime_unknown():
    state = InstallState()
    installed, latest = _check_runtime(state)
    assert installed == "unknown"
