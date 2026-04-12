"""Model discovery via HuggingFace Hub API — never hardcoded."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from .decision import RuntimeDecision
from .detect import HardwareProfile
from .questionnaire import UserPreferences


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


# --- Scoring ---

# Weights for composite score
W_TRENDING = 0.30
W_LIKES = 0.25
W_FRESHNESS = 0.20
W_DOWNLOADS = 0.15
W_RECENCY = 0.10

FRESHNESS_HALFLIFE_DAYS = 90
RECENCY_THRESHOLD_DAYS = 14


def _compute_scores(candidates: list[ModelCandidate]) -> None:
    """Compute composite score for each candidate (mutates in place)."""
    if not candidates:
        return

    now = datetime.now(timezone.utc)

    # Extract raw values
    trends = [c.trending_score for c in candidates]
    likes = [float(c.likes) for c in candidates]
    downloads = [float(c.downloads) for c in candidates]

    # Min-max normalize
    norm_t = _normalize(trends)
    norm_l = _normalize(likes)
    norm_d = _normalize(downloads)

    for i, c in enumerate(candidates):
        freshness = _freshness(c.created_at, now)
        recency = _recency(c.last_modified, now)

        c.score = (
            W_TRENDING * norm_t[i]
            + W_LIKES * norm_l[i]
            + W_FRESHNESS * freshness
            + W_DOWNLOADS * norm_d[i]
            + W_RECENCY * recency
        )


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


# --- Search ---

def find_chat_models(
    decision: RuntimeDecision,
    profile: HardwareProfile,
    prefs: UserPreferences,
    limit: int = 5,
) -> list[ModelCandidate]:
    """Search HF Hub for chat/instruct models matching runtime and hardware."""
    from huggingface_hub import HfApi

    api = HfApi()
    search_term = "mlx" if decision.backend == "mlx" else "GGUF"

    raw_models = api.list_models(
        search=search_term,
        pipeline_tag="text-generation",
        sort="trending",
        direction=-1,
        limit=100,
    )

    candidates = _filter_candidates(raw_models, decision, prefs)
    _compute_scores(candidates)
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:limit]


def find_embedding_models(
    decision: RuntimeDecision,
    profile: HardwareProfile,
    limit: int = 5,
) -> list[ModelCandidate]:
    """Search HF Hub for embedding models."""
    from huggingface_hub import HfApi

    api = HfApi()
    search_term = "mlx" if decision.backend == "mlx" else "embedding"

    raw_models = api.list_models(
        search=search_term,
        pipeline_tag="sentence-similarity",
        sort="trending",
        direction=-1,
        limit=50,
    )

    candidates: list[ModelCandidate] = []
    for m in raw_models:
        size_gb = _estimate_size(m)
        if size_gb > 5.0:
            continue

        fmt = "mlx" if "mlx" in (m.id or "").lower() else "safetensors"
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
        ))

    _compute_scores(candidates)
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:limit]


def _filter_candidates(
    raw_models,
    decision: RuntimeDecision,
    prefs: UserPreferences,
) -> list[ModelCandidate]:
    """Filter raw HF models by size/RAM/format constraints."""
    candidates: list[ModelCandidate] = []

    for m in raw_models:
        size_gb = _estimate_size(m)
        if size_gb > prefs.disk_budget_gb * 0.6:
            continue
        max_size = decision.max_model_params_b * 0.75
        if size_gb > max_size and max_size > 0:
            continue

        model_id = m.id or ""
        fmt = "mlx" if "mlx" in model_id.lower() else "gguf" if "gguf" in model_id.lower() else "safetensors"
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
    if hasattr(model_info, "safetensors") and model_info.safetensors:
        params = model_info.safetensors.get("total", 0)
        if params:
            return params * 2 / (1024 ** 3)

    if hasattr(model_info, "siblings") and model_info.siblings:
        total = sum(s.size or 0 for s in model_info.siblings if s.size)
        if total > 0:
            return total / (1024 ** 3)

    return 0.0


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
    table.add_column("Age", justify="right")
    table.add_column("Downloads", justify="right")

    now = datetime.now(timezone.utc)
    for i, c in enumerate(candidates):
        age_days = int(_days_since(c.created_at, now))
        age_str = f"{age_days}d" if age_days < 365 else f"{age_days // 365}y"
        score_pct = int(c.score * 100)

        table.add_row(
            str(i + 1),
            c.repo_id,
            c.format,
            f"{c.size_gb} GB" if c.size_gb else "?",
            f"{score_pct}",
            age_str,
            f"{c.downloads:,}",
        )

    console.print(table)
    choice = IntPrompt.ask(f"Select {title.lower()} (1-{len(candidates)}, 0 to skip)", default=1)
    return choice - 1
