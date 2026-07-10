"""Semantic retrieval for RAG (Phase 2 Task 6).

Orchestrates query embedding generation and Chroma similarity search.
Gateway wiring and Knowledge Agent integration are out of scope.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from src.rag.embeddings import (
    EmbeddingsConfig,
    EmbeddingsProvider,
    EmbeddingsProviderFactory,
)
from src.rag.models import Chunk, RetrievalQuery, RetrievedChunk
from src.rag.vector_store import ChromaVectorStore, VectorStore


@dataclass(frozen=True, slots=True)
class RetrieverConfig:
    """Retriever configuration."""

    top_k_default: int = 5


class Retriever(ABC):
    """High-level retrieval API for grounded travel guidance."""

    @abstractmethod
    async def retrieve(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        """Retrieve the most relevant chunks for the query."""


def _distance_to_score(distance: float) -> float:
    """Convert Chroma cosine distance to a similarity score (higher is better)."""
    return 1.0 - distance


def _metadata_to_chunk(*, document: str, metadata: dict[str, Any]) -> Chunk:
    chunk_id = str(metadata.get("chunk_id", ""))
    document_id = str(metadata.get("document_id", ""))
    return Chunk(
        chunk_id=chunk_id,
        doc_id=document_id,
        text=document,
        section=str(metadata.get("section", "")) or None,
        citation_id=str(metadata.get("citation_id", "")) or None,
        source_url=str(metadata.get("source_url", "")) or None,
        metadata={
            "city": metadata.get("city"),
            "source": metadata.get("source"),
            "chunk_index": metadata.get("chunk_index"),
            "document_id": document_id,
            "citation_id": metadata.get("citation_id"),
            "section": metadata.get("section"),
            "source_url": metadata.get("source_url"),
        },
    )


def _chroma_results_to_retrieved_chunks(results: dict[str, Any]) -> list[RetrievedChunk]:
    ids = results.get("ids") or []
    if not ids or not ids[0]:
        return []

    row_ids = ids[0]
    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    retrieved: list[RetrievedChunk] = []
    for index, chunk_id in enumerate(row_ids):
        metadata = metadatas[index] or {}
        distance = float(distances[index]) if index < len(distances) else 0.0
        chunk = _metadata_to_chunk(document=documents[index] or "", metadata=metadata)
        retrieved.append(
            RetrievedChunk(
                chunk=chunk,
                score=_distance_to_score(distance),
            )
        )

    retrieved.sort(
        key=lambda item: (
            -(item.score or 0.0),
            item.chunk.chunk_id,
        )
    )
    return retrieved


class SemanticRetriever(Retriever):
    """Retriever that embeds queries and searches a Chroma-backed vector store."""

    def __init__(
        self,
        *,
        vector_store: VectorStore,
        embeddings_provider: EmbeddingsProvider,
        config: RetrieverConfig | None = None,
    ) -> None:
        self._vector_store = vector_store
        self._embeddings_provider = embeddings_provider
        self._config = config or RetrieverConfig()

    def _require_chroma_store(self) -> ChromaVectorStore:
        if not isinstance(self._vector_store, ChromaVectorStore):
            raise TypeError("SemanticRetriever requires a ChromaVectorStore instance")
        return self._vector_store

    async def retrieve(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        city = str((request.filters or {}).get("city", ""))
        return await self.retrieve_query(
            query=request.query,
            city=city,
            top_k=request.top_k,
        )

    async def retrieve_query(
        self,
        *,
        query: str,
        city: str,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        if not query.strip() or not city.strip():
            return []

        resolved_top_k = top_k if top_k is not None else self._config.top_k_default
        store = self._require_chroma_store()

        if store.collection.count() == 0:
            return []

        vectors = await self._embeddings_provider.embed_texts([query])
        if not vectors:
            return []

        results = store.collection.query(
            query_embeddings=[vectors[0].vector],
            n_results=resolved_top_k,
            where={"city": city},
            include=["documents", "metadatas", "distances"],
        )
        return _chroma_results_to_retrieved_chunks(results)


async def retrieve(
    query: str,
    city: str,
    top_k: int = 5,
    *,
    vector_store: ChromaVectorStore | None = None,
    embeddings_provider: EmbeddingsProvider | None = None,
    config: RetrieverConfig | None = None,
) -> list[RetrievedChunk]:
    """Retrieve top-k chunks for a query scoped to a city."""
    retriever = SemanticRetriever(
        vector_store=vector_store or ChromaVectorStore(),
        embeddings_provider=embeddings_provider
        or EmbeddingsProviderFactory.create(EmbeddingsConfig.from_settings()),
        config=config,
    )
    return await retriever.retrieve_query(query=query, city=city, top_k=top_k)
