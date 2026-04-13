"""Tests for decision engine."""

from ankylosaurus.modules.decision import decide_runtime
from ankylosaurus.modules.detect import HardwareProfile


def test_m5_gets_mlx(m5_profile):
    d = decide_runtime(m5_profile)
    assert d.runtime == "ollama"
    assert d.backend == "mlx"
    assert d.quantization == "Q6_K"
    assert d.max_context_length >= 16384


def test_nvidia_linux_gets_cuda(rtx2070_profile):
    d = decide_runtime(rtx2070_profile)
    assert d.runtime == "ollama"
    assert d.backend == "cuda"
    assert d.quantization == "Q6_K"  # 32GB RAM


def test_budget_gets_cpu(budget_profile):
    d = decide_runtime(budget_profile)
    assert d.runtime == "ollama"
    assert d.backend == "cpu"
    assert d.quantization == "Q3_K_M"  # 8GB RAM
    assert d.max_context_length <= 8192


def test_max_params_scales_with_ram(m5_profile, budget_profile):
    d_big = decide_runtime(m5_profile)
    d_small = decide_runtime(budget_profile)
    assert d_big.max_model_params_b > d_small.max_model_params_b


# --- UI selection tests ---

def test_ui_open_webui_when_docker_available(m5_profile):
    docker = {"installed": True, "running": True}
    d = decide_runtime(m5_profile, docker_info=docker)
    assert d.ui == "open-webui"


def test_ui_ollama_cli_when_no_docker_macos(m5_profile):
    d = decide_runtime(m5_profile, docker_info=None)
    assert d.ui == "ollama-cli"


def test_ui_ollama_cli_linux_no_docker(rtx2070_profile):
    d = decide_runtime(rtx2070_profile, docker_info=None)
    assert d.ui == "ollama-cli"


def test_ui_ollama_cli_budget_windows(budget_profile):
    d = decide_runtime(budget_profile, docker_info=None)
    assert d.ui == "ollama-cli"


def test_open_webui_deducts_ram_overhead(m5_profile):
    docker = {"installed": True, "running": True}
    d_with_gui = decide_runtime(m5_profile, docker_info=docker)
    d_no_gui = decide_runtime(m5_profile, docker_info=None)
    assert d_with_gui.max_model_params_b < d_no_gui.max_model_params_b


def test_low_ram_no_open_webui():
    """System with 8GB RAM + Docker should NOT get open-webui (below 16GB threshold)."""
    profile = HardwareProfile(
        os_type="Linux", os_version="6.5", cpu_brand="Intel", cpu_arch="x86_64",
        cpu_cores=4, gpu_type="none", gpu_name="", gpu_cores=0, gpu_vram_gb=0,
        ram_total_gb=8.0, ram_available_gb=4.0, ram_unified=False,
        disk_free_gb=100.0, disk_is_ssd=True,
    )
    docker = {"installed": True, "running": True}
    d = decide_runtime(profile, docker_info=docker)
    assert d.ui != "open-webui"
