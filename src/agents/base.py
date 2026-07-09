"""Base agent interface."""

from abc import ABC, abstractmethod
from typing import Any

from src.platform.llm.adapter import LLMAdapter
from src.platform.mcp_gateway.gateway import MCPGateway
from src.platform.observability.tracer import Observability
from src.shared.messages.types import AgentRole


class BaseAgent(ABC):
    """All agents share the same LLM adapter; differ by role, prompt, and tool permissions."""

    role: AgentRole

    def __init__(
        self,
        llm: LLMAdapter,
        gateway: MCPGateway | None = None,
        observability: Observability | None = None,
    ) -> None:
        self.llm = llm
        self.gateway = gateway
        self.observability = observability

    def _trace(self, event: str, correlation_id: str = "", **extra: Any) -> None:
        if self.observability:
            self.observability.record_span(
                agent=self.role.value,
                event=event,
                correlation_id=correlation_id,
                **extra,
            )

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute agent-specific logic."""
