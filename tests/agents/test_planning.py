"""Phase 4 Task 3 — Planning Agent unit tests."""

from __future__ import annotations

from typing import Any

import pytest
from src.agents.planning.agent import PlanningAgent
from src.platform.llm.adapter import LLMAdapter
from src.platform.mcp_gateway.gateway import MCPGateway, PermissionDeniedError
from src.platform.observability.tracer import Observability
from src.shared.itinerary import Itinerary
from src.shared.messages.types import AgentRole, PlanArtifact, TaskMessage, TaskType

SAMPLE_POIS = [
    {
        "osm_id": "node/1",
        "name": "City Palace",
        "lat": 26.9855,
        "lon": 75.8513,
        "category": "culture",
        "source": "osm",
    },
    {
        "osm_id": "node/2",
        "name": "Hawa Mahal",
        "lat": 26.9239,
        "lon": 75.8267,
        "category": "culture",
        "source": "osm",
    },
]

SAMPLE_ITINERARY = {
    "city": "Jaipur",
    "total_days": 2,
    "traveler_constraints": {"pace": "relaxed", "interests": ["food", "culture"]},
    "days": [
        {
            "day_number": 1,
            "activities": [
                {
                    "id": "d1-a1",
                    "title": "City Palace",
                    "poi_id": "node/1",
                    "start_time": "09:00",
                    "end_time": "10:30",
                    "duration_minutes": 90,
                }
            ],
            "travel_segments": [],
        },
        {"day_number": 2, "activities": [], "travel_segments": []},
    ],
    "poi_registry": [
        {
            "poi_id": "node/1",
            "name": "City Palace",
            "latitude": 26.9855,
            "longitude": 75.8513,
            "category": "culture",
            "source": "osm",
        }
    ],
    "citations": [],
    "metadata": {"scheduler": "heuristic_v1"},
}


class RecordingGateway(MCPGateway):
    """Gateway that records invocations and returns canned tool results."""

    def __init__(self, observability: Observability | None = None) -> None:
        super().__init__(observability=observability)
        self.calls: list[tuple[AgentRole, str, dict[str, Any]]] = []
        self.register("search_pois", self._search_pois)
        self.register("build_itinerary", self._build_itinerary)
        self.register("rebuild_day", self._rebuild_day)

    async def invoke(
        self,
        role: AgentRole,
        tool_name: str,
        params: dict[str, Any],
        correlation_id: str = "",
    ) -> Any:
        self.calls.append((role, tool_name, params))
        return await super().invoke(role, tool_name, params, correlation_id)

    async def _search_pois(self, **kwargs: Any) -> dict[str, Any]:
        return {"source": "osm", "pois": list(SAMPLE_POIS)}

    async def _build_itinerary(self, **kwargs: Any) -> dict[str, Any]:
        return {"source": "itinerary_builder", "itinerary": dict(SAMPLE_ITINERARY)}

    async def _rebuild_day(self, **kwargs: Any) -> dict[str, Any]:
        return {"source": "itinerary_builder", "itinerary": dict(SAMPLE_ITINERARY)}


def _plan_task(**payload_overrides: Any) -> TaskMessage:
    constraints = {
        "city": "Jaipur",
        "days": 2,
        "interests": ["food", "culture"],
        "pace": "relaxed",
    }
    constraints.update(payload_overrides.pop("constraints", {}))
    payload = {"constraints": constraints}
    payload.update(payload_overrides)
    return TaskMessage(
        task_type=TaskType.PLAN,
        session_id="sess-plan-1",
        payload=payload,
        correlation_id="corr-plan-1",
    )


@pytest.fixture
def obs() -> Observability:
    return Observability()


@pytest.fixture
def gateway(obs: Observability) -> RecordingGateway:
    return RecordingGateway(observability=obs)


@pytest.fixture
def planning(gateway: RecordingGateway, obs: Observability) -> PlanningAgent:
    return PlanningAgent(llm=LLMAdapter(), gateway=gateway, observability=obs)


@pytest.mark.asyncio
async def test_valid_plan_flow_returns_plan_artifact(
    planning: PlanningAgent,
    gateway: RecordingGateway,
):
    artifact = await planning.run(_plan_task())

    assert isinstance(artifact, PlanArtifact)
    assert artifact.correlation_id == "corr-plan-1"
    assert artifact.constraints["city"] == "Jaipur"
    assert artifact.constraints["days"] == 2
    assert "node/1" in artifact.poi_registry
    assert artifact.metadata["tools_used"] == ["search_pois", "build_itinerary"]
    assert artifact.rag_citations == []

    # Canonical itinerary validates against shared schema.
    itinerary = Itinerary.model_validate(artifact.itinerary)
    assert itinerary.city == "Jaipur"
    assert itinerary.total_days == 2


@pytest.mark.asyncio
async def test_search_pois_and_build_itinerary_invoked_once_each(
    planning: PlanningAgent,
    gateway: RecordingGateway,
):
    await planning.run(_plan_task())

    tool_names = [name for _, name, _ in gateway.calls]
    assert tool_names == ["search_pois", "build_itinerary"]
    assert all(role == AgentRole.PLANNING for role, _, _ in gateway.calls)

    search_params = gateway.calls[0][2]
    assert search_params["city"] == "Jaipur"
    assert search_params["interests"] == ["food", "culture"]

    build_params = gateway.calls[1][2]
    assert build_params["city"] == "Jaipur"
    assert build_params["total_days"] == 2
    assert build_params["pois"] == SAMPLE_POIS
    assert build_params["traveler_constraints"]["pace"] == "relaxed"


@pytest.mark.asyncio
async def test_planning_uses_gateway_only(planning: PlanningAgent, gateway: RecordingGateway):
    await planning.run(_plan_task())
    # All tool traffic went through gateway.invoke (recorded).
    assert len(gateway.calls) == 2
    assert planning.gateway is gateway


@pytest.mark.asyncio
async def test_invalid_task_message_missing_constraints(planning: PlanningAgent):
    task = TaskMessage(
        task_type=TaskType.PLAN,
        session_id="sess-1",
        payload={},
        correlation_id="corr-1",
    )
    with pytest.raises(ValueError, match="constraints is required"):
        await planning.run(task)


@pytest.mark.asyncio
async def test_invalid_task_message_wrong_type(planning: PlanningAgent):
    task = TaskMessage(
        task_type=TaskType.EDIT,
        session_id="sess-1",
        payload={"constraints": {"city": "Jaipur", "days": 2}},
        correlation_id="corr-1",
    )
    with pytest.raises(ValueError, match="task_type=PLAN"):
        await planning.run(task)


@pytest.mark.asyncio
async def test_invalid_task_message_missing_city(planning: PlanningAgent):
    with pytest.raises(ValueError, match="city is required"):
        await planning.run(_plan_task(constraints={"city": "", "days": 2}))


@pytest.mark.asyncio
async def test_invalid_task_message_invalid_days(planning: PlanningAgent):
    with pytest.raises(ValueError, match="days must be at least 1"):
        await planning.run(_plan_task(constraints={"city": "Jaipur", "days": 0}))


@pytest.mark.asyncio
async def test_gateway_permission_enforcement_denies_disallowed_tool(
    planning: PlanningAgent,
    gateway: RecordingGateway,
):
    # Planning must not be able to call rebuild_day even if registered.
    with pytest.raises(PermissionDeniedError):
        await gateway.invoke(
            AgentRole.PLANNING,
            "rebuild_day",
            {"itinerary": SAMPLE_ITINERARY, "day_number": 1},
            correlation_id="corr-deny",
        )


@pytest.mark.asyncio
async def test_missing_gateway_raises():
    agent = PlanningAgent(llm=LLMAdapter(), gateway=None, observability=Observability())
    with pytest.raises(ValueError, match="requires an MCP Gateway"):
        await agent.run(_plan_task())


@pytest.mark.asyncio
async def test_plan_artifact_schema_validation(planning: PlanningAgent):
    artifact = await planning.run(_plan_task())
    dumped = artifact.model_dump(mode="json")
    reloaded = PlanArtifact.model_validate(dumped)
    assert reloaded.itinerary["city"] == "Jaipur"
    assert reloaded.correlation_id == "corr-plan-1"
    assert reloaded.constraints["pace"] == "relaxed"


@pytest.mark.asyncio
async def test_observability_spans(planning: PlanningAgent, obs: Observability):
    await planning.run(_plan_task())
    spans = obs.get_spans("corr-plan-1")
    events = [span["event"] for span in spans]

    assert "planning_started" in events
    assert "search_pois" in events
    assert "build_itinerary" in events
    assert "plan_artifact_created" in events
    assert all(span.get("correlation_id") == "corr-plan-1" for span in spans)
    # Gateway also emits tool_call spans for the same correlation id.
    assert "tool_call_start" in events
    assert "tool_call_complete" in events
