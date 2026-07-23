"""Timing helpers for observability spans."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from src.platform.observability.tracer import Observability


@asynccontextmanager
async def timed_step(
    observability: Observability | None,
    *,
    agent: str,
    event: str,
    correlation_id: str = "",
    **extra: Any,
) -> AsyncIterator[None]:
    """Record ``duration_ms`` on a span when the block completes."""
    start = time.perf_counter()
    error: str | None = None
    try:
        yield
    except Exception as exc:
        error = str(exc)[:300]
        raise
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        if observability is not None:
            payload: dict[str, Any] = {
                "agent": agent,
                "event": event,
                "correlation_id": correlation_id,
                "duration_ms": duration_ms,
                **extra,
            }
            if error:
                payload["error"] = error
            observability.record_span(**payload)
