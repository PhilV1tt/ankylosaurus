"""Hardware detection for ANKYLOSAURUS."""

from __future__ import annotations

import platform
import subprocess
import shutil
from dataclasses import dataclass


@dataclass
class HardwareProfile:
    os_type: str              # "macOS" | "Linux" | "Windows"
    os_version: str
    cpu_brand: str
    cpu_arch: str             # "arm64" | "x86_64"
    cpu_cores: int
    gpu_type: str             # "apple_silicon" | "nvidia" | "amd" | "intel_arc" | "none"
    gpu_name: str
    gpu_cores: int
    gpu_vram_gb: float
    ram_total_gb: float
    ram_available_gb: float
    ram_unified: bool
    disk_free_gb: float
    disk_is_ssd: bool
    mem_bandwidth_gbs: float = 0.0  # memory bandwidth in GB/s (for speed estimation)


# --- Memory bandwidth lookup tables ---

_APPLE_BANDWIDTH: dict[str, float] = {
    "M1": 68, "M1 Pro": 200, "M1 Max": 400, "M1 Ultra": 800,
    "M2": 100, "M2 Pro": 200, "M2 Max": 400, "M2 Ultra": 800,
    "M3": 100, "M3 Pro": 150, "M3 Max": 300, "M3 Ultra": 600,
    "M4": 120, "M4 Pro": 273, "M4 Max": 546, "M4 Ultra": 800,
    "M5": 120, "M5 Pro": 273, "M5 Max": 546, "M5 Ultra": 800,
}

_NVIDIA_BANDWIDTH: dict[str, float] = {
    "RTX 4090": 1008, "RTX 4080": 717, "RTX 4070 Ti": 504, "RTX 4070": 504,
    "RTX 4060 Ti": 288, "RTX 4060": 272,
    "RTX 3090": 936, "RTX 3080": 760, "RTX 3070": 448, "RTX 3060": 360,
    "RTX 2080 Ti": 616, "RTX 2080": 448, "RTX 2070": 448, "RTX 2060": 336,
    "A100": 2039, "H100": 3352, "L40": 864,
}

_DEFAULT_CPU_BANDWIDTH = 40.0  # conservative DDR4/DDR5 estimate


def _lookup_apple_bandwidth(cpu_brand: str) -> float:
    """Match Apple chip name to bandwidth. Tries most specific first."""
    import re
    m = re.search(r"M(\d+)\s*(Pro|Max|Ultra)?", cpu_brand)
    if not m:
        return _APPLE_BANDWIDTH.get("M1", 68.0)
    chip = f"M{m.group(1)}"
    if m.group(2):
        chip += f" {m.group(2)}"
    return _APPLE_BANDWIDTH.get(chip, 120.0)


def _lookup_nvidia_bandwidth(gpu_name: str) -> float:
    """Match NVIDIA GPU name to bandwidth. Tries substring match."""
    for key, bw in _NVIDIA_BANDWIDTH.items():
        if key in gpu_name:
            return bw
    return 400.0  # reasonable default for unknown NVIDIA


def detect_hardware() -> HardwareProfile:
    system = platform.system()
    if system == "Darwin":
        return _detect_macos()
    elif system == "Linux":
        return _detect_linux()
    elif system == "Windows":
        return _detect_windows()
    raise RuntimeError(f"Unsupported OS: {system}")


def _run(cmd: list[str], default: str = "") -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return default


def _detect_apple_chip() -> str:
    """Detect exact Apple Silicon chip model (e.g. 'Apple M5 Pro')."""
    # system_profiler gives the most reliable chip name
    sp_raw = _run(["system_profiler", "SPHardwareDataType"])
    for line in sp_raw.splitlines():
        stripped = line.strip()
        if "Chip:" in stripped:
            return stripped.split(":", 1)[1].strip()
    # Fallback to sysctl
    brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    return brand or "Apple Silicon"


def _detect_macos() -> HardwareProfile:
    import psutil

    arch = platform.machine()  # arm64 or x86_64
    cpu_brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    if not cpu_brand:
        cpu_brand = _run(["uname", "-m"])

    # Apple Silicon: detect exact chip model
    if arch == "arm64":
        cpu_brand = _detect_apple_chip()

    # Apple Silicon GPU info via system_profiler
    gpu_name = ""
    gpu_cores = 0
    gpu_type = "none"
    sp_raw = _run(["system_profiler", "SPDisplaysDataType"])
    for line in sp_raw.splitlines():
        stripped = line.strip()
        if "Chipset Model:" in stripped:
            gpu_name = stripped.split(":", 1)[1].strip()
        elif "Total Number of Cores:" in stripped:
            try:
                gpu_cores = int(stripped.split(":", 1)[1].strip())
            except ValueError:
                pass

    if arch == "arm64":
        gpu_type = "apple_silicon"

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    # SSD check - all modern Macs use NVMe
    disk_is_ssd = True

    # On Apple Silicon, VRAM = unified RAM
    ram_total = mem.total / (1024 ** 3)
    vram = ram_total if gpu_type == "apple_silicon" else 0.0

    bandwidth = _lookup_apple_bandwidth(cpu_brand) if gpu_type == "apple_silicon" else _DEFAULT_CPU_BANDWIDTH

    return HardwareProfile(
        os_type="macOS",
        os_version=platform.mac_ver()[0],
        cpu_brand=cpu_brand,
        cpu_arch=arch,
        cpu_cores=psutil.cpu_count(logical=False) or psutil.cpu_count(),
        gpu_type=gpu_type,
        gpu_name=gpu_name,
        gpu_cores=gpu_cores,
        gpu_vram_gb=round(vram, 1),
        ram_total_gb=round(ram_total, 1),
        ram_available_gb=round(mem.available / (1024 ** 3), 1),
        ram_unified=gpu_type == "apple_silicon",
        disk_free_gb=round(disk.free / (1024 ** 3), 1),
        disk_is_ssd=disk_is_ssd,
        mem_bandwidth_gbs=bandwidth,
    )


def _detect_linux() -> HardwareProfile:
    import psutil

    cpu_brand = ""
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    cpu_brand = line.split(":", 1)[1].strip()
                    break
    except FileNotFoundError:
        cpu_brand = platform.processor()

    gpu_type = "none"
    gpu_name = ""
    gpu_cores = 0
    gpu_vram_gb = 0.0

    # NVIDIA (take first line only for multi-GPU systems)
    if shutil.which("nvidia-smi"):
        nv = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
        if nv:
            first_line = nv.splitlines()[0]
            parts = first_line.split(",")
            gpu_name = parts[0].strip()
            gpu_type = "nvidia"
            try:
                gpu_vram_gb = round(float(parts[1].strip()) / 1024, 1)
            except (ValueError, IndexError):
                pass

    # AMD ROCm
    elif shutil.which("rocm-smi"):
        roc = _run(["rocm-smi", "--showproductname"])
        if roc:
            gpu_type = "amd"
            for line in roc.splitlines():
                if "GPU" in line:
                    gpu_name = line.strip()
                    break

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    # SSD heuristic: check if root is on rotational=0
    disk_is_ssd = False
    try:
        with open("/sys/block/sda/queue/rotational") as f:
            disk_is_ssd = f.read().strip() == "0"
    except FileNotFoundError:
        # NVMe drives use /sys/block/nvme0n1
        try:
            with open("/sys/block/nvme0n1/queue/rotational") as f:
                disk_is_ssd = f.read().strip() == "0"
        except FileNotFoundError:
            pass

    if gpu_type == "nvidia":
        bandwidth = _lookup_nvidia_bandwidth(gpu_name)
    else:
        bandwidth = _DEFAULT_CPU_BANDWIDTH

    return HardwareProfile(
        os_type="Linux",
        os_version=platform.release(),
        cpu_brand=cpu_brand,
        cpu_arch=platform.machine(),
        cpu_cores=psutil.cpu_count(logical=False) or psutil.cpu_count(),
        gpu_type=gpu_type,
        gpu_name=gpu_name,
        gpu_cores=gpu_cores,
        gpu_vram_gb=gpu_vram_gb,
        ram_total_gb=round(mem.total / (1024 ** 3), 1),
        ram_available_gb=round(mem.available / (1024 ** 3), 1),
        ram_unified=False,
        disk_free_gb=round(disk.free / (1024 ** 3), 1),
        disk_is_ssd=disk_is_ssd,
        mem_bandwidth_gbs=bandwidth,
    )


def _detect_windows() -> HardwareProfile:
    import psutil

    cpu_brand = platform.processor()

    gpu_type = "none"
    gpu_name = ""
    gpu_cores = 0
    gpu_vram_gb = 0.0

    if shutil.which("nvidia-smi"):
        nv = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
        if nv:
            first_line = nv.splitlines()[0]
            parts = first_line.split(",")
            gpu_name = parts[0].strip()
            gpu_type = "nvidia"
            try:
                gpu_vram_gb = round(float(parts[1].strip()) / 1024, 1)
            except (ValueError, IndexError):
                pass

    if gpu_type == "none":
        wmic = _run(["wmic", "path", "win32_VideoController", "get", "name"])
        for line in wmic.splitlines()[1:]:
            name = line.strip()
            if name:
                gpu_name = name
                if "AMD" in name or "Radeon" in name:
                    gpu_type = "amd"
                elif "Intel" in name and "Arc" in name:
                    gpu_type = "intel_arc"
                break

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")

    if gpu_type == "nvidia":
        bandwidth = _lookup_nvidia_bandwidth(gpu_name)
    else:
        bandwidth = _DEFAULT_CPU_BANDWIDTH

    return HardwareProfile(
        os_type="Windows",
        os_version=platform.version(),
        cpu_brand=cpu_brand,
        cpu_arch=platform.machine(),
        cpu_cores=psutil.cpu_count(logical=False) or psutil.cpu_count(),
        gpu_type=gpu_type,
        gpu_name=gpu_name,
        gpu_cores=gpu_cores,
        gpu_vram_gb=gpu_vram_gb,
        ram_total_gb=round(mem.total / (1024 ** 3), 1),
        ram_available_gb=round(mem.available / (1024 ** 3), 1),
        ram_unified=False,
        disk_free_gb=round(disk.free / (1024 ** 3), 1),
        disk_is_ssd=True,  # assume SSD on modern Windows
        mem_bandwidth_gbs=bandwidth,
    )


def detect_docker() -> dict:
    """Check Docker availability: CLI installed and daemon running."""
    result = {"installed": False, "running": False}
    if not shutil.which("docker"):
        return result
    result["installed"] = True
    info = _run(["docker", "info"], default="")
    result["running"] = bool(info and "Server Version" in info)
    return result


def display_hardware(profile: HardwareProfile) -> None:
    """Print hardware summary to console."""
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title="Hardware Profile", show_header=False, border_style="dim")
        table.add_column("Key", style="bold cyan")
        table.add_column("Value")

        table.add_row("OS", f"{profile.os_type} {profile.os_version}")
        table.add_row("CPU", f"{profile.cpu_brand} ({profile.cpu_arch}, {profile.cpu_cores} cores)")
        table.add_row("GPU", f"{profile.gpu_name or 'None'} ({profile.gpu_type})")
        if profile.gpu_vram_gb:
            table.add_row("VRAM", f"{profile.gpu_vram_gb} GB {'(unified)' if profile.ram_unified else ''}")
        table.add_row("RAM", f"{profile.ram_total_gb} GB total, {profile.ram_available_gb} GB free")
        table.add_row("Disk", f"{profile.disk_free_gb} GB free {'(SSD)' if profile.disk_is_ssd else '(HDD)'}")

        console.print(table)
    except ImportError:
        print(f"{profile.os_type} {profile.os_version} | {profile.cpu_brand} | "
              f"RAM {profile.ram_total_gb}GB | Disk {profile.disk_free_gb}GB free")
