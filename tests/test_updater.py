"""Tests for updater.py - brew/pip upgrade helpers."""

import os
import subprocess

from ankylosaurus.modules.updater import _brew_upgrade, _pip_upgrade
from rich.console import Console


def test_brew_upgrade_calls_brew(monkeypatch):
    calls = []

    def mock_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", mock_run)
    console = Console(file=open(os.devnull, "w", encoding="utf-8"))
    _brew_upgrade("ollama", console)

    assert len(calls) == 1
    assert calls[0] == ["brew", "upgrade", "ollama"]


def test_brew_upgrade_cask(monkeypatch):
    calls = []

    def mock_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", mock_run)
    console = Console(file=open(os.devnull, "w", encoding="utf-8"))
    _brew_upgrade("anythingllm", console, cask=True)

    assert calls[0] == ["brew", "upgrade", "--cask", "anythingllm"]


def test_pip_upgrade_calls_pip(monkeypatch):
    calls = []

    def mock_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", mock_run)
    console = Console(file=open(os.devnull, "w", encoding="utf-8"))
    _pip_upgrade("llm", console)

    assert calls[0] == ["pip3", "install", "--upgrade", "llm"]
