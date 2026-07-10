"""Embeddings generation pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx

from src.rag.embeddings.config import EmbeddingsConfig
from src.rag.embeddings.factory import EmbeddingsProviderFactory
from src.rag.embeddings.providers.base import EmbeddingsProvider

DEFAULT_CHUNKS_DIR = Path("data/chunks")
DEFAULT_EMBEDDINGS_DIR = Path("data/embeddings")


def chunks_fingerprint(chunks_path: Path) -> str:
    """Stable fingerprint of a chunk JSON file for idempotent embedding runs."""
    return hashlib.sha256(chunks_path.read_bytes()).hexdigest()


def embeddings_file_path(embeddings_dir: Path, city: str, source: str) -> Path:
    """Return the JSON path for a source's embeddings."""
    return embeddings_dir / city / f"{source}.json"


def chunk_metadata_reference(chunk: dict[str, Any]) -> dict[str, Any]:
    """Metadata carried alongside each embedding (no chunk text duplication)."""
    return {
        "document_id": chunk.get("document_id"),
        "city": chunk.get("city"),
        "source": chunk.get("source"),
        "section": chunk.get("section"),
        "source_url": chunk.get("source_url"),
        "chunk_index": chunk.get("chunk_index"),
    }


def embedding_record_to_dict(
    *,
    chunk_id: str,
    citation_id: str,
    vector: list[float],
    metadata: dict[str, Any],
    embedding_model: str,
) -> dict[str, Any]:
    """Serialize one embedding record for JSON persistence."""
    return {
        "chunk_id": chunk_id,
        "citation_id": citation_id,
        "embedding": vector,
        "metadata": metadata,
        "embedding_model": embedding_model,
    }


def load_chunks_payload(chunks_path: Path) -> dict[str, Any]:
    """Load a chunk JSON file produced by the chunking pipeline."""
    return json.loads(chunks_path.read_text(encoding="utf-8"))


def load_embeddings_payload(embeddings_path: Path) -> dict[str, Any]:
    """Load a persisted embeddings JSON file."""
    return json.loads(embeddings_path.read_text(encoding="utf-8"))


def should_skip_embedding(
    *,
    embeddings_path: Path,
    chunks_path: Path,
    embedding_model: str,
    force_refresh: bool,
) -> bool:
    """Return True when an up-to-date embeddings file already exists."""
    if force_refresh or not embeddings_path.exists():
        return False

    payload = load_embeddings_payload(embeddings_path)
    if payload.get("embedding_model") != embedding_model:
        return False
    if payload.get("chunks_fingerprint") != chunks_fingerprint(chunks_path):
        return False
    return True


async def generate_embeddings_for_chunks_file(
    chunks_path: Path,
    *,
    provider: EmbeddingsProvider,
    config: EmbeddingsConfig,
    embeddings_dir: Path = DEFAULT_EMBEDDINGS_DIR,
    force_refresh: bool = False,
) -> Path | None:
    """Generate embeddings for one chunk file and persist to disk.

    Returns the embeddings path, or ``None`` when generation was skipped.
    """
    payload = load_chunks_payload(chunks_path)
    city = str(payload["city"])
    source = str(payload["source"])
    chunks: list[dict[str, Any]] = payload["chunks"]
    if not chunks:
        raise ValueError(f"No chunks found in {chunks_path}")

    embeddings_path = embeddings_file_path(embeddings_dir, city, source)
    if should_skip_embedding(
        embeddings_path=embeddings_path,
        chunks_path=chunks_path,
        embedding_model=config.model,
        force_refresh=force_refresh,
    ):
        return None

    texts = [str(chunk["text"]) for chunk in chunks]
    vectors = await provider.embed_texts(texts)
    if len(vectors) != len(chunks):
        raise ValueError(
            f"Embedding count mismatch for {chunks_path}: "
            f"expected {len(chunks)}, got {len(vectors)}"
        )

    records = [
        embedding_record_to_dict(
            chunk_id=str(chunk["chunk_id"]),
            citation_id=str(chunk["citation_id"]),
            vector=vector.vector,
            metadata=chunk_metadata_reference(chunk),
            embedding_model=config.model,
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    output = {
        "document_id": payload.get("document_id"),
        "city": city,
        "source": source,
        "provider": config.provider,
        "embedding_model": config.model,
        "chunks_fingerprint": chunks_fingerprint(chunks_path),
        "embeddings": records,
    }
    content = json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    embeddings_path.parent.mkdir(parents=True, exist_ok=True)
    embeddings_path.write_text(content, encoding="utf-8")
    return embeddings_path


async def generate_embeddings_for_city(
    city: str,
    *,
    provider: EmbeddingsProvider | None = None,
    config: EmbeddingsConfig | None = None,
    chunks_dir: Path = DEFAULT_CHUNKS_DIR,
    embeddings_dir: Path = DEFAULT_EMBEDDINGS_DIR,
    force_refresh: bool = False,
    http_client: httpx.AsyncClient | None = None,
) -> list[Path]:
    """Generate embeddings for every chunk file under ``data/chunks/<city>/``."""
    resolved_config = config or EmbeddingsConfig.from_settings()
    resolved_provider = provider or EmbeddingsProviderFactory.create(
        resolved_config,
        http_client=http_client,
    )

    city_dir = chunks_dir / city
    if not city_dir.is_dir():
        return []

    written: list[Path] = []
    for chunks_path in sorted(city_dir.glob("*.json")):
        result = await generate_embeddings_for_chunks_file(
            chunks_path,
            provider=resolved_provider,
            config=resolved_config,
            embeddings_dir=embeddings_dir,
            force_refresh=force_refresh,
        )
        if result is not None:
            written.append(result)

    return written
