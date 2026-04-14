"""Build model recommendation index from HuggingFace Hub.

Runs in CI (GitHub Actions) on schedule. Outputs data/model_index.json.
No local storage needed - the index lives in the repo.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import HfApi

OUTPUT = Path(__file__).resolve().parent.parent / "data" / "model_index.json"

# Hardware tiers (RAM GB)
TIERS = {
    "8gb": {"max_size_gb": 5, "max_params_b": 9, "quant": "Q3_K_M"},
    "16gb": {"max_size_gb": 12, "max_params_b": 14, "quant": "Q4_K_M"},
    "24gb": {"max_size_gb": 18, "max_params_b": 27, "quant": "Q6_K"},
    "32gb": {"max_size_gb": 25, "max_params_b": 35, "quant": "Q6_K"},
    "48gb": {"max_size_gb": 40, "max_params_b": 70, "quant": "Q6_K"},
}

# Scoring weights (same as models.py)
W_TRENDING = 0.30
W_LIKES = 0.25
W_FRESHNESS = 0.20
W_DOWNLOADS = 0.15
W_RECENCY = 0.10
FRESHNESS_HALFLIFE = 90


def main() -> None:
    api = HfApi()
    now = datetime.now(timezone.utc)

    index = {
        "generated_at": now.isoformat(),
        "tiers": {},
        "embeddings": [],
    }

    # Chat models per tier, per format
    for tier_name, tier in TIERS.items():
        tier_results = {}
        for fmt, search in [("mlx", "mlx"), ("gguf", "GGUF")]:
            models = _fetch_and_score(
                api, now,
                search=search,
                pipeline="text-generation",
                max_size_gb=tier["max_size_gb"],
                limit=10,
            )
            tier_results[fmt] = models
        index["tiers"][tier_name] = tier_results

    # Embedding models (universal, small)
    for fmt, search in [("mlx", "mlx embedding"), ("general", "embedding")]:
        models = _fetch_and_score(
            api, now,
            search=search,
            pipeline="sentence-similarity",
            max_size_gb=5,
            limit=5,
        )
        index["embeddings"].extend(models)

    # Deduplicate embeddings by repo_id
    seen = set()
    deduped = []
    for m in index["embeddings"]:
        if m["repo_id"] not in seen:
            seen.add(m["repo_id"])
            deduped.append(m)
    index["embeddings"] = deduped[:10]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    print("Index written to {} ({} tiers, {} embeddings)".format(
        OUTPUT, len(index["tiers"]), len(index["embeddings"])
    ))


def _fetch_and_score(
    api: HfApi,
    now: datetime,
    search: str,
    pipeline: str,
    max_size_gb: float,
    limit: int,
) -> list[dict]:
    raw = api.list_models(
        search=search,
        pipeline_tag=pipeline,
        sort="trending_score",
        limit=150,
        expand=["safetensors", "siblings", "downloads", "likes", "createdAt", "lastModified", "trendingScore"],
    )

    candidates = []
    for m in raw:
        size_gb = _estimate_size(m)
        if size_gb > max_size_gb or size_gb == 0:
            continue

        candidates.append({
            "repo_id": m.id,
            "downloads": m.downloads or 0,
            "likes": m.likes or 0,
            "trending_score": getattr(m, "trending_score", 0) or 0,
            "size_gb": round(size_gb, 1),
            "created_at": _get_date(m, "created_at"),
            "last_modified": _get_date(m, "last_modified"),
            "format": "mlx" if "mlx" in (m.id or "").lower() else "gguf" if "gguf" in (m.id or "").lower() else "safetensors",
        })

    # Score
    if not candidates:
        return []

    trends = [c["trending_score"] for c in candidates]
    likes = [float(c["likes"]) for c in candidates]
    downloads = [float(c["downloads"]) for c in candidates]

    norm_t = _normalize(trends)
    norm_l = _normalize(likes)
    norm_d = _normalize(downloads)

    for i, c in enumerate(candidates):
        freshness = _freshness(c["created_at"], now)
        recency = _recency(c["last_modified"], now)
        c["score"] = round(
            W_TRENDING * norm_t[i]
            + W_LIKES * norm_l[i]
            + W_FRESHNESS * freshness
            + W_DOWNLOADS * norm_d[i]
            + W_RECENCY * recency,
            4,
        )

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:limit]


def _normalize(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _freshness(created_at: str, now: datetime) -> float:
    days = _days_since(created_at, now)
    return math.exp(-days * math.log(2) / FRESHNESS_HALFLIFE)


def _recency(last_modified: str, now: datetime) -> float:
    days = _days_since(last_modified, now)
    if days <= 14:
        return 1.0
    return max(0.0, 1.0 - (days - 14) / 42)


def _days_since(iso_date: str, now: datetime) -> float:
    if not iso_date:
        return 365.0
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return max(0.0, (now - dt).total_seconds() / 86400)
    except (ValueError, TypeError):
        return 365.0


def _estimate_size(model_info) -> float:
    model_id = (model_info.id or "").lower()
    is_quantized = any(q in model_id for q in ["4bit", "8bit", "q4", "q6", "q3", "q2", "gguf", "gptq", "awq"])

    if hasattr(model_info, "safetensors") and model_info.safetensors:
        params = model_info.safetensors.get("total", 0)
        if params:
            bpp = 0.55 if is_quantized else 2.0
            return params * bpp / (1024 ** 3)

    if hasattr(model_info, "siblings") and model_info.siblings:
        gguf_sizes = [
            s.size for s in model_info.siblings
            if s.size and hasattr(s, "rfilename") and s.rfilename.endswith(".gguf")
        ]
        if gguf_sizes:
            return max(gguf_sizes) / (1024 ** 3)
        total = sum(s.size or 0 for s in model_info.siblings if s.size)
        if total > 0:
            return total / (1024 ** 3)

    # Fallback: parse param count from model name (e.g. "8B", "31B", "70B")
    params_b = _parse_params_from_name(model_id)
    if params_b > 0:
        bpp = 0.55 if is_quantized else 2.0
        return params_b * bpp
    return 0.0


def _parse_params_from_name(model_id: str) -> float:
    """Extract parameter count in billions from model name."""
    import re
    # Match patterns like "8b", "31b", "70b", "1.5b", "0.5b"
    match = re.search(r"(\d+\.?\d*)[_-]?b(?:\b|[^a-z])", model_id)
    if match:
        return float(match.group(1))
    return 0.0


def _get_date(model_info, attr: str) -> str:
    val = getattr(model_info, attr, None)
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


if __name__ == "__main__":
    main()
