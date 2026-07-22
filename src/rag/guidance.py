"""Gateway-facing ``retrieve_guidance`` tool (Phase 2 closeout)."""

from __future__ import annotations

from typing import Any

from src.rag.models import RetrievedChunk
from src.rag.retriever import SemanticRetriever, retrieve


def _chunk_to_citation(chunk: RetrievedChunk) -> dict[str, Any]:
    meta = chunk.chunk.metadata or {}
    document_id = meta.get("document_id") or chunk.chunk.doc_id
    source_url = chunk.chunk.source_url
    friendly = _friendly_rag_label(document_id, source_url, chunk.chunk.section)
    return {
        "citation_id": chunk.chunk.citation_id or chunk.chunk.chunk_id,
        "source_url": source_url,
        "section": chunk.chunk.section,
        "document_id": document_id,
        "score": chunk.score,
        "metadata": {
            **dict(meta),
            "source": friendly,
            "label": friendly,
        },
    }


def _friendly_rag_label(
    document_id: Any,
    source_url: str | None,
    section: str | None,
) -> str:
    blob = f"{document_id or ''} {source_url or ''} {section or ''}".lower()
    if "wikivoyage" in blob:
        return "Wikivoyage"
    if "wikipedia" in blob:
        return "Wikipedia"
    if "rajasthan" in blob:
        return "Rajasthan Tourism"
    if "jaipur" in blob and "tourism" in blob:
        return "Jaipur Tourism"
    if "tourism" in blob:
        return "Official tourism guides"
    if section and str(section).strip():
        return str(section).strip()
    if document_id:
        text = str(document_id)
        parts = text.split(":")
        return parts[-1].replace("_", " ").replace("-", " ").title()
    return "Travel guidance"


def _chunk_to_payload(chunk: RetrievedChunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk.chunk_id,
        "text": chunk.chunk.text,
        "section": chunk.chunk.section,
        "citation_id": chunk.chunk.citation_id,
        "source_url": chunk.chunk.source_url,
        "score": chunk.score,
        "metadata": dict(chunk.chunk.metadata or {}),
    }


async def retrieve_guidance(
    *,
    query: str,
    city: str,
    top_k: int = 5,
    retriever: SemanticRetriever | None = None,
) -> dict[str, Any]:
    """MCP Gateway handler for ``retrieve_guidance``.

    Returns JSON-serializable guidance chunks and normalized citations for the
    Knowledge Agent and Sources panel.
    """
    normalized_city = (city or "").strip()
    normalized_query = (query or "").strip()
    if not normalized_city or not normalized_query:
        return {"source": "rag", "chunks": [], "citations": []}

    city_key = normalized_city.lower()
    if retriever is not None:
        results = await retriever.retrieve_query(
            query=normalized_query,
            city=city_key,
            top_k=top_k,
        )
    else:
        results = await retrieve(normalized_query, city_key, top_k=top_k)

    chunks = [_chunk_to_payload(item) for item in results]
    citations = [_chunk_to_citation(item) for item in results]
    return {
        "source": "rag",
        "chunks": chunks,
        "citations": citations,
    }
