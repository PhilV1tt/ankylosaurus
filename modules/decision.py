"""Runtime and quantization decision engine — pure logic, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from modules.detect import HardwareProfile


@dataclass
class RuntimeDecision:
    runtime: str          # "lm-studio" | "ollama"
    backend: str          # "mlx" | "llama.cpp-metal" | "cuda" | "rocm" | "cpu"
    quantization: str     # "Q6_K" | "Q4_K_M" | "Q3_K_M" | "Q2_K"
    max_model_params_b: float
    max_context_length: int


def decide_runtime(profile: HardwareProfile) -> RuntimeDecision:
    runtime, backend = _pick_runtime_backend(profile)
    quant = _pick_quantization(profile)
    max_params = _estimate_max_params(profile, quant)
    max_ctx = _estimate_max_context(profile, max_params)

    return RuntimeDecision(
        runtime=runtime,
        backend=backend,
        quantization=quant,
        max_model_params_b=max_params,
        max_context_length=max_ctx,
    )


def _pick_runtime_backend(profile: HardwareProfile) -> tuple[str, str]:
    gpu = profile.gpu_type
    os = profile.os_type

    if gpu == "apple_silicon" and os == "macOS":
        return "lm-studio", "mlx"
    if gpu == "none" and os == "macOS":
        return "ollama", "llama.cpp-metal"
    if gpu == "nvidia" and os == "Linux":
        return "ollama", "cuda"
    if gpu == "amd" and os == "Linux":
        return "ollama", "rocm"
    if gpu == "nvidia" and os == "Windows":
        return "lm-studio", "cuda"
    return "ollama", "cpu"


def _pick_quantization(profile: HardwareProfile) -> str:
    ram = profile.ram_total_gb
    if ram >= 24:
        return "Q6_K"
    if ram >= 16:
        return "Q4_K_M"
    if ram >= 8:
        return "Q3_K_M"
    return "Q2_K"


def _estimate_max_params(profile: HardwareProfile, quant: str) -> float:
    """Estimate max model size in billions of params that fits in memory."""
    # Rough bytes-per-param for each quantization
    bpp = {"Q6_K": 0.75, "Q4_K_M": 0.55, "Q3_K_M": 0.44, "Q2_K": 0.33}
    bytes_per_param = bpp.get(quant, 0.55)

    # Use 75% of available VRAM/RAM for the model, rest for KV cache + OS
    usable_gb = (profile.gpu_vram_gb if profile.gpu_vram_gb > 0 else profile.ram_total_gb) * 0.75
    max_params_b = usable_gb / bytes_per_param
    return round(max_params_b, 1)


def _estimate_max_context(profile: HardwareProfile, max_params_b: float) -> int:
    """Estimate safe max context length."""
    ram = profile.ram_total_gb
    if ram >= 24 and max_params_b <= 14:
        return 32768
    if ram >= 24:
        return 16384
    if ram >= 16:
        return 8192
    return 4096


def display_decision(decision: RuntimeDecision) -> None:
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title="Recommended Setup", show_header=False, border_style="dim")
        table.add_column("Key", style="bold green")
        table.add_column("Value")

        table.add_row("Runtime", decision.runtime)
        table.add_row("Backend", decision.backend)
        table.add_row("Quantization", decision.quantization)
        table.add_row("Max model size", f"~{decision.max_model_params_b}B params")
        table.add_row("Max context", f"{decision.max_context_length} tokens")

        console.print(table)
    except ImportError:
        print(f"Runtime: {decision.runtime} | Backend: {decision.backend} | "
              f"Quant: {decision.quantization} | Max: ~{decision.max_model_params_b}B")
