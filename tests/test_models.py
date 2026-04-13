"""Tests for model scoring and selection."""

from datetime import datetime, timezone, timedelta

import pytest

from ankylosaurus.modules.models import (
    ModelCandidate,
    _compute_scores,
    _normalize,
    _freshness,
    _recency,
    _days_since,
    _effective_model_memory,
    _parse_moe_params,
    _infer_family,
    _infer_use_case,
    _infer_context_length,
    _detect_quantization,
    _extract_metadata,
    _quality_score,
    _speed_score,
    _fit_score,
    _context_score,
)
from ankylosaurus.modules.decision import RuntimeDecision


def _make_candidate(
    repo_id="test/model",
    downloads=1000,
    likes=100,
    trending_score=5.0,
    age_days=30,
    modified_days=7,
    size_gb=5.0,
    params_b=7.0,
    family="",
    use_case="general",
    context_length=8192,
    quantization="",
    is_moe=False,
    active_params_b=0.0,
):
    now = datetime.now(timezone.utc)
    return ModelCandidate(
        repo_id=repo_id,
        pipeline="text-generation",
        downloads=downloads,
        size_gb=size_gb,
        format="mlx",
        likes=likes,
        trending_score=trending_score,
        created_at=(now - timedelta(days=age_days)).isoformat(),
        last_modified=(now - timedelta(days=modified_days)).isoformat(),
        params_b=params_b,
        family=family,
        use_case=use_case,
        context_length=context_length,
        quantization=quantization,
        is_moe=is_moe,
        active_params_b=active_params_b,
    )


def _make_decision(**overrides):
    defaults = dict(
        runtime="ollama", backend="cuda", quantization="Q4_K_M",
        max_model_params_b=10.0, max_context_length=8192,
        ui="terminal", quantization_hierarchy=["Q4_K_M", "Q3_K_M", "Q2_K"],
    )
    defaults.update(overrides)
    return RuntimeDecision(**defaults)


# --- Normalize / freshness / recency (backward compat) ---

def test_normalize_basic():
    assert _normalize([0, 5, 10]) == [0.0, 0.5, 1.0]


def test_normalize_identical():
    result = _normalize([5, 5, 5])
    assert all(v == 0.5 for v in result)


def test_freshness_decays_with_age():
    now = datetime.now(timezone.utc)
    fresh = _freshness((now - timedelta(days=1)).isoformat(), now)
    old = _freshness((now - timedelta(days=180)).isoformat(), now)
    assert fresh > old
    assert fresh > 0.9
    assert old < 0.3


def test_freshness_unknown_date():
    now = datetime.now(timezone.utc)
    result = _freshness("", now)
    assert result < 0.1


def test_recency_recent():
    now = datetime.now(timezone.utc)
    result = _recency((now - timedelta(days=3)).isoformat(), now)
    assert result == 1.0


def test_recency_old():
    now = datetime.now(timezone.utc)
    result = _recency((now - timedelta(days=100)).isoformat(), now)
    assert result == 0.0


def test_days_since_valid():
    now = datetime.now(timezone.utc)
    iso = (now - timedelta(days=10)).isoformat()
    result = _days_since(iso, now)
    assert 9.9 < result < 10.1


def test_days_since_invalid():
    now = datetime.now(timezone.utc)
    result = _days_since("not-a-date", now)
    assert result == 365.0


# --- Metadata extraction ---

def test_parse_moe_8x7b():
    total, active, is_moe = _parse_moe_params("Mixtral-8x7B-Instruct")
    assert is_moe
    assert total == pytest.approx(56.0)
    assert active == pytest.approx(7.0)


def test_parse_moe_17b_16e():
    total, active, is_moe = _parse_moe_params("DeepSeek-17B-16E")
    assert is_moe
    assert total == pytest.approx(272.0)
    assert active == pytest.approx(17.0)


def test_parse_moe_not_moe():
    total, active, is_moe = _parse_moe_params("Llama-3-70B-Instruct")
    assert not is_moe
    assert total == 0.0


def test_infer_family():
    assert _infer_family("Qwen/Qwen3-72B") == "qwen"
    assert _infer_family("meta-llama/Llama-4-70B") == "llama"
    assert _infer_family("deepseek-ai/DeepSeek-R1") == "deepseek"
    assert _infer_family("unknown/random-model") == ""


def test_infer_use_case():
    assert _infer_use_case("bigcode/starcoder2-15B") == "code"
    assert _infer_use_case("deepseek-ai/DeepSeek-R1-7B") == "reasoning"
    assert _infer_use_case("llava-hf/llava-1.5-7B") == "vision"
    assert _infer_use_case("meta-llama/Llama-4-8B-Instruct") == "chat"
    assert _infer_use_case("generic/model-7B") == "general"


def test_infer_use_case_from_tags():
    assert _infer_use_case("model", ["code-generation"]) == "code"


def test_infer_context_length_from_name():
    assert _infer_context_length("Qwen3-32k-7B", "qwen") == 32768
    assert _infer_context_length("Model-128k", "") == 131072


def test_infer_context_length_family_default():
    assert _infer_context_length("Qwen3-7B", "qwen") == 32768
    assert _infer_context_length("unknown-model", "") == 8192


def test_detect_quantization():
    assert _detect_quantization("model-Q4_K_M.gguf") == "Q4_K_M"
    assert _detect_quantization("model-4bit-mlx") == "4bit"
    assert _detect_quantization("model-fp16") == ""


def test_extract_metadata_full():
    meta = _extract_metadata("Qwen/Qwen3-Coder-7B-Q4_K_M-GGUF")
    assert meta["family"] == "qwen"
    assert meta["use_case"] == "code"
    assert meta["params_b"] == pytest.approx(7.0)
    assert meta["quantization"] == "Q4_K_M"
    assert not meta["is_moe"]


def test_extract_metadata_moe():
    meta = _extract_metadata("someone/Mixtral-8x7B-Instruct-GGUF")
    assert meta["is_moe"]
    assert meta["params_b"] == pytest.approx(56.0)
    assert meta["active_params_b"] == pytest.approx(7.0)


# --- Multi-axis scoring ---

def test_quality_favors_larger_models():
    small = _make_candidate(params_b=1.0)
    large = _make_candidate(params_b=70.0)
    assert _quality_score(large, "general") > _quality_score(small, "general")


def test_quality_family_bonus():
    generic = _make_candidate(params_b=7.0, family="")
    qwen = _make_candidate(params_b=7.0, family="qwen")
    assert _quality_score(qwen, "general") > _quality_score(generic, "general")


def test_quality_quant_penalty():
    no_quant = _make_candidate(params_b=7.0, quantization="")
    q2 = _make_candidate(params_b=7.0, quantization="Q2_K")
    assert _quality_score(no_quant, "general") > _quality_score(q2, "general")


def test_quality_use_case_bonus():
    coder = _make_candidate(params_b=7.0, use_case="code")
    general = _make_candidate(params_b=7.0, use_case="general")
    assert _quality_score(coder, "code") > _quality_score(general, "code")


def test_speed_score_larger_model_slower():
    small = _make_candidate(size_gb=2.0)
    large = _make_candidate(size_gb=10.0)
    bandwidth = 120.0
    assert _speed_score(small, bandwidth) > _speed_score(large, bandwidth)


def test_speed_score_stores_tps():
    c = _make_candidate(size_gb=4.0)
    _speed_score(c, 120.0)
    assert c.estimated_tps > 0


def test_fit_score_sweet_spot():
    c = _make_candidate(size_gb=5.0)
    assert _fit_score(c, 8.0) == 1.0  # 62.5% utilization


def test_fit_score_over_budget():
    c = _make_candidate(size_gb=20.0)
    assert _fit_score(c, 8.0) == 0.0


def test_fit_score_tight():
    c = _make_candidate(size_gb=7.5)
    score = _fit_score(c, 8.0)  # 93.75%
    assert 0.0 < score < 1.0


def test_context_score_meets_target():
    c = _make_candidate(context_length=32768)
    assert _context_score(c, "code") == 1.0  # target is 32768


def test_context_score_below_target():
    c = _make_candidate(context_length=4096)
    score = _context_score(c, "code")  # target is 32768
    assert score < 0.5


def test_compute_scores_use_case_weights_change_ranking(m5_profile):
    """Same models scored for 'code' vs 'writing' should produce different rankings."""
    decision = _make_decision(backend="mlx")

    coder = _make_candidate(
        repo_id="code/model", params_b=14.0, size_gb=8.0,
        use_case="code", context_length=32768, family="qwen",
    )
    chatter = _make_candidate(
        repo_id="chat/model", params_b=7.0, size_gb=3.0,
        use_case="chat", context_length=8192, family="llama",
    )

    # Score for coding
    code_candidates = [_make_candidate(**{
        "repo_id": c.repo_id, "params_b": c.params_b, "size_gb": c.size_gb,
        "use_case": c.use_case, "context_length": c.context_length, "family": c.family,
    }) for c in [coder, chatter]]
    _compute_scores(code_candidates, m5_profile, decision, "code")

    # Score for writing (chat profile)
    chat_candidates = [_make_candidate(**{
        "repo_id": c.repo_id, "params_b": c.params_b, "size_gb": c.size_gb,
        "use_case": c.use_case, "context_length": c.context_length, "family": c.family,
    }) for c in [coder, chatter]]
    _compute_scores(chat_candidates, m5_profile, decision, "writing")

    # The coder model should rank higher for code usage
    code_coder_score = code_candidates[0].score
    code_chatter_score = code_candidates[1].score
    assert code_coder_score > code_chatter_score

    # The chatter model should be relatively better for writing usage
    chat_ratio = chat_candidates[1].score / chat_candidates[0].score
    code_ratio = code_candidates[1].score / code_candidates[0].score
    assert chat_ratio > code_ratio


def test_scoring_single_candidate(m5_profile):
    decision = _make_decision(backend="mlx")
    c = _make_candidate()
    _compute_scores([c], m5_profile, decision, "general")
    assert 0.0 <= c.score <= 1.0


def test_scoring_empty_list():
    _compute_scores([])  # should not raise


def test_scoring_without_profile():
    """Score without profile/decision falls back gracefully."""
    c = _make_candidate()
    _compute_scores([c])
    assert 0.0 <= c.score <= 1.0


# --- Effective model memory tests ---

def test_effective_mem_deducts_docker_overhead(m5_profile):
    decision_docker = _make_decision(ui="open-webui")
    decision_no_docker = _make_decision(ui="ollama-cli")

    mem_with = _effective_model_memory(m5_profile, decision_docker)
    mem_without = _effective_model_memory(m5_profile, decision_no_docker)

    assert mem_without - mem_with == pytest.approx(2.0)


def test_effective_mem_discrete_gpu_includes_overflow(rtx2070_profile):
    decision = _make_decision()
    mem = _effective_model_memory(rtx2070_profile, decision)
    assert mem > 8.0
