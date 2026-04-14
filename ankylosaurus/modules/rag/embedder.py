"""Jina v5 MLX embedding engine - loads model natively on Apple Silicon."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

DEFAULT_MODEL_PATH = Path.home() / ".ankylosaurus" / "models" / "jina-v5-mlx"


class Embedder:
    """Lazy-loaded Jina v5 MLX embedder."""

    def __init__(self, model_path: str | Path | None = None):
        self._model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self._model = None
        self._tokenizer = None

    def _load(self):
        if self._model is not None:
            return

        import mlx.core as mx

        model_dir = self._model_path

        # Load model.py from the HF download (ships with the model)
        model_py = model_dir / "model.py"
        if not model_py.exists():
            raise FileNotFoundError(
                f"model.py not found in {model_dir}. "
                f"Download with: hf download jinaai/jina-embeddings-v5-text-small-retrieval-mlx "
                f"--local-dir {model_dir}"
            )

        spec = importlib.util.spec_from_file_location("jina_model", model_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        with open(model_dir / "config.json") as f:
            config = json.load(f)

        self._model = mod.JinaEmbeddingModel(config)

        # Prefer quantized weights - find first existing file
        candidates = ["model-4bit.safetensors", "model-8bit.safetensors", "model.safetensors"]
        weights_path = next((model_dir / f for f in candidates if (model_dir / f).exists()), None)
        if weights_path is None:
            raise FileNotFoundError(f"No safetensors found in {model_dir}")
        weights = mx.load(str(weights_path))
        self._model.load_weights(list(weights.items()))

        from tokenizers import Tokenizer
        self._tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))

    def embed(
        self, texts: list[str], task: str = "retrieval.passage", batch_size: int = 32,
    ) -> list[list[float]]:
        """Embed a list of texts in batches. Returns list of float vectors."""
        self._load()
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            result = self._model.encode(batch, self._tokenizer, task_type=task)
            if hasattr(result, "tolist"):
                all_embeddings.extend(result.tolist())
            elif result and hasattr(result[0], "tolist"):
                all_embeddings.extend(r.tolist() for r in result)
            else:
                all_embeddings.extend(list(r) for r in result)

        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query for retrieval."""
        results = self.embed([query], task="retrieval.query")
        return results[0]

    @property
    def model_path(self) -> Path:
        return self._model_path

    @property
    def is_downloaded(self) -> bool:
        return (self._model_path / "model.py").exists()
