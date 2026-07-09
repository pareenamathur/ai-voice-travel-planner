"""Supervisor Agent — sole user-facing component."""

from typing import Any
from uuid import uuid4

from src.agents.base import BaseAgent
from src.platform.session.manager import SessionManager
from src.shared.messages.types import AgentRole


class SupervisorAgent(BaseAgent):
    """
    Owns user conversation, intent routing, and response synthesis.
    Reads/writes session state only via SessionManager.
    Never calls MCP tools or runs evaluations.
    """

    role = AgentRole.SUPERVISOR

    def __init__(self, llm, gateway, observability, session_manager: SessionManager) -> None:
        super().__init__(llm, gateway, observability)
        self.sessions = session_manager

    async def handle_message(
        self,
        session_id: str | None,
        message: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        if correlation_id:
            corr_id = correlation_id
        elif self.observability:
            corr_id = self.observability.new_correlation_id()
        else:
            corr_id = str(uuid4())
        session = self.sessions.get_or_create(session_id)

        self._trace("user_message_received", corr_id, session_id=session.session_id)
        self._trace("decision", corr_id, decision="route_to_intake", message_preview=message[:80])

        supervisor_config = self.llm.get_config(AgentRole.SUPERVISOR)
        await self.llm.complete(
            AgentRole.SUPERVISOR,
            [
                {"role": "system", "content": supervisor_config.system_prompt},
                {"role": "user", "content": message},
            ],
        )

        # Phase 0: echo with session metadata. Full routing in Phase 4+.
        response_text = (
            f"Supervisor received your message. Session phase: {session.conversation_phase.value}. "
            "Planning and editing workflows will route through Review Agent in later phases."
        )

        self._trace("user_response_sent", corr_id, session_id=session.session_id)

        return {
            "session_id": session.session_id,
            "correlation_id": corr_id,
            "response": response_text,
            "conversation_phase": session.conversation_phase.value,
            "itinerary_approved": session.itinerary_approved,
        }

    async def run(
        self,
        session_id: str | None = None,
        message: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        return await self.handle_message(session_id, message, kwargs.get("correlation_id"))
