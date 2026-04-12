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

    def _ensure_table(self, dim: int):
        if self.TABLE not in self._db.table_names():
            schema = _SCHEMA.append(pa.field("vector", pa.list_(pa.float32(), dim)))
            self._db.create_table(self.TABLE, schema=schema)

    def add_document(
        self,
        doc_name: str,
        chunks: list[dict],
        embeddings: list[list[float]],
    ) -> int:
        """Add chunks + embeddings for a document. Returns number of rows added."""
        if not chunks:
            return 0

        dim = len(embeddings[0])
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
        if self.TABLE not in self._db.table_names():
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
        if self.TABLE not in self._db.table_names():
            return []
        table = self._db.open_table(self.TABLE)
        arrow_table = table.to_arrow()
        names = arrow_table.column("doc_name").to_pylist()
        return sorted(set(names))

    def delete_document(self, doc_name: str) -> int:
        """Delete all chunks for a document. Returns rows deleted."""
        if self.TABLE not in self._db.table_names():
            return 0
        table = self._db.open_table(self.TABLE)
        before = table.count_rows()
        table.delete(f"doc_name = '{doc_name}'")
        after = table.count_rows()
        return before - after
