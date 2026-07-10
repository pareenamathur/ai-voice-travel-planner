"""Phase 2 Task 4 — embeddings generation unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from src.rag.embeddings import (
    EmbeddingsConfig,
    OpenAICompatibleEmbeddingsProvider,
    chunk_metadata_reference,
    generate_embeddings_for_chunks_file,
    load_embeddings_payload,
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


def _write_chunks(path: Path, payload: dict | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload or SAMPLE_CHUNKS_PAYLOAD, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _mock_embeddings_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content.decode())
    texts = body["input"]
    data = [
        {
            "index": index,
            "embedding": [float(index), 0.25, 0.5],
        }
        for index, _ in enumerate(texts)
    ]
    return httpx.Response(200, json={"data": data})


@pytest.mark.asyncio
async def test_generate_embeddings_writes_expected_schema(tmp_path: Path):
    chunks_path = _write_chunks(tmp_path / "chunks" / "jaipur" / "wikivoyage.json")
    embeddings_dir = tmp_path / "embeddings"
    config = EmbeddingsConfig(
        provider="openai",
        model="text-embedding-3-small",
        api_key="test-key",
        base_url="https://api.example.com/v1",
    )

    transport = httpx.MockTransport(_mock_embeddings_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleEmbeddingsProvider(config=config, http_client=client)
        result = await generate_embeddings_for_chunks_file(
            chunks_path,
            provider=provider,
            config=config,
            embeddings_dir=embeddings_dir,
        )

    assert result is not None
    payload = load_embeddings_payload(result)
    assert payload["city"] == "jaipur"
    assert payload["source"] == "wikivoyage"
    assert payload["embedding_model"] == "text-embedding-3-small"
    assert payload["provider"] == "openai"
    assert "chunks_fingerprint" in payload
    assert len(payload["embeddings"]) == 2

    record = payload["embeddings"][0]
    assert set(record.keys()) == {
        "chunk_id",
        "citation_id",
        "embedding",
        "metadata",
        "embedding_model",
    }
    assert record["chunk_id"] == "jaipur:wikivoyage::intro::0000"
    assert record["citation_id"] == "jaipur:wikivoyage#intro#0000"
    assert record["embedding"] == [0.0, 0.25, 0.5]
    assert record["embedding_model"] == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_generate_embeddings_preserves_metadata_reference(tmp_path: Path):
    chunks_path = _write_chunks(tmp_path / "chunks" / "jaipur" / "wikivoyage.json")
    embeddings_dir = tmp_path / "embeddings"
    config = EmbeddingsConfig(provider="openai", model="text-embedding-3-small")

    transport = httpx.MockTransport(_mock_embeddings_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleEmbeddingsProvider(config=config, http_client=client)
        await generate_embeddings_for_chunks_file(
            chunks_path,
            provider=provider,
            config=config,
            embeddings_dir=embeddings_dir,
        )

    payload = load_embeddings_payload(embeddings_dir / "jaipur" / "wikivoyage.json")
    metadata = payload["embeddings"][1]["metadata"]
    expected = chunk_metadata_reference(SAMPLE_CHUNKS_PAYLOAD["chunks"][1])
    assert metadata == expected
    assert "text" not in metadata


@pytest.mark.asyncio
async def test_generate_embeddings_is_idempotent(tmp_path: Path):
    chunks_path = _write_chunks(tmp_path / "chunks" / "jaipur" / "wikivoyage.json")
    embeddings_dir = tmp_path / "embeddings"
    config = EmbeddingsConfig(provider="openai", model="text-embedding-3-small")

    calls = {"count": 0}

    def counting_handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return _mock_embeddings_handler(request)

    transport = httpx.MockTransport(counting_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleEmbeddingsProvider(config=config, http_client=client)

        first = await generate_embeddings_for_chunks_file(
            chunks_path,
            provider=provider,
            config=config,
            embeddings_dir=embeddings_dir,
        )
        second = await generate_embeddings_for_chunks_file(
            chunks_path,
            provider=provider,
            config=config,
            embeddings_dir=embeddings_dir,
        )

    assert first is not None
    assert second is None
    assert calls["count"] == 1

    path = embeddings_dir / "jaipur" / "wikivoyage.json"
    first_mtime = path.stat().st_mtime_ns
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleEmbeddingsProvider(config=config, http_client=client)
        await generate_embeddings_for_chunks_file(
            chunks_path,
            provider=provider,
            config=config,
            embeddings_dir=embeddings_dir,
        )
    assert path.stat().st_mtime_ns == first_mtime


@pytest.mark.asyncio
async def test_generate_embeddings_force_refresh_regenerates(tmp_path: Path):
    chunks_path = _write_chunks(tmp_path / "chunks" / "jaipur" / "wikivoyage.json")
    embeddings_dir = tmp_path / "embeddings"
    config = EmbeddingsConfig(provider="openai", model="text-embedding-3-small")

    calls = {"count": 0}

    def counting_handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return _mock_embeddings_handler(request)

    transport = httpx.MockTransport(counting_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleEmbeddingsProvider(config=config, http_client=client)
        await generate_embeddings_for_chunks_file(
            chunks_path,
            provider=provider,
            config=config,
            embeddings_dir=embeddings_dir,
        )
        await generate_embeddings_for_chunks_file(
            chunks_path,
            provider=provider,
            config=config,
            embeddings_dir=embeddings_dir,
            force_refresh=True,
        )

    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_openai_provider_uses_configured_endpoint(tmp_path: Path):
    seen: dict[str, str] = {}

    def capture_handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization", "")
        seen["model"] = json.loads(request.content.decode())["model"]
        return _mock_embeddings_handler(request)

    config = EmbeddingsConfig(
        provider="openai",
        model="text-embedding-3-small",
        api_key="secret-token",
        base_url="https://api.example.com/v1",
    )
    transport = httpx.MockTransport(capture_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAICompatibleEmbeddingsProvider(config=config, http_client=client)
        vectors = await provider.embed_texts(["hello"])

    assert seen["url"] == "https://api.example.com/v1/embeddings"
    assert seen["auth"] == "Bearer secret-token"
    assert seen["model"] == "text-embedding-3-small"
    assert vectors[0].dim == 3
