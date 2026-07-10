"""RAG domain models (Phase 2).

These types define the contracts between ingest, chunking, embedding, indexing,
and retrieval. Business logic is intentionally not implemented in Phase 2 Task 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CorpusSource = Literal["wikivoyage", "wikipedia", "custom"]


@dataclass(frozen=True, slots=True)
class Document:
    """A raw source document prior to chunking."""

    doc_id: str
    title: str
    source: CorpusSource
    source_url: str
    language: str = "en"
    metadata: dict[str, Any] | None = None
    text: str = ""


@dataclass(frozen=True, slots=True)
class Chunk:
    """A section-aware chunk suitable for embedding and retrieval."""

    chunk_id: str
    doc_id: str
    text: str
    section: str | None = None
    citation_id: str | None = None
    source_url: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    """Opaque embedding vector produced by an embeddings provider."""

    vector: list[float]
    dim: int


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    """Input to the retriever."""

    query: str
    top_k: int = 5
    filters: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A retrieved chunk with an optional similarity score."""

    chunk: Chunk
    score: float | None = None

