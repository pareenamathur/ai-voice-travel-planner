#!/usr/bin/env python3
"""Run the Phase 2 RAG pipeline for a city.

Executes in order:
  1. ingest   — download raw HTML and build cleaned corpus
  2. chunk    — section-aware chunk JSON
  3. embed    — embedding JSON via OpenAI-compatible API
  4. index    — Chroma vector store + index manifest

Usage:
  python scripts/ingest_rag.py
  python scripts/ingest_rag.py --city jaipur
  python scripts/ingest_rag.py --city jaipur --force-refresh
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure project root is importable when invoked as a script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.config import settings  # noqa: E402
from src.rag.chunker import chunk_documents  # noqa: E402
from src.rag.embeddings import (  # noqa: E402
    DEFAULT_CHUNKS_DIR,
    DEFAULT_EMBEDDINGS_DIR,
    generate_embeddings_for_city,
)
from src.rag.ingest import ingest_city  # noqa: E402
from src.rag.vector_store import index_city  # noqa: E402

DEFAULT_CHUNKS_DIR_PATH = Path("data/chunks")
DEFAULT_EMBEDDINGS_DIR_PATH = Path("data/embeddings")


async def run_rag_pipeline(*, city: str, force_refresh: bool = False) -> None:
    city = city.strip().lower()
    print(f"Phase 2 RAG pipeline — city={city!r}, force_refresh={force_refresh}")

    print("\n[1/4] Ingesting sources...")
    documents = await ingest_city(city=city, force_refresh=force_refresh)
    if not documents:
        raise SystemExit(f"No documents ingested for city={city!r}. Check src/rag/config.py.")
    print(f"  Ingested {len(documents)} document(s).")

    print("\n[2/4] Chunking documents...")
    chunks = chunk_documents(
        documents,
        chunks_dir=DEFAULT_CHUNKS_DIR_PATH,
        force_refresh=force_refresh,
    )
    print(f"  Wrote {len(chunks)} chunk(s) under {DEFAULT_CHUNKS_DIR_PATH / city}/")

    if not settings.embedding_api_key:
        raise SystemExit(
            "EMBEDDING_API_KEY is not set. Embeddings require an OpenAI-compatible API key.\n"
            "Copy .env.example to .env and set EMBEDDING_API_KEY before running embed/index steps."
        )

    print("\n[3/4] Generating embeddings...")
    embedding_paths = await generate_embeddings_for_city(
        city,
        force_refresh=force_refresh,
    )
    if embedding_paths:
        embed_dir = DEFAULT_EMBEDDINGS_DIR_PATH / city
        print(f"  Wrote {len(embedding_paths)} embedding file(s) under {embed_dir}/")
    else:
        print(f"  Embeddings up to date under {DEFAULT_EMBEDDINGS_DIR_PATH / city}/")

    print("\n[4/4] Building Chroma index...")
    indexed_paths = await index_city(
        city,
        embeddings_dir=DEFAULT_EMBEDDINGS_DIR,
        chunks_dir=DEFAULT_CHUNKS_DIR,
        force_refresh=force_refresh,
    )
    if indexed_paths:
        print(f"  Indexed {len(indexed_paths)} embedding file(s).")
    else:
        print("  Chroma index up to date.")

    chroma_dir = settings.chroma_persist_dir
    manifest = chroma_dir / "index_manifest.json"
    print("\nPipeline complete.")
    print(f"  raw:        data/raw/{city}/")
    print(f"  corpus:     data/corpus/{city}/")
    print(f"  chunks:     data/chunks/{city}/")
    print(f"  embeddings: data/embeddings/{city}/")
    print(f"  chroma:     {chroma_dir}/")
    if manifest.exists():
        print(f"  manifest:   {manifest}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase 2 RAG pipeline for a city.")
    parser.add_argument(
        "--city",
        default="jaipur",
        help="City slug to process (default: jaipur)",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-download, re-chunk, re-embed, and rebuild the Chroma index",
    )
    args = parser.parse_args()
    asyncio.run(run_rag_pipeline(city=args.city, force_refresh=args.force_refresh))


if __name__ == "__main__":
    main()
