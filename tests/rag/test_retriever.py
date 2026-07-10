"""Phase 2 Task 6 — semantic retrieval unit tests."""

from __future__ import annotations

from collections.abc import Sequence

import chromadb
import pytest
from src.rag.embeddings import EmbeddingsProvider
from src.rag.models import EmbeddingVector
from src.rag.retriever import SemanticRetriever, retrieve
from src.rag.vector_store import ChromaVectorStore, VectorStoreConfig


class MockEmbeddingsProvider(EmbeddingsProvider):
    """Deterministic embedding provider for tests (no API calls)."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        self.calls.append(list(texts))
        return [EmbeddingVector(vector=self._vector, dim=len(self._vector))]


def _make_store(tmp_path, collection_name: str = "test_retrieval") -> ChromaVectorStore:
    persist_dir = tmp_path / "chroma"
    config = VectorStoreConfig(
        backend="chroma",
        collection=collection_name,
        persist_dir=persist_dir,
    )
    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    return ChromaVectorStore(config=config, client=client, collection=collection)


def _index_records(store: ChromaVectorStore, records: list[dict]) -> None:
    store.collection.upsert(
        ids=[record["id"] for record in records],
        embeddings=[record["embedding"] for record in records],
        documents=[record["document"] for record in records],
        metadatas=[record["metadata"] for record in records],
    )


JAIPUR_RECORDS = [
    {
        "id": "jaipur:wikivoyage::intro::0000",
        "embedding": [1.0, 0.0, 0.0],
        "document": "Jaipur intro text.",
        "metadata": {
            "chunk_id": "jaipur:wikivoyage::intro::0000",
            "citation_id": "jaipur:wikivoyage#intro#0000",
            "city": "jaipur",
            "source": "wikivoyage",
            "section": "_intro",
            "chunk_index": 0,
            "document_id": "jaipur:wikivoyage",
            "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
        },
    },
    {
        "id": "jaipur:wikivoyage::see::0001",
        "embedding": [0.0, 1.0, 0.0],
        "document": "Jaipur see text.",
        "metadata": {
            "chunk_id": "jaipur:wikivoyage::see::0001",
            "citation_id": "jaipur:wikivoyage#see#0001",
            "city": "jaipur",
            "source": "wikivoyage",
            "section": "See",
            "chunk_index": 1,
            "document_id": "jaipur:wikivoyage",
            "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
        },
    },
    {
        "id": "jaipur:wikivoyage::eat::0002",
        "embedding": [0.0, 0.0, 1.0],
        "document": "Jaipur eat text.",
        "metadata": {
            "chunk_id": "jaipur:wikivoyage::eat::0002",
            "citation_id": "jaipur:wikivoyage#eat#0002",
            "city": "jaipur",
            "source": "wikivoyage",
            "section": "Eat",
            "chunk_index": 2,
            "document_id": "jaipur:wikivoyage",
            "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
        },
    },
]

MUMBAI_RECORD = {
    "id": "mumbai:wikivoyage::intro::0000",
    "embedding": [0.99, 0.01, 0.0],
    "document": "Mumbai intro text.",
    "metadata": {
        "chunk_id": "mumbai:wikivoyage::intro::0000",
        "citation_id": "mumbai:wikivoyage#intro#0000",
        "city": "mumbai",
        "source": "wikivoyage",
        "section": "_intro",
        "chunk_index": 0,
        "document_id": "mumbai:wikivoyage",
        "source_url": "https://en.wikivoyage.org/wiki/Mumbai",
    },
}


@pytest.mark.asyncio
async def test_retrieve_returns_top_k_chunks(tmp_path):
    store = _make_store(tmp_path)
    _index_records(store, JAIPUR_RECORDS)
    embeddings = MockEmbeddingsProvider([1.0, 0.0, 0.0])

    results = await retrieve(
        "What should I see in Jaipur?",
        city="jaipur",
        top_k=2,
        vector_store=store,
        embeddings_provider=embeddings,
    )

    assert len(results) == 2
    assert results[0].chunk.chunk_id == "jaipur:wikivoyage::intro::0000"
    assert embeddings.calls == [["What should I see in Jaipur?"]]


@pytest.mark.asyncio
async def test_retrieve_respects_city_filter(tmp_path):
    store = _make_store(tmp_path)
    _index_records(store, [*JAIPUR_RECORDS, MUMBAI_RECORD])
    embeddings = MockEmbeddingsProvider([1.0, 0.0, 0.0])

    results = await retrieve(
        "city intro",
        city="jaipur",
        top_k=5,
        vector_store=store,
        embeddings_provider=embeddings,
    )

    assert results
    assert all(item.chunk.metadata["city"] == "jaipur" for item in results)
    assert all("mumbai" not in item.chunk.chunk_id for item in results)


@pytest.mark.asyncio
async def test_retrieve_returns_metadata_and_score(tmp_path):
    store = _make_store(tmp_path)
    _index_records(store, JAIPUR_RECORDS[:1])
    embeddings = MockEmbeddingsProvider([1.0, 0.0, 0.0])

    results = await retrieve(
        "Jaipur intro",
        city="jaipur",
        top_k=1,
        vector_store=store,
        embeddings_provider=embeddings,
    )

    chunk = results[0].chunk
    assert chunk.chunk_id == "jaipur:wikivoyage::intro::0000"
    assert chunk.citation_id == "jaipur:wikivoyage#intro#0000"
    assert chunk.section == "_intro"
    assert chunk.source_url == "https://en.wikivoyage.org/wiki/Jaipur"
    assert chunk.metadata["source"] == "wikivoyage"
    assert chunk.metadata["document_id"] == "jaipur:wikivoyage"
    assert results[0].score is not None
    assert results[0].score == pytest.approx(1.0, abs=1e-5)


@pytest.mark.asyncio
async def test_retrieve_empty_database_returns_empty_list(tmp_path):
    store = _make_store(tmp_path)
    embeddings = MockEmbeddingsProvider([1.0, 0.0, 0.0])

    results = await retrieve(
        "anything",
        city="jaipur",
        vector_store=store,
        embeddings_provider=embeddings,
    )

    assert results == []
    assert embeddings.calls == []


@pytest.mark.asyncio
async def test_retrieve_has_deterministic_ordering(tmp_path):
    store = _make_store(tmp_path)
    tied_records = [
        {
            "id": "jaipur:wikivoyage::b::0001",
            "embedding": [1.0, 0.0, 0.0],
            "document": "B chunk",
            "metadata": {
                "chunk_id": "jaipur:wikivoyage::b::0001",
                "citation_id": "jaipur:wikivoyage#b#0001",
                "city": "jaipur",
                "source": "wikivoyage",
                "section": "B",
                "chunk_index": 1,
                "document_id": "jaipur:wikivoyage",
                "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
            },
        },
        {
            "id": "jaipur:wikivoyage::a::0000",
            "embedding": [1.0, 0.0, 0.0],
            "document": "A chunk",
            "metadata": {
                "chunk_id": "jaipur:wikivoyage::a::0000",
                "citation_id": "jaipur:wikivoyage#a#0000",
                "city": "jaipur",
                "source": "wikivoyage",
                "section": "A",
                "chunk_index": 0,
                "document_id": "jaipur:wikivoyage",
                "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
            },
        },
    ]
    _index_records(store, tied_records)
    embeddings = MockEmbeddingsProvider([1.0, 0.0, 0.0])
    retriever = SemanticRetriever(vector_store=store, embeddings_provider=embeddings)

    first = await retriever.retrieve_query(query="tie", city="jaipur", top_k=2)
    second = await retriever.retrieve_query(query="tie", city="jaipur", top_k=2)

    assert [item.chunk.chunk_id for item in first] == [item.chunk.chunk_id for item in second]
    assert [item.chunk.chunk_id for item in first] == sorted(
        [item.chunk.chunk_id for item in first]
    )
