"""LanceDB vector store wrapper for RAG."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa


_SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("text", pa.string()),
    pa.field("doc_name", pa.string()),
    pa.field("page", pa.int32()),
    pa.field("chunk_id", pa.int32()),
    # vector field added dynamically based on embedding dimension
])


class VectorStore:
    """Thin wrapper around a single LanceDB table for RAG documents."""

    TABLE = "documents"

    def __init__(self, db_path: str | None = None):
        import lancedb

        if db_path is None:
            db_path = str(Path.home() / ".ankylosaurus" / "rag.lance")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(db_path)
        self._table_exists: bool = self.TABLE in self._db.list_tables()

    def _ensure_table(self, dim: int):
        if not self._table_exists:
            schema = _SCHEMA.append(pa.field("vector", pa.list_(pa.float32(), dim)))
            self._db.create_table(self.TABLE, schema=schema)
            self._table_exists = True

    def add_document(
        self,
        doc_name: str,
        chunks: list[dict],
        embeddings: list[list[float]],
    ) -> int:
        """Add chunks + embeddings for a document. Returns number of rows added."""
        if not chunks or not embeddings:
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks/embeddings length mismatch: {len(chunks)} chunks, {len(embeddings)} embeddings"
            )

        dim = len(embeddings[0])
        # Validate all embeddings have same dimension
        for i, emb in enumerate(embeddings):
            if len(emb) != dim:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {dim}, got {len(emb)} at index {i}"
                )
        self._ensure_table(dim)

        rows = []
        for chunk, emb in zip(chunks, embeddings):
            rows.append({
                "id": f"{doc_name}:{chunk['metadata']['chunk_id']}",
                "text": chunk["text"],
                "doc_name": doc_name,
                "page": chunk["metadata"]["page"],
                "chunk_id": chunk["metadata"]["chunk_id"],
                "vector": emb,
            })

        table = self._db.open_table(self.TABLE)
        table.add(rows)
        return len(rows)

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        """Return top_k most similar chunks."""
        if not self._table_exists:
            return []
        table = self._db.open_table(self.TABLE)
        results = (
            table.search(query_embedding)
            .limit(top_k)
            .to_list()
        )
        return [
            {
                "text": r["text"],
                "doc_name": r["doc_name"],
                "page": r["page"],
                "score": r.get("_distance", 0.0),
            }
            for r in results
        ]

    def list_documents(self) -> list[str]:
        """Return unique document names."""
        if not self._table_exists:
            return []
        table = self._db.open_table(self.TABLE)
        arrow_table = table.to_arrow(columns=["doc_name"])
        names = arrow_table.column("doc_name").to_pylist()
        return sorted(set(names))

    def delete_document(self, doc_name: str) -> int:
        """Delete all chunks for a document. Returns rows deleted."""
        if not self._table_exists:
            return 0
        table = self._db.open_table(self.TABLE)
        before = table.count_rows()
        safe_name = doc_name.replace("'", "''")
        table.delete(f"doc_name = '{safe_name}'")
        after = table.count_rows()
        return before - after
