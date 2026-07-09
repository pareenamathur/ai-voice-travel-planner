"""Planning Agent — itinerary creation; returns PlanArtifact to Review only (Phase 4+)."""

from typing import Any

from src.agents.base import BaseAgent
from src.shared.messages.types import AgentRole, PlanArtifact, TaskMessage


class PlanningAgent(BaseAgent):
    """Invokes search_pois + build_itinerary via MCP Gateway. Never user-facing."""

    role = AgentRole.PLANNING

    async def run(self, task: TaskMessage) -> PlanArtifact:
        self._trace("delegation_started", task.correlation_id, task_type=task.task_type.value)
        # Phase 4: implement MCP tool calls and artifact build
        return PlanArtifact(
            itinerary={},
            poi_registry={},
            rag_citations=[],
            correlation_id=task.correlation_id,
        )

    async def handle_regen(self, hints: dict[str, Any], correlation_id: str) -> PlanArtifact:
        self._trace("regen_requested", correlation_id, hints=hints)
        return PlanArtifact(itinerary={}, correlation_id=correlation_id)
