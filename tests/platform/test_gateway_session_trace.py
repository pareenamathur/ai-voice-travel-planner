"""Gateway session_id propagation for GET /api/session/{session_id}/trace."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from src.api.deps import get_registry, reset_registry
from src.api.main import app
from src.platform.mcp_gateway.gateway import MCPGateway
from src.platform.observability.tracer import Observability
from src.shared.messages.types import AgentRole

CITY_PALACE = {
    "osm_id": "node/1",
    "name": "City Palace",
    "lat": 26.9855,
    "lon": 75.8513,
    "category": "culture",
}
HAWA_MAHAL = {
    "osm_id": "node/2",
    "name": "Hawa Mahal",
    "lat": 26.9239,
    "lon": 75.8267,
    "category": "culture",
}


async def _echo_handler(**kwargs):
    return {"ok": True, "received_keys": sorted(kwargs.keys())}


async def _failing_handler(**kwargs):
    _ = kwargs
    raise RuntimeError("tool failed")


@pytest.fixture(autouse=True)
def _reset_registry():
    reset_registry()
    yield
    reset_registry()


def _gateway_spans(spans: list[dict]) -> list[dict]:
    return [span for span in spans if span.get("agent") == "mcp_gateway"]


@pytest.mark.asyncio
async def test_gateway_start_and_complete_spans_include_session_id_kwarg():
    obs = Observability()
    gw = MCPGateway(observability=obs)
    gw.register("search_pois", _echo_handler)

    await gw.invoke(
        AgentRole.PLANNING,
        "search_pois",
        {"city": "Jaipur"},
        correlation_id="corr-session-kwarg",
        session_id="sess-kwarg",
    )

    gateway_spans = _gateway_spans(obs.get_spans())
    assert len(gateway_spans) == 2
    events = {span["event"] for span in gateway_spans}
    assert events == {"tool_call_start", "tool_call_complete"}
    for span in gateway_spans:
        assert span["session_id"] == "sess-kwarg"
        assert span["correlation_id"] == "corr-session-kwarg"
        assert span["tool"] == "search_pois"
        assert "city" not in span
        assert "received_keys" not in span


@pytest.mark.asyncio
async def test_gateway_spans_session_id_from_tool_params():
    obs = Observability()
    gw = MCPGateway(observability=obs)
    gw.register("search_pois", _echo_handler)

    await gw.invoke(
        AgentRole.PLANNING,
        "search_pois",
        {"city": "Jaipur", "session_id": "sess-from-params"},
        correlation_id="corr-session-params",
    )

    gateway_spans = _gateway_spans(obs.get_spans())
    assert len(gateway_spans) == 2
    assert all(span["session_id"] == "sess-from-params" for span in gateway_spans)


@pytest.mark.asyncio
async def test_gateway_error_span_preserves_session_id():
    obs = Observability()
    gw = MCPGateway(observability=obs)
    gw.register("search_pois", _failing_handler)

    with pytest.raises(RuntimeError, match="tool failed"):
        await gw.invoke(
            AgentRole.PLANNING,
            "search_pois",
            {"city": "Jaipur"},
            correlation_id="corr-session-error",
            session_id="sess-error",
        )

    gateway_spans = _gateway_spans(obs.get_spans())
    assert len(gateway_spans) == 2
    events = [span["event"] for span in gateway_spans]
    assert "tool_call_start" in events
    assert "tool_call_error" in events
    for span in gateway_spans:
        assert span["session_id"] == "sess-error"
        assert span["correlation_id"] == "corr-session-error"


@pytest.mark.asyncio
async def test_session_trace_api_returns_search_pois_and_build_itinerary():
    registry = get_registry()
    session_id = "sess-trace-plan"
    correlation_id = "corr-trace-plan"

    await registry.gateway.invoke(
        AgentRole.PLANNING,
        "search_pois",
        {
            "city": "Jaipur",
            "interests": ["culture"],
            "session_id": session_id,
        },
        correlation_id=correlation_id,
        session_id=session_id,
    )
    await registry.gateway.invoke(
        AgentRole.PLANNING,
        "build_itinerary",
        {
            "city": "Jaipur",
            "pois": [CITY_PALACE, HAWA_MAHAL],
            "total_days": 1,
            "traveler_constraints": {"pace": "moderate"},
        },
        correlation_id=correlation_id,
        session_id=session_id,
    )

    client = TestClient(app)
    response = client.get(f"/api/session/{session_id}/trace")
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id

    gateway_spans = _gateway_spans(payload["spans"])
    tools = {span.get("tool") for span in gateway_spans}
    assert "search_pois" in tools
    assert "build_itinerary" in tools
    assert all(span.get("session_id") == session_id for span in gateway_spans)


@pytest.mark.asyncio
async def test_session_trace_api_includes_rebuild_day():
    registry = get_registry()
    session_id = "sess-trace-edit"
    correlation_id = "corr-trace-edit"

    built = await registry.gateway.invoke(
        AgentRole.PLANNING,
        "build_itinerary",
        {
            "city": "Jaipur",
            "pois": [CITY_PALACE, HAWA_MAHAL],
            "total_days": 1,
        },
        correlation_id=correlation_id,
        session_id=session_id,
    )
    await registry.gateway.invoke(
        AgentRole.EDIT,
        "rebuild_day",
        {
            "itinerary": built["itinerary"],
            "day_number": 1,
            "traveler_constraints": {"pace": "relaxed"},
        },
        correlation_id=correlation_id,
        session_id=session_id,
    )

    client = TestClient(app)
    response = client.get(f"/api/session/{session_id}/trace")
    assert response.status_code == 200
    gateway_spans = _gateway_spans(response.json()["spans"])
    tools = {span.get("tool") for span in gateway_spans}
    assert "rebuild_day" in tools


@pytest.mark.asyncio
async def test_session_trace_api_isolates_sessions():
    registry = get_registry()

    await registry.gateway.invoke(
        AgentRole.PLANNING,
        "search_pois",
        {"city": "Jaipur", "session_id": "sess-one"},
        correlation_id="corr-one",
        session_id="sess-one",
    )
    await registry.gateway.invoke(
        AgentRole.PLANNING,
        "search_pois",
        {"city": "Jaipur", "session_id": "sess-two"},
        correlation_id="corr-two",
        session_id="sess-two",
    )

    client = TestClient(app)
    one = client.get("/api/session/sess-one/trace").json()["spans"]
    two = client.get("/api/session/sess-two/trace").json()["spans"]

    one_gateway = _gateway_spans(one)
    two_gateway = _gateway_spans(two)
    assert one_gateway
    assert two_gateway
    assert all(span.get("session_id") == "sess-one" for span in one_gateway)
    assert all(span.get("session_id") == "sess-two" for span in two_gateway)
    assert not any(span.get("session_id") == "sess-two" for span in one_gateway)
    assert not any(span.get("session_id") == "sess-one" for span in two_gateway)
