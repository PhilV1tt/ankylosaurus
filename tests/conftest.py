"""Shared fixtures for ANKYLOSAURUS tests."""

import pytest

from ankylosaurus.modules.detect import HardwareProfile


@pytest.fixture
def m5_profile():
    return HardwareProfile(
        os_type="macOS", os_version="26.4",
        cpu_brand="Apple M5", cpu_arch="arm64", cpu_cores=10,
        gpu_type="apple_silicon", gpu_name="Apple M5", gpu_cores=10,
        gpu_vram_gb=24.0,
        ram_total_gb=24.0, ram_available_gb=12.0, ram_unified=True,
        disk_free_gb=300.0, disk_is_ssd=True,
    )


@pytest.fixture
def rtx2070_profile():
    return HardwareProfile(
        os_type="Linux", os_version="6.5.0",
        cpu_brand="Intel i7-10700K", cpu_arch="x86_64", cpu_cores=8,
        gpu_type="nvidia", gpu_name="RTX 2070 SUPER", gpu_cores=2560,
        gpu_vram_gb=8.0,
        ram_total_gb=32.0, ram_available_gb=20.0, ram_unified=False,
        disk_free_gb=335.0, disk_is_ssd=True,
    )


@pytest.fixture
def budget_profile():
    return HardwareProfile(
        os_type="Windows", os_version="10.0.22631",
        cpu_brand="Intel i5-8250U", cpu_arch="x86_64", cpu_cores=4,
        gpu_type="none", gpu_name="Intel UHD 620", gpu_cores=0,
        gpu_vram_gb=0.0,
        ram_total_gb=8.0, ram_available_gb=4.0, ram_unified=False,
        disk_free_gb=50.0, disk_is_ssd=True,
    )
