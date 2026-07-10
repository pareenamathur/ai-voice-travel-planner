"""Factory for embeddings providers."""

from __future__ import annotations

import httpx

from src.rag.embeddings.config import EmbeddingsConfig
from src.rag.embeddings.providers.base import EmbeddingsProvider
from src.rag.embeddings.providers.google import GoogleEmbeddingsProvider
from src.rag.embeddings.providers.openai import OpenAIEmbeddingsProvider

_OPENAI_ALIASES = frozenset({"openai"})
_GOOGLE_ALIASES = frozenset({"google", "gemini"})
_GROK_ALIASES = frozenset({"grok", "xai"})


class EmbeddingsProviderFactory:
    """Selects an embeddings provider based on configuration."""

    @staticmethod
    def create(
        config: EmbeddingsConfig | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> EmbeddingsProvider:
        """Return the configured embeddings provider implementation."""
        resolved = config or EmbeddingsConfig.from_settings()
        provider = resolved.provider.strip().lower()

        if provider in _OPENAI_ALIASES:
            return OpenAIEmbeddingsProvider(config=resolved, http_client=http_client)
        if provider in _GOOGLE_ALIASES:
            return GoogleEmbeddingsProvider(config=resolved, http_client=http_client)
        if provider in _GROK_ALIASES:
            raise NotImplementedError(
                "Grok embeddings provider is not implemented yet. "
                "Register it in EmbeddingsProviderFactory when available."
            )

        raise ValueError(f"Unsupported embedding provider: {resolved.provider}")
