"""Embeddings provider factory unit tests."""

from __future__ import annotations

import json

import httpx
import pytest
from src.rag.embeddings import (
    EmbeddingsConfig,
    EmbeddingsProviderFactory,
    GoogleEmbeddingsProvider,
    OpenAIEmbeddingsProvider,
)


def test_factory_selects_openai_provider():
    config = EmbeddingsConfig(provider="openai", model="text-embedding-3-small")
    provider = EmbeddingsProviderFactory.create(config)
    assert isinstance(provider, OpenAIEmbeddingsProvider)


def test_factory_selects_google_provider():
    config = EmbeddingsConfig(provider="google", model="text-embedding-004")
    provider = EmbeddingsProviderFactory.create(config)
    assert isinstance(provider, GoogleEmbeddingsProvider)


def test_factory_accepts_gemini_alias():
    config = EmbeddingsConfig(provider="gemini", model="text-embedding-004")
    provider = EmbeddingsProviderFactory.create(config)
    assert isinstance(provider, GoogleEmbeddingsProvider)


def test_factory_raises_for_unsupported_provider():
    config = EmbeddingsConfig(provider="unknown", model="model")
    with pytest.raises(ValueError, match="Unsupported embedding provider"):
        EmbeddingsProviderFactory.create(config)


def test_factory_grok_not_implemented_yet():
    config = EmbeddingsConfig(provider="grok", model="grok-embed")
    with pytest.raises(NotImplementedError, match="Grok embeddings provider"):
        EmbeddingsProviderFactory.create(config)


@pytest.mark.asyncio
async def test_google_provider_uses_configured_endpoint():
    seen: dict[str, str] = {}

    def capture_handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.url.params.get("key", "")
        body = json.loads(request.content.decode())
        seen["request_count"] = str(len(body["requests"]))
        return httpx.Response(
            200,
            json={"embeddings": [{"values": [0.1, 0.2, 0.3]}]},
        )

    config = EmbeddingsConfig(
        provider="google",
        model="text-embedding-004",
        api_key="google-secret",
    )
    transport = httpx.MockTransport(capture_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = EmbeddingsProviderFactory.create(config, http_client=client)
        vectors = await provider.embed_texts(["hello"])

    assert isinstance(provider, GoogleEmbeddingsProvider)
    assert seen["url"].startswith(
        "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents"
    )
    assert seen["key"] == "google-secret"
    assert seen["request_count"] == "1"
    assert vectors[0].dim == 3
