"""Benchmark RAG retrieval: Jina v5 MLX (ANKYLOSAURUS proxy) on EU AI Act PDF."""

import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from rich.console import Console
from rich.table import Table

from ankylosaurus.modules.rag.embedder import Embedder
from ankylosaurus.modules.rag.store import VectorStore

QUESTIONS = [
    "Quels sont les systemes IA interdits selon l'Article 5 ?",
    "Quelles sont les sanctions en cas de non-conformite ?",
    "Quels sont les systemes IA a haut risque ?",
]

console = Console()


def benchmark_retrieval():
    embedder = Embedder()
    store = VectorStore()

    docs = store.list_documents()
    if not docs:
        console.print("[red]No documents ingested. Run 'ankylosaurus rag ingest <pdf>' first.[/red]")
        return

    console.print(f"\n[bold]RAG Benchmark -- Jina v5 MLX + LanceDB[/bold]")
    console.print(f"Documents: {', '.join(docs)}\n")

    # Warm up embedder
    console.print("Loading model...", end=" ")
    t0 = time.perf_counter()
    embedder.embed_query("warmup")
    load_time = time.perf_counter() - t0
    console.print(f"[green]{load_time:.2f}s[/green]\n")

    for i, question in enumerate(QUESTIONS, 1):
        console.print(f"[bold]Q{i}: {question}[/bold]")

        # Embed query
        t0 = time.perf_counter()
        query_vec = embedder.embed_query(question)
        embed_time = time.perf_counter() - t0

        # Search
        t1 = time.perf_counter()
        results = store.search(query_vec, top_k=5)
        search_time = time.perf_counter() - t1

        console.print(f"  Embed: {embed_time*1000:.0f}ms | Search: {search_time*1000:.0f}ms | Total: {(embed_time+search_time)*1000:.0f}ms")

        table = Table(show_header=True, header_style="bold", width=100)
        table.add_column("#", width=3)
        table.add_column("Page", width=5)
        table.add_column("Score", width=8)
        table.add_column("Text (truncated)", ratio=1)

        for j, r in enumerate(results, 1):
            text = r["text"][:120].replace("\n", " ")
            table.add_row(str(j), str(r["page"]), f"{r['score']:.4f}", text)

        console.print(table)
        console.print()

    # Summary
    console.print("[bold]Summary[/bold]")
    console.print(f"  Model: Jina v5 MLX (1024-dim)")
    console.print(f"  Store: LanceDB ({len(docs)} doc(s))")
    console.print(f"  Model load: {load_time:.2f}s (cached after first call)")
    console.print("  Compare these results with Open WebUI RAG on the same questions.\n")


if __name__ == "__main__":
    benchmark_retrieval()
