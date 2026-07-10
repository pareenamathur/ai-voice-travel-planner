"""Embeddings configuration."""

from __future__ import annotations

from dataclasses import dataclass

from src.api.config import settings


@dataclass(frozen=True, slots=True)
class EmbeddingsConfig:
    """Embeddings provider configuration."""

    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""
    dim: int | None = None

    @classmethod
    def from_settings(cls) -> EmbeddingsConfig:
        """Build config from application settings (no hardcoded API keys)."""
        return cls(
            provider=settings.embedding_provider,
            model=settings.embedding_model,
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
        )
