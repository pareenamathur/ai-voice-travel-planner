"""Agent registry — internal dispatcher; not exposed as HTTP endpoints."""

from src.agents.base import BaseAgent
from src.agents.edit.agent import EditAgent
from src.agents.export.agent import ExportAgent
from src.agents.knowledge.agent import KnowledgeAgent
from src.agents.planning.agent import PlanningAgent
from src.agents.review.agent import ReviewAgent
from src.agents.supervisor.agent import SupervisorAgent
from src.platform.llm.adapter import LLMAdapter
from src.platform.mcp_gateway.gateway import MCPGateway
from src.platform.observability.tracer import Observability
from src.platform.session.manager import SessionManager
from src.shared.messages.types import AgentRole


class AgentRegistry:
    """Wires platform services to agent instances."""

    def __init__(
        self,
        session_manager: SessionManager,
        llm: LLMAdapter,
        gateway: MCPGateway,
        observability: Observability,
    ) -> None:
        self.session_manager = session_manager
        self.llm = llm
        self.gateway = gateway
        self.observability = observability

        self.planning = PlanningAgent(llm, gateway, observability)
        self.knowledge = KnowledgeAgent(llm, gateway, observability)
        self.edit = EditAgent(llm, gateway, observability)
        self.export = ExportAgent(llm, gateway, observability)
        self.review = ReviewAgent(llm, gateway, observability)
        self.supervisor = SupervisorAgent(
            llm,
            gateway,
            observability,
            session_manager,
            planning=self.planning,
            review=self.review,
            edit=self.edit,
            knowledge=self.knowledge,
        )

        self._specialists: dict[AgentRole, BaseAgent] = {
            AgentRole.PLANNING: self.planning,
            AgentRole.KNOWLEDGE: self.knowledge,
            AgentRole.EDIT: self.edit,
            AgentRole.EXPORT: self.export,
            AgentRole.REVIEW: self.review,
        }

    def get_specialist(self, role: AgentRole) -> BaseAgent:
        if role not in self._specialists:
            raise KeyError(f"No specialist registered for role: {role}")
        return self._specialists[role]

    def specialist_roles(self) -> list[AgentRole]:
        return list(self._specialists.keys())
