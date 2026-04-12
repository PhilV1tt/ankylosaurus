"""FastAPI RAG proxy — intercepts chat completions, injects retrieved context."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

from .chunker import ingest_pdf
from .embedder import Embedder
from .store import VectorStore

LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234")
RAG_PORT = int(os.getenv("RAG_PORT", "1235"))

app = FastAPI(title="ANKYLOSAURUS RAG Proxy")

# Singletons — initialized at startup
_embedder: Embedder | None = None
_store: VectorStore | None = None


def _get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


def _get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def _build_context_message(chunks: list[dict]) -> str:
    """Format retrieved chunks into a context block for the LLM."""
    if not chunks:
        return ""
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[{i}] (source: {c['doc_name']}, p.{c['page']})\n{c['text']}")
    return (
        "Use the following retrieved context to answer the user's question. "
        "Cite sources when relevant.\n\n"
        + "\n\n".join(parts)
    )


# --- OpenAI-compatible proxy ---

@app.post("/v1/chat/completions")
async def chat_completions(request: dict):
    """Intercept chat requests, add RAG context, forward to LM Studio."""
    import httpx

    messages = request.get("messages", [])
    store = _get_store()

    # Extract last user message for retrieval
    user_msg = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                user_msg = content
            break

    # RAG retrieval
    if user_msg and store.list_documents():
        embedder = _get_embedder()
        query_vec = embedder.embed_query(user_msg)
        chunks = store.search(query_vec, top_k=5)

        if chunks:
            context = _build_context_message(chunks)
            # Inject as system message at the beginning
            messages = [{"role": "system", "content": context}] + messages
            request = {**request, "messages": messages}

    # Forward to LM Studio
    stream = request.get("stream", False)

    async with httpx.AsyncClient(timeout=120.0) as client:
        if stream:
            async def stream_response():
                async with client.stream(
                    "POST",
                    f"{LM_STUDIO_URL}/v1/chat/completions",
                    json=request,
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk

            return StreamingResponse(stream_response(), media_type="text/event-stream")
        else:
            resp = await client.post(
                f"{LM_STUDIO_URL}/v1/chat/completions",
                json=request,
            )
            return resp.json()


@app.post("/v1/embeddings")
async def embeddings(request: dict):
    """OpenAI-compatible embeddings endpoint using Jina v5 MLX."""
    embedder = _get_embedder()
    inp = request.get("input", [])
    if isinstance(inp, str):
        inp = [inp]

    vectors = embedder.embed(inp, task="retrieval.passage")

    data = []
    for i, vec in enumerate(vectors):
        data.append({
            "object": "embedding",
            "embedding": vec,
            "index": i,
        })

    return {
        "object": "list",
        "data": data,
        "model": request.get("model", "jina-v5-mlx"),
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }


@app.get("/v1/models")
async def list_models():
    """Proxy to LM Studio models endpoint."""
    import httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{LM_STUDIO_URL}/v1/models")
        return resp.json()


# --- RAG management ---

@app.post("/ingest")
async def ingest(file: UploadFile = File(...), chunk_size: int = 512, overlap: int = 50):
    """Ingest a PDF: extract text, chunk, embed, store."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    # Save to temp
    tmp_path = Path("/tmp") / file.filename
    content = await file.read()
    tmp_path.write_bytes(content)

    try:
        chunks = ingest_pdf(str(tmp_path), chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            raise HTTPException(400, "No text found in PDF")

        embedder = _get_embedder()
        texts = [c["text"] for c in chunks]
        embeddings = embedder.embed(texts, task="retrieval.passage")

        store = _get_store()
        doc_name = Path(file.filename).stem
        n = store.add_document(doc_name, chunks, embeddings)

        return {"document": doc_name, "chunks": n, "status": "ingested"}
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/documents")
async def documents():
    """List ingested documents."""
    return {"documents": _get_store().list_documents()}


@app.delete("/documents/{name}")
async def delete_document(name: str):
    """Delete a document and its vectors."""
    n = _get_store().delete_document(name)
    if n == 0:
        raise HTTPException(404, f"Document '{name}' not found")
    return {"document": name, "chunks_deleted": n}


def run_server(host: str = "0.0.0.0", port: int | None = None):
    """Start the RAG proxy server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port or RAG_PORT)
