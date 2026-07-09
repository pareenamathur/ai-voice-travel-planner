"""Export Agent — n8n PDF/email via Gateway (Phase 8+)."""

from src.agents.base import BaseAgent
from src.shared.messages.types import AgentResult, AgentRole, TaskMessage


class ExportAgent(BaseAgent):
    """Triggers export only for approved itineraries. Returns AgentResult to Supervisor."""

    role = AgentRole.EXPORT

    async def run(self, task: TaskMessage) -> AgentResult:
        self._trace("delegation_started", task.correlation_id, task_type=task.task_type.value)
        return AgentResult(
            status="stub",
            payload={"export": "not_implemented"},
            correlation_id=task.correlation_id,
        )
