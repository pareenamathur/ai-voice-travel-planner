"""Tests for LLM adapter stub."""

import pytest
from src.platform.llm.adapter import LLMAdapter
from src.shared.messages.types import AgentRole


@pytest.mark.asyncio
async def test_llm_adapter_complete_callable():
    adapter = LLMAdapter(model="gpt-4o-mini", provider="openai")
    result = await adapter.complete(
        AgentRole.SUPERVISOR,
        [{"role": "user", "content": "hello"}],
    )
    assert result["role"] == "supervisor"
    assert result["model"] == "gpt-4o-mini"
    assert "content" in result


def test_llm_adapter_per_agent_config():
    adapter = LLMAdapter()
    planning = adapter.get_config(AgentRole.PLANNING)
    assert "search_pois" in planning.allowed_tools
    supervisor = adapter.get_config(AgentRole.SUPERVISOR)
    assert supervisor.allowed_tools == []
