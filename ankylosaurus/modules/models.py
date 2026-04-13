"""Model discovery — multi-axis scoring with live HF Hub + curated catalog."""

from __future__ import annotations

import heapq
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from .decision import BYTES_PER_PARAM, RuntimeDecision
from .detect import HardwareProfile
from .questionnaire import UserPreferences

INDEX_URL = "https://raw.githubusercontent.com/PhilV1tt/ankylosaurus/main/data/model_index.json"
INDEX_MAX_AGE_DAYS = 7

# --- Curated families (Top 10) ---

CURATED_FAMILIES: list[tuple[str, str, str]] = [
    ("Qwen/Qwen3", "qwen", "general"),
    ("meta-llama/Llama-4", "llama", "general"),
    ("deepseek-ai/DeepSeek-R1", "deepseek", "reasoning"),
    ("google/gemma-4", "gemma", "general"),
    ("mistralai/Mistral", "mistral", "general"),
    ("microsoft/phi-4", "phi", "general"),
    ("01-ai/Yi", "yi", "general"),
    ("CohereForAI/c4ai-command-r", "command-r", "chat"),
    ("bigcode/starcoder2", "starcoder", "code"),
    ("internlm/internlm3", "internlm", "general"),
]

# --- Usage mapping ---

USAGE_TO_PROFILE: dict[str, str] = {
    "code": "coding",
    "studies": "reasoning",
    "writing": "chat",
    "general": "general",
}

# --- Scoring weights per profile: (quality, speed, fit, context) ---

PROFILE_WEIGHTS: dict[str, tuple[float, float, float, float]] = {
    "general":   (0.45, 0.30, 0.15, 0.10),
    "coding":    (0.50, 0.20, 0.15, 0.15),
    "reasoning": (0.55, 0.15, 0.15, 0.15),
    "chat":      (0.40, 0.35, 0.15, 0.10),
}

# --- Context targets per profile ---

CONTEXT_TARGETS: dict[str, int] = {
    "general": 8192,
    "coding": 32768,
    "reasoning": 16384,
    "chat": 8192,
}

# --- Family reputation bonus ---

FAMILY_REPUTATION: dict[str, float] = {
    "qwen": 0.12, "deepseek": 0.12, "llama": 0.10, "mistral": 0.10,
    "gemma": 0.08, "phi": 0.08, "yi": 0.06, "command-r": 0.06,
    "starcoder": 0.06, "internlm": 0.04,
}

# --- Quantization penalty ---

QUANT_PENALTY: dict[str, float] = {
    "Q2_K": 0.15, "Q3_K_M": 0.10, "Q4_K_M": 0.05, "Q5_K_M": 0.03,
    "Q6_K": 0.02, "Q8_0": 0.0, "4bit": 0.05, "8bit": 0.0,
    "gptq": 0.05, "awq": 0.05, "mlx-4bit": 0.05, "mlx-8bit": 0.0,
}

# Freshness constants (kept for backward compat with tests)
FRESHNESS_HALFLIFE_DAYS = 90
RECENCY_THRESHOLD_DAYS = 14


@dataclass
class ModelCandidate:
    repo_id: str
    pipeline: str
    downloads: int
    size_gb: float
    format: str
    likes: int
    trending_score: float
    created_at: str
    last_modified: str
    score: float = 0.0
    # enriched metadata
    params_b: float = 0.0
    is_moe: bool = False
    active_params_b: float = 0.0
    family: str = ""
    use_case: str = ""
    context_length: int = 0
    quantization: str = ""
    # sub-scores
    quality_score: float = 0.0
    speed_score: float = 0.0
    fit_score: float = 0.0
    context_score: float = 0.0
    estimated_tps: float = 0.0


# ── Regex patterns ──

_PARAM_RE = re.compile(r"(\d+\.?\d*)[_-]?b(?:\b|[^a-z])", re.IGNORECASE)
_MOE_RE = re.compile(r"(\d+)x(\d+\.?\d*)[_-]?b", re.IGNORECASE)
_MOE_RE2 = re.compile(r"(\d+\.?\d*)[_-]?b[_-](\d+)e", re.IGNORECASE)
_CTX_RE = re.compile(r"(\d+)[_-]?k\b", re.IGNORECASE)
_QUANT_RE = re.compile(
    r"(Q[2-8]_K(?:_[A-Z])?|Q[2-8]_0|4bit|8bit|gptq|awq|mlx-[48]bit)",
    re.IGNORECASE,
)


# ── Metadata extraction ──

def _parse_moe_params(name: str) -> tuple[float, float, bool]:
    """Parse MoE patterns like '8x7B' or '17B-16E'. Returns (total, active, is_moe)."""
    m = _MOE_RE.search(name)
    if m:
        experts = int(m.group(1))
        per_expert = float(m.group(2))
        return (experts * per_expert, per_expert, True)

    m = _MOE_RE2.search(name)
    if m:
        per_expert = float(m.group(1))
        experts = int(m.group(2))
        return (experts * per_expert, per_expert, True)

    return (0.0, 0.0, False)


def _infer_family(name: str) -> str:
    """Detect model family from name."""
    lower = name.lower()
    families = [
        "qwen", "llama", "deepseek", "gemma", "mistral", "phi", "yi",
        "command-r", "starcoder", "internlm",
    ]
    for f in families:
        if f in lower:
            return f
    return ""


def _infer_use_case(name: str, tags: list[str] | None = None) -> str:
    """Infer use-case from model name and tags."""
    lower = name.lower()
    all_text = lower + " " + " ".join(t.lower() for t in (tags or []))

    if any(k in all_text for k in ("coder", "code", "starcoder")):
        return "code"
    if any(k in all_text for k in ("reason", "think", "r1", "qwq")):
        return "reasoning"
    if any(k in all_text for k in ("vision", "vl", "multimodal", "llava")):
        return "vision"
    if any(k in all_text for k in ("chat", "instruct", "assistant")):
        return "chat"
    return "general"


def _infer_context_length(name: str, family: str) -> int:
    """Infer context window from name patterns or family defaults."""
    m = _CTX_RE.search(name)
    if m:
        k = int(m.group(1))
        if k >= 1:
            return k * 1024

    family_defaults: dict[str, int] = {
        "qwen": 32768, "llama": 131072, "deepseek": 65536,
        "gemma": 32768, "mistral": 32768, "phi": 16384,
        "yi": 32768, "command-r": 131072, "starcoder": 16384,
        "internlm": 32768,
    }
    return family_defaults.get(family, 8192)


def _detect_quantization(name: str) -> str:
    """Detect quantization level from model name."""
    m = _QUANT_RE.search(name)
    return m.group(1) if m else ""


def _extract_metadata(repo_id: str, tags: list[str] | None = None) -> dict:
    """Extract all metadata from a model repo ID."""
    total, active, is_moe = _parse_moe_params(repo_id)
    if not is_moe:
        params_b = _parse_params_from_name(repo_id)
        total = params_b
        active = params_b

    family = _infer_family(repo_id)
    return {
        "params_b": total,
        "is_moe": is_moe,
        "active_params_b": active,
        "family": family,
        "use_case": _infer_use_case(repo_id, tags),
        "context_length": _infer_context_length(repo_id, family),
        "quantization": _detect_quantization(repo_id),
    }


# ── Multi-axis scoring ──

def _quality_score(c: ModelCandidate, user_profile: str) -> float:
    """Quality axis: base from params + family bonus - quant penalty + use-case match."""
    p = c.params_b
    if p <= 0:
        base = 0.40  # unknown size
    elif p <= 1:
        base = 0.30
    elif p <= 3:
        base = 0.40
    elif p <= 7:
        base = 0.55
    elif p <= 14:
        base = 0.65
    elif p <= 30:
        base = 0.80
    elif p <= 70:
        base = 0.90
    else:
        base = 0.95

    base += FAMILY_REPUTATION.get(c.family, 0.0)
    base -= QUANT_PENALTY.get(c.quantization.upper() if c.quantization else "", 0.0)

    # Use-case alignment bonus
    usage_profile = USAGE_TO_PROFILE.get(user_profile, user_profile)
    case_map = {"coding": "code", "reasoning": "reasoning", "chat": "chat"}
    if c.use_case == case_map.get(usage_profile, ""):
        base += 0.10

    return max(0.0, min(1.0, base))


def _speed_score(c: ModelCandidate, bandwidth_gbs: float) -> float:
    """Speed axis: estimated TPS from memory bandwidth model."""
    if c.size_gb <= 0 or bandwidth_gbs <= 0:
        return 0.5  # unknown

    model_size = c.size_gb
    # For MoE, only active params contribute to per-token cost
    if c.is_moe and c.active_params_b > 0 and c.params_b > 0:
        model_size *= (c.active_params_b / c.params_b)

    max_tps = bandwidth_gbs / model_size
    # Apply ~60% efficiency factor
    estimated_tps = max_tps * 0.6
    c.estimated_tps = round(estimated_tps, 1)

    # Score: 40 tps = 1.0, linear below
    target_tps = 40.0
    return min(1.0, estimated_tps / target_tps)


def _fit_score(c: ModelCandidate, effective_mem: float) -> float:
    """Fit axis: memory utilization efficiency. Sweet spot at 50-80%."""
    if effective_mem <= 0 or c.size_gb <= 0:
        return 0.5

    ratio = c.size_gb / effective_mem
    if ratio > 1.0:
        return 0.0  # over budget
    if ratio > 0.95:
        return 0.2  # very tight
    if ratio > 0.80:
        return 0.7  # tight but ok
    if ratio >= 0.50:
        return 1.0  # sweet spot
    if ratio >= 0.30:
        return 0.6 + (ratio - 0.30) / 0.20 * 0.4
    return 0.6  # very small model, wastes capacity


def _context_score(c: ModelCandidate, user_profile: str) -> float:
    """Context axis: model context vs use-case target."""
    usage_profile = USAGE_TO_PROFILE.get(user_profile, user_profile)
    target = CONTEXT_TARGETS.get(usage_profile, 8192)
    if c.context_length <= 0:
        return 0.5  # unknown
    return min(1.0, c.context_length / target)


def _compute_scores(
    candidates: list[ModelCandidate],
    profile: HardwareProfile | None = None,
    decision: RuntimeDecision | None = None,
    user_usage: str = "general",
) -> None:
    """Compute multi-axis composite score for each candidate (mutates in place)."""
    if not candidates:
        return

    # Determine scoring profile
    usage_profile = USAGE_TO_PROFILE.get(user_usage, "general")
    wq, ws, wf, wc = PROFILE_WEIGHTS.get(usage_profile, PROFILE_WEIGHTS["general"])

    bandwidth = profile.mem_bandwidth_gbs if profile else 0.0
    effective_mem = _effective_model_memory(profile, decision) if profile and decision else 0.0

    now = datetime.now(timezone.utc)

    for c in candidates:
        # Enrich metadata if not already set
        if not c.family:
            meta = _extract_metadata(c.repo_id)
            for k, v in meta.items():
                if not getattr(c, k, None):
                    setattr(c, k, v)

        c.quality_score = _quality_score(c, user_usage)
        c.speed_score = _speed_score(c, bandwidth)
        c.fit_score = _fit_score(c, effective_mem)
        c.context_score = _context_score(c, user_usage)

        # Weighted composite + small freshness/trending bonus (10%)
        base_score = (
            wq * c.quality_score
            + ws * c.speed_score
            + wf * c.fit_score
            + wc * c.context_score
        )
        freshness_bonus = 0.10 * _freshness(c.created_at, now)
        c.score = min(1.0, base_score + freshness_bonus)


# ── Utility functions (kept public for backward-compat with tests) ──

def _normalize(values: list[float]) -> list[float]:
    """Min-max normalization to [0, 1]."""
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _freshness(created_at: str, now: datetime) -> float:
    """Exponential decay based on model age. Half-life ~90 days."""
    age_days = _days_since(created_at, now)
    return math.exp(-age_days * math.log(2) / FRESHNESS_HALFLIFE_DAYS)


def _recency(last_modified: str, now: datetime) -> float:
    """1.0 if modified within threshold, decays linearly to 0 at 4x threshold."""
    days = _days_since(last_modified, now)
    if days <= RECENCY_THRESHOLD_DAYS:
        return 1.0
    return max(0.0, 1.0 - (days - RECENCY_THRESHOLD_DAYS) / (3 * RECENCY_THRESHOLD_DAYS))


def _days_since(iso_date: str, now: datetime) -> float:
    """Parse ISO date string and return days elapsed."""
    if not iso_date:
        return 365.0  # unknown = assume old
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return max(0.0, (now - dt).total_seconds() / 86400)
    except (ValueError, TypeError):
        return 365.0


# ── Memory estimation ──

def _effective_model_memory(profile: HardwareProfile, decision: RuntimeDecision) -> float:
    """Calculate effective memory in GB for model selection, accounting for overhead."""
    if profile.ram_unified:
        base = profile.ram_total_gb
    elif profile.gpu_vram_gb > 0:
        ram_overflow = min(profile.ram_total_gb * 0.25, 8.0)
        base = profile.gpu_vram_gb + ram_overflow
    else:
        base = profile.ram_total_gb

    overhead = 2.0 if decision.ui == "open-webui" else 0.0
    return max(base - overhead, 4.0)


# ── Index ──

def _ram_to_tier(ram_gb: float) -> str:
    if ram_gb >= 48:
        return "48gb"
    if ram_gb >= 32:
        return "32gb"
    if ram_gb >= 24:
        return "24gb"
    if ram_gb >= 16:
        return "16gb"
    return "8gb"


def _load_index() -> dict | None:
    """Try to fetch pre-computed index. Returns None if unavailable or stale."""
    try:
        import httpx
        resp = httpx.get(INDEX_URL, timeout=5, follow_redirects=True)
        if resp.status_code != 200:
            return None
        data = resp.json()
        gen = data.get("generated_at", "")
        if gen:
            age = _days_since(gen, datetime.now(timezone.utc))
            if age > INDEX_MAX_AGE_DAYS:
                return None
        return data
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug("Failed to load model index: %s", e)
        return None


def _index_to_candidates(entries: list[dict], pipeline: str = "text-generation") -> list[ModelCandidate]:
    """Convert index entries to ModelCandidate objects."""
    return [
        ModelCandidate(
            repo_id=e["repo_id"],
            pipeline=pipeline,
            downloads=e.get("downloads", 0),
            size_gb=e.get("size_gb", 0),
            format=e.get("format", ""),
            likes=e.get("likes", 0),
            trending_score=e.get("trending_score", 0),
            created_at=e.get("created_at", ""),
            last_modified=e.get("last_modified", ""),
            score=e.get("score", 0),
            params_b=e.get("params_b", 0),
            is_moe=e.get("is_moe", False),
            active_params_b=e.get("active_params_b", 0),
            family=e.get("family", ""),
            use_case=e.get("use_case", ""),
            context_length=e.get("context_length", 0),
            quantization=e.get("quantization", ""),
        )
        for e in entries
    ]


# ── Search ──

def find_chat_models(
    decision: RuntimeDecision,
    profile: HardwareProfile,
    prefs: UserPreferences,
    limit: int = 5,
) -> list[ModelCandidate]:
    """Search for chat models. Uses pre-computed index, falls back to live HF Hub."""
    index = _load_index()
    effective_mem = _effective_model_memory(profile, decision)
    max_size_gb = effective_mem * 0.75

    if index:
        tier = _ram_to_tier(effective_mem)
        fmt = "mlx" if decision.backend == "mlx" else "gguf"
        entries = index.get("tiers", {}).get(tier, {}).get(fmt, [])
        if entries:
            candidates = _index_to_candidates(entries)
            candidates = [
                c for c in candidates
                if c.size_gb > 0
                and c.size_gb <= prefs.disk_budget_gb * 0.6
                and (c.size_gb <= max_size_gb if max_size_gb > 0 else True)
            ]
            _compute_scores(candidates, profile, decision, prefs.usage)
            candidates.sort(key=lambda c: c.score, reverse=True)
            return candidates[:limit]

    # Fallback: live search (trending + curated)
    return _live_chat_search(decision, profile, prefs, limit, max_size_gb=max_size_gb)


def _live_chat_search(
    decision: RuntimeDecision,
    profile: HardwareProfile,
    prefs: UserPreferences,
    limit: int,
    max_size_gb: float = 0,
) -> list[ModelCandidate]:
    from huggingface_hub import HfApi

    api = HfApi()
    search_term = "mlx" if decision.backend == "mlx" else "GGUF"

    # 1. Trending search (existing)
    raw_models = list(api.list_models(
        search=search_term,
        pipeline_tag="text-generation",
        sort="trending_score",
        limit=100,
        expand=["safetensors", "siblings", "downloads", "likes",
                "createdAt", "lastModified", "trendingScore", "tags"],
    ))

    # 2. Curated families search
    for prefix, _family, _use_case in CURATED_FAMILIES:
        try:
            curated = list(api.list_models(
                search=f"{prefix} {search_term}",
                pipeline_tag="text-generation",
                sort="trending_score",
                limit=10,
                expand=["safetensors", "siblings", "downloads", "likes",
                        "createdAt", "lastModified", "trendingScore", "tags"],
            ))
            raw_models.extend(curated)
        except Exception:
            continue

    # 3. Deduplicate
    seen: set[str] = set()
    unique = []
    for m in raw_models:
        mid = m.id or ""
        if mid not in seen:
            seen.add(mid)
            unique.append(m)

    candidates = _filter_candidates(unique, decision, prefs, max_size_gb)
    _compute_scores(candidates, profile, decision, prefs.usage)
    return heapq.nlargest(limit, candidates, key=lambda c: c.score)


def find_embedding_models(
    decision: RuntimeDecision,
    profile: HardwareProfile,
    limit: int = 5,
) -> list[ModelCandidate]:
    """Search for embedding models. Uses pre-computed index, falls back to live."""
    index = _load_index()
    if index:
        entries = index.get("embeddings", [])
        fmt = "mlx" if decision.backend == "mlx" else "safetensors"
        filtered = [e for e in entries if e.get("format") == fmt or fmt == "safetensors"]
        if filtered:
            return _index_to_candidates(filtered, "sentence-similarity")[:limit]

    return _live_embedding_search(decision, limit)


def _live_embedding_search(
    decision: RuntimeDecision,
    limit: int,
) -> list[ModelCandidate]:
    from huggingface_hub import HfApi

    api = HfApi()
    search_term = "mlx" if decision.backend == "mlx" else "embedding"

    raw_models = api.list_models(
        search=search_term,
        pipeline_tag="sentence-similarity",
        sort="trending_score",
        limit=50,
        expand=["safetensors", "siblings", "downloads", "likes",
                "createdAt", "lastModified", "trendingScore", "tags"],
    )

    candidates: list[ModelCandidate] = []
    for m in raw_models:
        size_gb = _estimate_size(m)
        if size_gb > 5.0:
            continue

        fmt = "mlx" if "mlx" in (m.id or "").lower() else "safetensors"
        tags = list(m.tags) if hasattr(m, "tags") and m.tags else []
        meta = _extract_metadata(m.id or "", tags)
        candidates.append(ModelCandidate(
            repo_id=m.id,
            pipeline=m.pipeline_tag or "sentence-similarity",
            downloads=m.downloads or 0,
            size_gb=round(size_gb, 2),
            format=fmt,
            likes=m.likes or 0,
            trending_score=getattr(m, "trending_score", 0) or 0,
            created_at=_get_date(m, "created_at"),
            last_modified=_get_date(m, "last_modified"),
            **meta,
        ))

    _compute_scores(candidates)
    return heapq.nlargest(limit, candidates, key=lambda c: c.score)


def _filter_candidates(
    raw_models,
    decision: RuntimeDecision,
    prefs: UserPreferences,
    max_size_gb: float = 0,
) -> list[ModelCandidate]:
    """Filter raw HF models by size/RAM/format constraints."""
    candidates: list[ModelCandidate] = []

    for m in raw_models:
        size_gb = _estimate_size(m)
        if size_gb <= 0 or size_gb > prefs.disk_budget_gb * 0.6:
            continue
        if max_size_gb > 0 and size_gb > max_size_gb:
            continue

        model_id = m.id or ""
        fmt = "mlx" if "mlx" in model_id.lower() else "gguf" if "gguf" in model_id.lower() else "safetensors"
        tags = list(m.tags) if hasattr(m, "tags") and m.tags else []
        meta = _extract_metadata(model_id, tags)
        candidates.append(ModelCandidate(
            repo_id=model_id,
            pipeline=m.pipeline_tag or "text-generation",
            downloads=m.downloads or 0,
            size_gb=round(size_gb, 1),
            format=fmt,
            likes=m.likes or 0,
            trending_score=getattr(m, "trending_score", 0) or 0,
            created_at=_get_date(m, "created_at"),
            last_modified=_get_date(m, "last_modified"),
            **meta,
        ))

    return candidates


def _get_date(model_info, attr: str) -> str:
    """Extract date string from model info, handling various formats."""
    val = getattr(model_info, attr, None)
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


def _estimate_size(model_info) -> float:
    """Estimate model size in GB from siblings or model card."""
    model_id = (model_info.id or "").lower()
    is_quantized = any(q in model_id for q in ["4bit", "8bit", "q4", "q6", "q3", "q2", "gguf", "gptq", "awq"])

    if hasattr(model_info, "safetensors") and model_info.safetensors:
        params = model_info.safetensors.get("total", 0)
        if params:
            bpp = 0.55 if is_quantized else 2.0
            return params * bpp / (1024 ** 3)

    if hasattr(model_info, "siblings") and model_info.siblings:
        max_gguf = 0
        total = 0
        for s in model_info.siblings:
            size = s.size or 0
            total += size
            if size and hasattr(s, "rfilename") and s.rfilename.endswith(".gguf"):
                if size > max_gguf:
                    max_gguf = size
        if max_gguf:
            return max_gguf / (1024 ** 3)
        if total > 0:
            return total / (1024 ** 3)

    # Fallback: parse param count from model name
    params_b = _parse_params_from_name(model_id)
    if params_b > 0:
        bpp = 0.55 if is_quantized else 2.0
        return params_b * bpp
    return 0.0


def _parse_params_from_name(model_id: str) -> float:
    """Extract parameter count in billions from model name."""
    match = _PARAM_RE.search(model_id)
    if match:
        return float(match.group(1))
    return 0.0


# ── Display ──

def display_candidates(candidates: list[ModelCandidate], title: str = "Models") -> int:
    """Display model candidates in a Rich table, return user's choice index."""
    from rich.console import Console
    from rich.table import Table
    from rich.prompt import IntPrompt

    console = Console()

    if not candidates:
        console.print(f"[yellow]No {title.lower()} found matching criteria.[/yellow]")
        return -1

    table = Table(title=title, border_style="dim")
    table.add_column("#", style="bold")
    table.add_column("Model")
    table.add_column("Format")
    table.add_column("Size")
    table.add_column("Score", justify="right", style="bold green")
    table.add_column("TPS", justify="right", style="cyan")
    table.add_column("Age", justify="right")
    table.add_column("Downloads", justify="right")

    now = datetime.now(timezone.utc)
    for i, c in enumerate(candidates):
        age_days = int(_days_since(c.created_at, now))
        age_str = f"{age_days}d" if age_days < 365 else f"{age_days // 365}y"
        score_pct = int(c.score * 100)
        tps_str = f"~{c.estimated_tps:.0f}" if c.estimated_tps > 0 else "?"

        table.add_row(
            str(i + 1),
            c.repo_id,
            c.format,
            f"{c.size_gb} GB" if c.size_gb else "?",
            f"{score_pct}",
            tps_str,
            age_str,
            f"{c.downloads:,}",
        )

    console.print(table)
    while True:
        choice = IntPrompt.ask(f"Select {title.lower()} (1-{len(candidates)}, 0 to skip)", default=1)
        if choice == 0:
            return -1
        if 1 <= choice <= len(candidates):
            return choice - 1
        console.print(f"[yellow]Please enter a number between 0 and {len(candidates)}.[/yellow]")
