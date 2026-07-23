"""Tests for MCP Gateway permissions + observability spans."""

import pytest
from src.platform.mcp_gateway.gateway import MCPGateway, PermissionDeniedError
from src.platform.observability.tracer import Observability
from src.shared.messages.types import AgentRole


async def _echo_handler(**kwargs):
    return {"ok": True, **kwargs}


@pytest.mark.asyncio
async def test_gateway_permission_allowed():
    gw = MCPGateway()
    gw.register("search_pois", _echo_handler)
    result = await gw.invoke(AgentRole.PLANNING, "search_pois", {"city": "Jaipur"})
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_gateway_permission_denied():
    gw = MCPGateway()
    gw.register("search_pois", _echo_handler)
    with pytest.raises(PermissionDeniedError):
        await gw.invoke(AgentRole.SUPERVISOR, "search_pois", {"city": "Jaipur"})


@pytest.mark.asyncio
async def test_gateway_emits_observability_spans():
    obs = Observability()
    gw = MCPGateway(observability=obs)
    gw.register("search_pois", _echo_handler)

    corr_id = "c-123"
    await gw.invoke(AgentRole.PLANNING, "search_pois", {"city": "Jaipur"}, correlation_id=corr_id)

    spans = obs.get_spans(corr_id)
    events = [s.get("event") for s in spans]
    assert "tool_call_start" in events
    assert "tool_call_complete" in events
    complete = next(s for s in spans if s.get("event") == "tool_call_complete")
    assert "duration_ms" in complete
    assert complete["duration_ms"] >= 0


def test_gateway_is_permitted():
    gw = MCPGateway()
    assert gw.is_permitted(AgentRole.PLANNING, "build_itinerary") is True
    assert gw.is_permitted(AgentRole.EDIT, "build_itinerary") is False
