"""PDF text extraction and chunking for RAG ingestion."""

from __future__ import annotations

import bisect



def extract_text(pdf_path: str) -> list[dict]:
    """Extract text from a PDF, page by page.

    Returns list of {"page": int, "text": str}.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            pages.append({"page": i + 1, "text": text})
    doc.close()
    return pages


def chunk_text(
    pages: list[dict],
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[dict]:
    """Split page texts into overlapping chunks.

    Args:
        pages: Output of extract_text().
        chunk_size: Max characters per chunk.
        overlap: Character overlap between consecutive chunks.

    Returns list of {"text": str, "metadata": {"page": int, "chunk_id": int}}.
    """
    chunks = []
    chunk_id = 0

    for page_info in pages:
        text = page_info["text"]
        page_num = page_info["page"]
        start = 0

        # Precompute paragraph break positions for O(n + k log n) chunking
        breaks = [i for i in range(len(text) - 1) if text[i:i+2] == "\n\n"]

        while start < len(text):
            end = start + chunk_size

            # Try to break at paragraph boundary via binary search
            if end < len(text) and breaks:
                idx = bisect.bisect_right(breaks, end) - 1
                if idx >= 0 and breaks[idx] > start + chunk_size // 2:
                    end = breaks[idx] + 2

            chunk_text_str = text[start:end].strip()
            if chunk_text_str:
                chunks.append({
                    "text": chunk_text_str,
                    "metadata": {"page": page_num, "chunk_id": chunk_id},
                })
                chunk_id += 1

            start = end - overlap if end < len(text) else len(text)

    return chunks


def ingest_pdf(pdf_path: str, chunk_size: int = 512, overlap: int = 50) -> list[dict]:
    """Convenience: extract + chunk a PDF in one call."""
    pages = extract_text(pdf_path)
    return chunk_text(pages, chunk_size=chunk_size, overlap=overlap)
