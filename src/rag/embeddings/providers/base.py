"""Embeddings provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from src.rag.models import EmbeddingVector


class EmbeddingsProvider(ABC):
    """Converts text into embedding vectors."""

    @abstractmethod
    async def embed_texts(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        """Return one embedding per input text."""
