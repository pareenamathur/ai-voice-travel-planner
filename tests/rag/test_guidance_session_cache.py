"""Session-scoped RAG cache for retrieve_guidance."""

import pytest

from src.rag import guidance as guidance_module
from src.rag.guidance import retrieve_guidance


@pytest.mark.asyncio
async def test_retrieve_guidance_session_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    guidance_module._SESSION_RAG_CACHE.clear()
    calls = {"count": 0}

    async def fake_retrieve(query: str, city: str, top_k: int = 5):
        calls["count"] += 1
        return []

    monkeypatch.setattr(guidance_module, "retrieve", fake_retrieve)

    first = await retrieve_guidance(
        query="best food",
        city="Jaipur",
        top_k=3,
        session_id="sess-1",
    )
    second = await retrieve_guidance(
        query="best food",
        city="Jaipur",
        top_k=3,
        session_id="sess-1",
    )

    assert first == second
    assert calls["count"] == 1
