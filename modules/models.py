"""Model discovery via HuggingFace Hub API — never hardcoded."""

from __future__ import annotations

from dataclasses import dataclass

from modules.decision import RuntimeDecision
from modules.detect import HardwareProfile
from modules.questionnaire import UserPreferences


@dataclass
class ModelCandidate:
    repo_id: str
    pipeline: str       # "text-generation" | "sentence-similarity"
    downloads: int
    size_gb: float      # estimated from safetensors/GGUF size
    format: str         # "mlx" | "gguf" | "safetensors"
    likes: int


def find_chat_models(
    decision: RuntimeDecision,
    profile: HardwareProfile,
    prefs: UserPreferences,
    limit: int = 5,
) -> list[ModelCandidate]:
    """Search HF Hub for chat/instruct models matching runtime and hardware."""
    from huggingface_hub import HfApi

    api = HfApi()
    candidates: list[ModelCandidate] = []

    if decision.backend == "mlx":
        search_term = "mlx"
        models = api.list_models(
            search=search_term,
            pipeline_tag="text-generation",
            sort="downloads",
            direction=-1,
            limit=50,
        )
    else:
        search_term = "GGUF"
        models = api.list_models(
            search=search_term,
            pipeline_tag="text-generation",
            sort="downloads",
            direction=-1,
            limit=50,
        )

    for m in models:
        size_gb = _estimate_size(m)
        if size_gb > prefs.disk_budget_gb * 0.6:
            continue
        # Skip models too large for RAM
        max_size = decision.max_model_params_b * 0.75  # rough GB estimate
        if size_gb > max_size and max_size > 0:
            continue

        fmt = "mlx" if "mlx" in (m.id or "").lower() else "gguf" if "gguf" in (m.id or "").lower() else "safetensors"
        candidates.append(ModelCandidate(
            repo_id=m.id,
            pipeline=m.pipeline_tag or "text-generation",
            downloads=m.downloads or 0,
            size_gb=round(size_gb, 1),
            format=fmt,
            likes=m.likes or 0,
        ))
        if len(candidates) >= limit:
            break

    return candidates


def find_embedding_models(
    decision: RuntimeDecision,
    profile: HardwareProfile,
    limit: int = 5,
) -> list[ModelCandidate]:
    """Search HF Hub for embedding models."""
    from huggingface_hub import HfApi

    api = HfApi()
    candidates: list[ModelCandidate] = []

    search_term = "mlx" if decision.backend == "mlx" else "embedding"
    models = api.list_models(
        search=search_term,
        pipeline_tag="sentence-similarity",
        sort="downloads",
        direction=-1,
        limit=30,
    )

    for m in models:
        size_gb = _estimate_size(m)
        if size_gb > 5.0:  # embeddings should be small
            continue

        fmt = "mlx" if "mlx" in (m.id or "").lower() else "safetensors"
        candidates.append(ModelCandidate(
            repo_id=m.id,
            pipeline=m.pipeline_tag or "sentence-similarity",
            downloads=m.downloads or 0,
            size_gb=round(size_gb, 2),
            format=fmt,
            likes=m.likes or 0,
        ))
        if len(candidates) >= limit:
            break

    return candidates


def _estimate_size(model_info) -> float:
    """Estimate model size in GB from siblings or model card."""
    # safetensors_params gives total param count if available
    if hasattr(model_info, "safetensors") and model_info.safetensors:
        params = model_info.safetensors.get("total", 0)
        if params:
            return params * 2 / (1024 ** 3)  # fp16 estimate

    # Fallback: check siblings for file sizes
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
    table.add_column("Downloads", justify="right")

    for i, c in enumerate(candidates):
        table.add_row(
            str(i + 1),
            c.repo_id,
            c.format,
            f"{c.size_gb} GB" if c.size_gb else "?",
            f"{c.downloads:,}",
        )

    console.print(table)
    choice = IntPrompt.ask(f"Select {title.lower()} (1-{len(candidates)}, 0 to skip)", default=1)
    return choice - 1
