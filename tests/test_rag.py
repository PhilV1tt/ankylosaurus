"""Tests for RAG modules (chunker, store)."""



# --- Chunker tests ---

def test_chunk_text_splits():
    from ankylosaurus.modules.rag.chunker import chunk_text

    pages = [{"page": 1, "text": "A" * 1000}]
    chunks = chunk_text(pages, chunk_size=200, overlap=20)
    assert len(chunks) > 1
    assert all(len(c["text"]) <= 200 for c in chunks)


def test_chunk_text_preserves_overlap():
    from ankylosaurus.modules.rag.chunker import chunk_text

    pages = [{"page": 1, "text": "word " * 200}]
    chunks = chunk_text(pages, chunk_size=100, overlap=20)
    # Adjacent chunks should share some text (overlap)
    if len(chunks) >= 2:
        end_of_first = chunks[0]["text"][-20:]
        assert end_of_first in chunks[1]["text"]


def test_chunk_text_metadata():
    from ankylosaurus.modules.rag.chunker import chunk_text

    pages = [
        {"page": 1, "text": "First page content."},
        {"page": 2, "text": "Second page content."},
    ]
    chunks = chunk_text(pages, chunk_size=5000)
    assert chunks[0]["metadata"]["page"] == 1
    assert chunks[1]["metadata"]["page"] == 2
    assert chunks[0]["metadata"]["chunk_id"] == 0
    assert chunks[1]["metadata"]["chunk_id"] == 1


def test_chunk_text_empty():
    from ankylosaurus.modules.rag.chunker import chunk_text

    chunks = chunk_text([], chunk_size=512)
    assert chunks == []


# --- Store tests ---

def test_store_add_and_search(tmp_path):
    from ankylosaurus.modules.rag.store import VectorStore

    store = VectorStore(db_path=str(tmp_path / "test.lance"))

    chunks = [
        {"text": "hello world", "metadata": {"page": 1, "chunk_id": 0}},
        {"text": "goodbye world", "metadata": {"page": 1, "chunk_id": 1}},
    ]
    embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

    n = store.add_document("test_doc", chunks, embeddings)
    assert n == 2

    results = store.search([1.0, 0.0, 0.0], top_k=1)
    assert len(results) == 1
    assert results[0]["text"] == "hello world"
    assert results[0]["doc_name"] == "test_doc"


def test_store_list_documents(tmp_path):
    from ankylosaurus.modules.rag.store import VectorStore

    store = VectorStore(db_path=str(tmp_path / "test.lance"))

    chunks = [{"text": "a", "metadata": {"page": 1, "chunk_id": 0}}]
    store.add_document("doc_a", chunks, [[1.0, 0.0]])
    store.add_document("doc_b", chunks, [[0.0, 1.0]])

    docs = store.list_documents()
    assert "doc_a" in docs
    assert "doc_b" in docs


def test_store_delete_document(tmp_path):
    from ankylosaurus.modules.rag.store import VectorStore

    store = VectorStore(db_path=str(tmp_path / "test.lance"))

    chunks = [{"text": "a", "metadata": {"page": 1, "chunk_id": 0}}]
    store.add_document("to_delete", chunks, [[1.0, 0.0]])

    n = store.delete_document("to_delete")
    assert n == 1
    assert store.list_documents() == []


def test_store_empty_search(tmp_path):
    from ankylosaurus.modules.rag.store import VectorStore

    store = VectorStore(db_path=str(tmp_path / "test.lance"))
    results = store.search([1.0, 0.0], top_k=5)
    assert results == []
