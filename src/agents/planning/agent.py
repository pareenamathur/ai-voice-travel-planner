"""Planning Agent — itinerary creation via MCP Gateway only (Phase 4 Task 3)."""

from __future__ import annotations

from typing import Any

from src.agents.base import BaseAgent
from src.shared.messages.types import (
    AgentRole,
    PlanArtifact,
    TaskMessage,
    TaskType,
    TripConstraints,
)


class PlanningAgent(BaseAgent):
    """Invokes ``search_pois`` + ``build_itinerary`` via MCP Gateway. Never user-facing."""

    role = AgentRole.PLANNING

    async def run(self, task: TaskMessage) -> PlanArtifact:
        """Accept a PLAN TaskMessage and return a PlanArtifact for Review."""
        constraints = self._validate_task(task)
        correlation_id = task.correlation_id

        if self.gateway is None:
            raise ValueError("Planning Agent requires an MCP Gateway")

        self._trace(
            "planning_started",
            correlation_id,
            session_id=task.session_id,
            city=constraints.city,
            days=constraints.days,
        )

        pois = await self._search_pois(constraints, correlation_id)
        itinerary_payload = await self._build_itinerary(constraints, pois, correlation_id)

        itinerary = itinerary_payload.get("itinerary") or {}
        poi_registry = self._build_poi_registry(pois, itinerary)
        artifact = PlanArtifact(
            itinerary=itinerary,
            poi_registry=poi_registry,
            rag_citations=[],
            correlation_id=correlation_id,
            constraints=constraints.model_dump(mode="json"),
            metadata={
                "session_id": task.session_id,
                "source": "planning_agent",
                "tools_used": ["search_pois", "build_itinerary"],
                "poi_count": len(pois),
                "search_source": "osm",
                "itinerary_source": itinerary_payload.get("source", "itinerary_builder"),
            },
        )

        self._trace(
            "plan_artifact_created",
            correlation_id,
            session_id=task.session_id,
            day_count=itinerary.get("total_days"),
            poi_registry_size=len(poi_registry),
        )
        return artifact

    async def handle_regen(self, hints: dict[str, Any], correlation_id: str) -> PlanArtifact:
        """Stub for future Review regen — not implemented in Task 3."""
        self._trace("regen_requested", correlation_id, hints=hints)
        return PlanArtifact(itinerary={}, correlation_id=correlation_id)

    def _validate_task(self, task: TaskMessage) -> TripConstraints:
        if not isinstance(task, TaskMessage):
            raise ValueError("task must be a TaskMessage")
        if task.task_type != TaskType.PLAN:
            raise ValueError(f"Planning Agent requires task_type=PLAN, got '{task.task_type}'")
        if not task.session_id or not str(task.session_id).strip():
            raise ValueError("session_id is required")
        if not task.correlation_id or not str(task.correlation_id).strip():
            raise ValueError("correlation_id is required")

        raw = task.payload.get("constraints")
        if raw is None:
            raise ValueError("PLAN payload.constraints is required")
        if not isinstance(raw, dict):
            raise ValueError("PLAN payload.constraints must be a dict")

        try:
            constraints = TripConstraints.model_validate(raw)
        except Exception as exc:
            raise ValueError(f"invalid PLAN constraints: {exc}") from exc

        city = (constraints.city or "").strip()
        if not city:
            raise ValueError("PLAN constraints.city is required")
        if constraints.days is None or constraints.days < 1:
            raise ValueError("PLAN constraints.days must be at least 1")

        # Normalize city whitespace for downstream tools.
        return constraints.model_copy(update={"city": city})

    async def _search_pois(
        self,
        constraints: TripConstraints,
        correlation_id: str,
    ) -> list[dict[str, Any]]:
        assert self.gateway is not None
        self._trace("search_pois", correlation_id, city=constraints.city)
        result = await self.gateway.invoke(
            AgentRole.PLANNING,
            "search_pois",
            {
                "city": constraints.city,
                "interests": list(constraints.interests or []),
            },
            correlation_id=correlation_id,
        )
        if not isinstance(result, dict):
            raise ValueError("search_pois must return a dict payload")
        pois = result.get("pois") or []
        if not isinstance(pois, list):
            raise ValueError("search_pois.pois must be a list")
        return pois

    async def _build_itinerary(
        self,
        constraints: TripConstraints,
        pois: list[dict[str, Any]],
        correlation_id: str,
    ) -> dict[str, Any]:
        assert self.gateway is not None
        traveler_constraints = {
            "interests": list(constraints.interests or []),
            "pace": constraints.pace,
            "party_size": constraints.party_size,
            "mobility_notes": constraints.mobility_notes,
            "metadata": {
                "budget": constraints.budget,
                "travel_dates": constraints.travel_dates,
                "food_preferences": list(constraints.food_preferences or []),
                "transport_preferences": list(constraints.transport_preferences or []),
            },
        }
        # Drop None values for cleaner tool input.
        traveler_constraints = {
            key: value for key, value in traveler_constraints.items() if value is not None
        }

        params: dict[str, Any] = {
            "city": constraints.city,
            "pois": pois,
            "total_days": constraints.days,
            "traveler_constraints": traveler_constraints,
        }
        if constraints.travel_dates and _looks_like_iso_date(constraints.travel_dates):
            params["start_date"] = constraints.travel_dates[:10]

        self._trace(
            "build_itinerary",
            correlation_id,
            city=constraints.city,
            total_days=constraints.days,
            poi_count=len(pois),
        )
        result = await self.gateway.invoke(
            AgentRole.PLANNING,
            "build_itinerary",
            params,
            correlation_id=correlation_id,
        )
        if not isinstance(result, dict):
            raise ValueError("build_itinerary must return a dict payload")
        return result

    def _build_poi_registry(
        self,
        pois: list[dict[str, Any]],
        itinerary: dict[str, Any],
    ) -> dict[str, Any]:
        registry: dict[str, Any] = {}
        for poi in pois:
            poi_id = poi.get("osm_id") or poi.get("poi_id")
            if poi_id:
                registry[str(poi_id)] = dict(poi)

        for ref in itinerary.get("poi_registry") or []:
            if not isinstance(ref, dict):
                continue
            poi_id = ref.get("poi_id")
            if poi_id and str(poi_id) not in registry:
                registry[str(poi_id)] = dict(ref)
        return registry


def _looks_like_iso_date(value: str) -> bool:
    return len(value) >= 10 and value[4] == "-" and value[7] == "-"
