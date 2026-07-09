"""Edit Agent — scoped patches; returns EditArtifact to Review only (Phase 6+)."""

from typing import Any

from src.agents.base import BaseAgent
from src.shared.messages.types import AgentRole, EditArtifact, EditScope, TaskMessage


class EditAgent(BaseAgent):
    """Invokes rebuild_day via Gateway. Never user-facing."""

    role = AgentRole.EDIT

    async def run(self, task: TaskMessage) -> EditArtifact:
        self._trace("delegation_started", task.correlation_id, task_type=task.task_type.value)
        return EditArtifact(
            itinerary={},
            edit_scope=EditScope(intent=str(task.payload.get("edit_intent", ""))),
            before_snapshot=task.payload.get("before_snapshot", {}),
            correlation_id=task.correlation_id,
        )

    async def handle_regen(self, hints: dict[str, Any], correlation_id: str) -> EditArtifact:
        self._trace("regen_requested", correlation_id, hints=hints)
        return EditArtifact(
            itinerary={},
            edit_scope=EditScope(intent="regen"),
            before_snapshot={},
            correlation_id=correlation_id,
        )
