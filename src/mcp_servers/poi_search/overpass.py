"""Overpass client with simple file cache (Phase 1)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx


class OverpassError(RuntimeError):
    pass


class OverpassClient:
    def __init__(
        self,
        *,
        base_url: str,
        cache_dir: Path,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url
        self.cache_dir = cache_dir
        self._client = client

    def _cache_path(self, query: str) -> Path:
        digest = hashlib.md5(query.encode("utf-8")).hexdigest()  # noqa: S324 (non-crypto use)
        return self.cache_dir / f"overpass-{digest}.json"

    async def run_query(self, query: str, *, use_cache: bool = True) -> dict[str, Any]:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self._cache_path(query)

        if use_cache and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        async with httpx.AsyncClient(timeout=30.0) if self._client is None else _null_async_cm(
            self._client
        ) as client:
            c = client if self._client is None else self._client
            resp = await c.post(self.base_url, data={"data": query})

        if resp.status_code != 200:
            raise OverpassError(f"Overpass HTTP {resp.status_code}: {resp.text[:200]}")

        payload = resp.json()
        cache_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload


class _null_async_cm:
    """Async context manager that yields a pre-existing object."""

    def __init__(self, obj: Any) -> None:
        self._obj = obj

    async def __aenter__(self) -> Any:
        return self._obj

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

