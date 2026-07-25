"""End-to-end interest preservation for planning."""

from __future__ import annotations

import pytest

from src.agents.planning.agent import PlanningAgent
from src.agents.supervisor.slots import extract_slots, merge_constraints
from src.mcp_servers.itinerary_builder.scheduler import schedule_itinerary
from src.mcp_servers.poi_search.fallback import well_known_pois_for_city
from src.mcp_servers.poi_search.models import POI
from src.platform.llm.adapter import LLMAdapter
from src.platform.mcp_gateway.gateway import MCPGateway
from src.platform.observability.tracer import Observability
from src.shared.interests import missing_interests
from src.shared.itinerary import TravelerConstraints
from src.shared.messages.types import AgentRole, TaskMessage, TaskType, TripConstraints


class InterestAwareGateway(MCPGateway):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple] = []
        self.register("search_pois", self._search_pois)
        self.register("build_itinerary", self._build_itinerary)

    async def invoke(self, role, tool_name, params, correlation_id="", session_id=None):
        self.calls.append((role, tool_name, params))
        return await super().invoke(
            role, tool_name, params, correlation_id, session_id=session_id
        )

    async def _search_pois(self, **kwargs):
        interests = kwargs.get("interests") or []
        pois = well_known_pois_for_city(kwargs.get("city") or "Jaipur", interests=interests)
        return {"source": "well_known", "pois": pois, "live_poi_lookup": False}

    async def _build_itinerary(self, **kwargs):
        pois = [POI.model_validate(p) for p in kwargs.get("pois") or []]
        itinerary = schedule_itinerary(
            city=kwargs["city"],
            pois=pois,
            traveler_constraints=TravelerConstraints.model_validate(
                kwargs.get("traveler_constraints") or {}
            ),
            total_days=int(kwargs["total_days"]),
        )
        return {"source": "itinerary_builder", "itinerary": itinerary.model_dump(mode="json")}


@pytest.mark.asyncio
async def test_jaipur_food_and_adventure_message_preserves_both_interests():
    message = "Create a 3-day Jaipur itinerary including food and adventure."
    slots = extract_slots(message)
    constraints = merge_constraints(TripConstraints(), slots)

    assert constraints.city == "jaipur"
    assert constraints.days == 3
    assert "food" in constraints.interests
    assert "adventure" in constraints.interests

    gateway = InterestAwareGateway()
    agent = PlanningAgent(LLMAdapter(), gateway, Observability())
    task = TaskMessage(
        task_type=TaskType.PLAN,
        session_id="sess-food-adventure",
        correlation_id="corr-food-adventure",
        payload={"constraints": constraints.model_dump(mode="json")},
    )
    artifact = await agent.run(task)

    search_call = next(call for call in gateway.calls if call[1] == "search_pois")
    assert "food" in search_call[2]["interests"]
    assert "adventure" in search_call[2]["interests"]

    itinerary = artifact.itinerary
    registry = list(artifact.poi_registry.values())
    assert missing_interests(constraints.interests, registry) == []

    scheduled = []
    for day in itinerary.get("days") or []:
        for activity in day.get("activities") or []:
            poi_id = activity.get("poi_id")
            if poi_id and str(poi_id) in artifact.poi_registry:
                scheduled.append(artifact.poi_registry[str(poi_id)])
    assert missing_interests(constraints.interests, scheduled) == []
