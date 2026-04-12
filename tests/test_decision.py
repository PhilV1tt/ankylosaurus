"""Tests for decision engine."""

from modules.decision import decide_runtime


def test_m5_gets_mlx(m5_profile):
    d = decide_runtime(m5_profile)
    assert d.runtime == "lm-studio"
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
