"""Overpass client with mirrors, retries, and simple file cache (Phase 1)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx

# Identify this app to the public Overpass front-end (avoids Apache 406 on generic clients).
DEFAULT_USER_AGENT = (
    "AI-Voice-Travel-Planner/0.1 "
    "(+https://github.com/pareenamathur/ai-voice-travel-planner)"
)
DEFAULT_REFERER = "https://github.com/pareenamathur/ai-voice-travel-planner"

# Retry transient Overpass / gateway failures with exponential backoff per mirror.
RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})
MAX_ATTEMPTS_PER_MIRROR = 3
BACKOFF_BASE_SECONDS = 1.0

# Back-compat aliases for older imports/tests.
MAX_504_RETRIES = MAX_ATTEMPTS_PER_MIRROR - 1


class OverpassError(RuntimeError):
    pass


class OverpassClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        base_urls: list[str] | None = None,
        cache_dir: Path,
        client: httpx.AsyncClient | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        referer: str = DEFAULT_REFERER,
        backoff_base_seconds: float = BACKOFF_BASE_SECONDS,
        max_attempts_per_mirror: int = MAX_ATTEMPTS_PER_MIRROR,
        retryable_statuses: frozenset[int] | set[int] = RETRYABLE_STATUS_CODES,
    ) -> None:
        urls = [u.strip() for u in (base_urls or []) if u and u.strip()]
        if not urls and base_url:
            urls = [base_url.strip()]
        if not urls:
            raise ValueError("OverpassClient requires base_url or base_urls")

        self.base_urls = urls
        self.base_url = urls[0]
        self.cache_dir = cache_dir
        self._client = client
        self.user_agent = user_agent
        self.referer = referer
        self.backoff_base_seconds = backoff_base_seconds
        self.max_attempts_per_mirror = max(1, int(max_attempts_per_mirror))
        self.retryable_statuses = frozenset(retryable_statuses)

    def _request_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Referer": self.referer,
        }

    def _cache_path(self, query: str) -> Path:
        digest = hashlib.md5(query.encode("utf-8")).hexdigest()  # noqa: S324 (non-crypto use)
        return self.cache_dir / f"overpass-{digest}.json"

    async def run_query(self, query: str, *, use_cache: bool = True) -> dict[str, Any]:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self._cache_path(query)

        if use_cache and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        headers = self._request_headers()
        last_error: OverpassError | None = None

        async with httpx.AsyncClient(timeout=30.0) if self._client is None else _null_async_cm(
            self._client
        ) as client:
            c = client if self._client is None else self._client
            for mirror_url in self.base_urls:
                for attempt in range(self.max_attempts_per_mirror):
                    # Keep official form POST: application/x-www-form-urlencoded with data=<QL>.
                    resp = await c.post(mirror_url, data={"data": query}, headers=headers)
                    if resp.status_code == 200:
                        payload = resp.json()
                        cache_path.write_text(json.dumps(payload), encoding="utf-8")
                        return payload

                    detail = f"Overpass HTTP {resp.status_code}: {resp.text[:200]}"
                    last_error = OverpassError(detail)

                    if (
                        resp.status_code in self.retryable_statuses
                        and attempt < self.max_attempts_per_mirror - 1
                    ):
                        delay = self.backoff_base_seconds * (2**attempt)
                        await asyncio.sleep(delay)
                        continue
                    # Non-retryable, or retries exhausted for this mirror → try next mirror.
                    break

        assert last_error is not None
        raise last_error


class _null_async_cm:
    """Async context manager that yields a pre-existing object."""

    def __init__(self, obj: Any) -> None:
        self._obj = obj

    async def __aenter__(self) -> Any:
        return self._obj

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None
