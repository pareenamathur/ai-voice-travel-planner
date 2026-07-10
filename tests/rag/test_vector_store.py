"""Phase 2 Task 5 — vector store unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.rag.vector_store import (
    ChromaVectorStore,
    VectorStoreConfig,
    build_index_records,
    embeddings_fingerprint,
    load_index_manifest,
)

SAMPLE_CHUNKS_PAYLOAD = {
    "document_id": "jaipur:wikivoyage",
    "city": "jaipur",
    "source": "wikivoyage",
    "chunks": [
        {
            "chunk_id": "jaipur:wikivoyage::intro::0000",
            "document_id": "jaipur:wikivoyage",
            "city": "jaipur",
            "source": "wikivoyage",
            "section": "_intro",
            "citation_id": "jaipur:wikivoyage#intro#0000",
            "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
            "chunk_index": 0,
            "text": "Intro paragraph.",
        },
        {
            "chunk_id": "jaipur:wikivoyage::see::0001",
            "document_id": "jaipur:wikivoyage",
            "city": "jaipur",
            "source": "wikivoyage",
            "section": "See",
            "citation_id": "jaipur:wikivoyage#see#0001",
            "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
            "chunk_index": 1,
            "text": "See content.",
        },
    ],
}

SAMPLE_EMBEDDINGS_PAYLOAD = {
    "document_id": "jaipur:wikivoyage",
    "city": "jaipur",
    "source": "wikivoyage",
    "provider": "openai",
    "embedding_model": "text-embedding-3-small",
    "chunks_fingerprint": "abc123",
    "embeddings": [
        {
            "chunk_id": "jaipur:wikivoyage::intro::0000",
            "citation_id": "jaipur:wikivoyage#intro#0000",
            "embedding": [0.1, 0.2, 0.3],
            "metadata": {
                "document_id": "jaipur:wikivoyage",
                "city": "jaipur",
                "source": "wikivoyage",
                "section": "_intro",
                "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
                "chunk_index": 0,
            },
            "embedding_model": "text-embedding-3-small",
        },
        {
            "chunk_id": "jaipur:wikivoyage::see::0001",
            "citation_id": "jaipur:wikivoyage#see#0001",
            "embedding": [0.4, 0.5, 0.6],
            "metadata": {
                "document_id": "jaipur:wikivoyage",
                "city": "jaipur",
                "source": "wikivoyage",
                "section": "See",
                "source_url": "https://en.wikivoyage.org/wiki/Jaipur",
                "chunk_index": 1,
            },
            "embedding_model": "text-embedding-3-small",
        },
    ],
}


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _make_store(tmp_path: Path) -> ChromaVectorStore:
    persist_dir = tmp_path / "chroma"
    config = VectorStoreConfig(
        backend="chroma",
        collection="test_travel_guidance",
        persist_dir=persist_dir,
    )
    return ChromaVectorStore(config=config)


def test_build_index_records_joins_chunk_text_and_metadata():
    records = build_index_records(
        embeddings_payload=SAMPLE_EMBEDDINGS_PAYLOAD,
        chunks_payload=SAMPLE_CHUNKS_PAYLOAD,
    )

    assert len(records) == 2
    assert records[0]["id"] == "jaipur:wikivoyage::intro::0000"
    assert records[0]["document"] == "Intro paragraph."
    assert records[0]["metadata"]["citation_id"] == "jaipur:wikivoyage#intro#0000"
    assert records[0]["metadata"]["city"] == "jaipur"
    assert records[0]["metadata"]["source"] == "wikivoyage"
    assert records[0]["metadata"]["section"] == "_intro"
    assert records[0]["metadata"]["chunk_index"] == 0
    assert records[0]["metadata"]["document_id"] == "jaipur:wikivoyage"


@pytest.mark.asyncio
async def test_chroma_collection_creation_and_health(tmp_path: Path):
    store = _make_store(tmp_path)
    health = await store.health()

    assert health["backend"] == "chroma"
    assert health["collection"] == "test_travel_guidance"
    assert health["count"] == 0


@pytest.mark.asyncio
async def test_index_embeddings_file_indexes_records(tmp_path: Path):
    chunks_dir = tmp_path / "chunks"
    embeddings_dir = tmp_path / "embeddings"
    _write_json(chunks_dir / "jaipur" / "wikivoyage.json", SAMPLE_CHUNKS_PAYLOAD)
    embeddings_path = _write_json(
        embeddings_dir / "jaipur" / "wikivoyage.json",
        SAMPLE_EMBEDDINGS_PAYLOAD,
    )

    store = _make_store(tmp_path)
    indexed = await store.index_embeddings_file(
        embeddings_path,
        chunks_dir=chunks_dir,
    )

    assert indexed is True
    health = await store.health()
    assert health["count"] == 2

    results = store.collection.get(
        ids=["jaipur:wikivoyage::intro::0000"],
        include=["documents", "metadatas", "embeddings"],
    )
    assert results["documents"][0] == "Intro paragraph."
    assert results["metadatas"][0]["section"] == "_intro"
    embedding = [float(value) for value in results["embeddings"][0]]
    assert embedding == pytest.approx([0.1, 0.2, 0.3])


@pytest.mark.asyncio
async def test_index_embeddings_file_is_idempotent(tmp_path: Path):
    chunks_dir = tmp_path / "chunks"
    embeddings_dir = tmp_path / "embeddings"
    _write_json(chunks_dir / "jaipur" / "wikivoyage.json", SAMPLE_CHUNKS_PAYLOAD)
    embeddings_path = _write_json(
        embeddings_dir / "jaipur" / "wikivoyage.json",
        SAMPLE_EMBEDDINGS_PAYLOAD,
    )

    store = _make_store(tmp_path)
    first = await store.index_embeddings_file(embeddings_path, chunks_dir=chunks_dir)
    second = await store.index_embeddings_file(embeddings_path, chunks_dir=chunks_dir)

    assert first is True
    assert second is False
    health = await store.health()
    assert health["count"] == 2

    manifest = load_index_manifest(store.config.persist_dir)
    assert manifest["files"]["jaipur/wikivoyage.json"]["fingerprint"] == embeddings_fingerprint(
        embeddings_path
    )


@pytest.mark.asyncio
async def test_index_embeddings_file_prevents_duplicates_on_reindex(tmp_path: Path):
    chunks_dir = tmp_path / "chunks"
    embeddings_dir = tmp_path / "embeddings"
    _write_json(chunks_dir / "jaipur" / "wikivoyage.json", SAMPLE_CHUNKS_PAYLOAD)
    embeddings_path = _write_json(
        embeddings_dir / "jaipur" / "wikivoyage.json",
        SAMPLE_EMBEDDINGS_PAYLOAD,
    )

    store = _make_store(tmp_path)
    await store.index_embeddings_file(embeddings_path, chunks_dir=chunks_dir)

    updated_payload = json.loads(embeddings_path.read_text(encoding="utf-8"))
    updated_payload["embeddings"][0]["embedding"] = [0.9, 0.8, 0.7]
    embeddings_path.write_text(
        json.dumps(updated_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    reindexed = await store.index_embeddings_file(
        embeddings_path,
        chunks_dir=chunks_dir,
        force_refresh=True,
    )

    assert reindexed is True
    health = await store.health()
    assert health["count"] == 2

    results = store.collection.get(
        ids=["jaipur:wikivoyage::intro::0000"],
        include=["embeddings"],
    )
    embedding = [float(value) for value in results["embeddings"][0]]
    assert embedding == pytest.approx([0.9, 0.8, 0.7])


@pytest.mark.asyncio
async def test_index_city_force_refresh_rebuilds_collection(tmp_path: Path):
    chunks_dir = tmp_path / "chunks"
    embeddings_dir = tmp_path / "embeddings"
    _write_json(chunks_dir / "jaipur" / "wikivoyage.json", SAMPLE_CHUNKS_PAYLOAD)
    _write_json(embeddings_dir / "jaipur" / "wikivoyage.json", SAMPLE_EMBEDDINGS_PAYLOAD)

    store = _make_store(tmp_path)
    await store.index_city("jaipur", embeddings_dir=embeddings_dir, chunks_dir=chunks_dir)
    assert (await store.health())["count"] == 2

    await store.index_city(
        "jaipur",
        embeddings_dir=embeddings_dir,
        chunks_dir=chunks_dir,
        force_refresh=True,
    )
    assert (await store.health())["count"] == 2

    manifest = load_index_manifest(store.config.persist_dir)
    assert manifest["files"]["jaipur/wikivoyage.json"]["fingerprint"]
