"""Tests for detect.py — hardware detection."""

from ankylosaurus.modules.detect import detect_hardware, HardwareProfile, display_hardware


def test_detect_hardware_returns_profile():
    profile = detect_hardware()
    assert isinstance(profile, HardwareProfile)


def test_detect_hardware_valid_os():
    profile = detect_hardware()
    assert profile.os_type in ("macOS", "Linux", "Windows")


def test_detect_hardware_positive_ram():
    profile = detect_hardware()
    assert profile.ram_total_gb > 0
    assert profile.ram_available_gb > 0


def test_detect_hardware_positive_disk():
    profile = detect_hardware()
    assert profile.disk_free_gb > 0


def test_detect_hardware_cpu_info():
    profile = detect_hardware()
    assert profile.cpu_arch in ("arm64", "x86_64", "AMD64")
    assert profile.cpu_cores > 0


def test_display_hardware_no_crash(m5_profile):
    # Should not raise
    display_hardware(m5_profile)
