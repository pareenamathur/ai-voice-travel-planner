"""Phase 2 closeout — retrieve_guidance Gateway handler tests."""

from __future__ import annotations

import pytest
from src.rag.guidance import retrieve_guidance
from src.rag.models import Chunk, RetrievedChunk


class StubRetriever:
    def __init__(self, results: list[RetrievedChunk]) -> None:
        self._results = results
        self.calls: list[tuple[str, str, int]] = []

    async def retrieve_query(self, *, query: str, city: str, top_k: int = 5) -> list[RetrievedChunk]:
        self.calls.append((query, city, top_k))
        return self._results


def _sample_chunk() -> RetrievedChunk:
    chunk = Chunk(
        chunk_id="jaipur:wikivoyage::see::0001",
        doc_id="jaipur:wikivoyage",
        text="Hawa Mahal is famous for its pink facade.",
        section="See",
        citation_id="jaipur:wikivoyage#see#0001",
        source_url="https://en.wikivoyage.org/wiki/Jaipur",
        metadata={"document_id": "jaipur:wikivoyage", "city": "jaipur"},
    )
    return RetrievedChunk(chunk=chunk, score=0.88)


@pytest.mark.asyncio
async def test_retrieve_guidance_returns_chunks_and_citations():
    retriever = StubRetriever([_sample_chunk()])
    payload = await retrieve_guidance(
        query="Hawa Mahal",
        city="Jaipur",
        top_k=3,
        retriever=retriever,
    )

    assert payload["source"] == "rag"
    assert len(payload["chunks"]) == 1
    assert payload["chunks"][0]["text"].startswith("Hawa Mahal")
    assert payload["citations"][0]["citation_id"] == "jaipur:wikivoyage#see#0001"
    assert retriever.calls == [("Hawa Mahal", "jaipur", 3)]


@pytest.mark.asyncio
async def test_retrieve_guidance_empty_on_missing_inputs():
    payload = await retrieve_guidance(query="", city="Jaipur")
    assert payload == {"source": "rag", "chunks": [], "citations": []}
