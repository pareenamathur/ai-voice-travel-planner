"""Knowledge Agent — grounded explanations; returns AgentResult to Supervisor (Phase 6+)."""

from src.agents.base import BaseAgent
from src.shared.messages.types import AgentResult, AgentRole, TaskMessage


class KnowledgeAgent(BaseAgent):
    """RAG + citations via Gateway. Review Agent bypassed for EXPLAIN workflows."""

    role = AgentRole.KNOWLEDGE

    async def run(self, task: TaskMessage) -> AgentResult:
        self._trace("delegation_started", task.correlation_id, task_type=task.task_type.value)
        return AgentResult(
            status="stub",
            payload={"answer": ""},
            citations=[],
            correlation_id=task.correlation_id,
        )
