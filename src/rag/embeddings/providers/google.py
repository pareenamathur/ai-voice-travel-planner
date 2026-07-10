"""Google Generative AI embeddings provider."""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from src.rag.embeddings._http import _null_async_cm
from src.rag.embeddings.config import EmbeddingsConfig
from src.rag.embeddings.providers.base import EmbeddingsProvider
from src.rag.models import EmbeddingVector

GOOGLE_EMBEDDINGS_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"
GOOGLE_BATCH_EMBED_MAX = 100


class GoogleEmbeddingsProvider(EmbeddingsProvider):
    """Google Generative AI batch embeddings API."""

    def __init__(
        self,
        *,
        config: EmbeddingsConfig,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._http_client = http_client

    def _resolve_base_url(self) -> str:
        base = self._config.base_url.strip() or GOOGLE_EMBEDDINGS_DEFAULT_BASE_URL
        return base.rstrip("/")

    def _resolve_model_path(self) -> str:
        model = self._config.model.strip()
        if model.startswith("models/"):
            return model
        return f"models/{model}"

    async def _embed_batch(
        self,
        texts: list[str],
        *,
        client: httpx.AsyncClient,
    ) -> list[EmbeddingVector]:
        model_path = self._resolve_model_path()
        url = f"{self._resolve_base_url()}/v1beta/{model_path}:batchEmbedContents"
        params = {"key": self._config.api_key} if self._config.api_key else None
        payload = {
            "requests": [
                {
                    "model": model_path,
                    "content": {"parts": [{"text": text}]},
                }
                for text in texts
            ]
        }
        response = await client.post(url, params=params, json=payload)
        response.raise_for_status()
        body = response.json()
        embeddings = body.get("embeddings", [])
        return [
            EmbeddingVector(vector=item["values"], dim=len(item["values"]))
            for item in embeddings
        ]

    async def embed_texts(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        if not texts:
            return []

        text_list = list(texts)
        vectors: list[EmbeddingVector] = []
        async with (
            httpx.AsyncClient(timeout=120.0)
            if self._http_client is None
            else _null_async_cm(self._http_client)
        ) as client:
            for start in range(0, len(text_list), GOOGLE_BATCH_EMBED_MAX):
                batch = text_list[start : start + GOOGLE_BATCH_EMBED_MAX]
                vectors.extend(await self._embed_batch(batch, client=client))

        return vectors
