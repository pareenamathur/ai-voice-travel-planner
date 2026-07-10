"""OpenAI embeddings provider."""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from src.rag.embeddings._http import _null_async_cm
from src.rag.embeddings.config import EmbeddingsConfig
from src.rag.embeddings.providers.base import EmbeddingsProvider
from src.rag.models import EmbeddingVector

OPENAI_EMBEDDINGS_PATH = "/embeddings"


class OpenAIEmbeddingsProvider(EmbeddingsProvider):
    """OpenAI embeddings API (also supports OpenAI-compatible base URLs)."""

    def __init__(
        self,
        *,
        config: EmbeddingsConfig,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._http_client = http_client

    def _resolve_base_url(self) -> str:
        base = self._config.base_url.strip() or "https://api.openai.com/v1"
        return base.rstrip("/")

    async def embed_texts(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        if not texts:
            return []

        payload = {"model": self._config.model, "input": list(texts)}
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        url = f"{self._resolve_base_url()}{OPENAI_EMBEDDINGS_PATH}"

        async with (
            httpx.AsyncClient(timeout=60.0)
            if self._http_client is None
            else _null_async_cm(self._http_client)
        ) as client:
            response = await client.post(url, headers=headers, json=payload)

        response.raise_for_status()
        body = response.json()
        data = sorted(body["data"], key=lambda item: item["index"])
        return [
            EmbeddingVector(vector=item["embedding"], dim=len(item["embedding"]))
            for item in data
        ]
