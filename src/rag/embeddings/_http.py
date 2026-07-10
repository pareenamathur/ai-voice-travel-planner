"""Shared HTTP helpers for embeddings providers."""

from __future__ import annotations

from typing import Any


class _null_async_cm:
    def __init__(self, obj: Any) -> None:
        self._obj = obj

    async def __aenter__(self) -> Any:
        return self._obj

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None
