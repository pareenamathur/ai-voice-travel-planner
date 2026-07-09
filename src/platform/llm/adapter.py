"""Model-agnostic LLM adapter — all agents share one underlying model."""

from dataclasses import dataclass
from typing import Any

from src.shared.messages.types import AgentRole


@dataclass
class AgentLLMConfig:
    """Per-agent system prompt and allowed tool names (enforced by Gateway)."""

    system_prompt: str
    allowed_tools: list[str]


DEFAULT_AGENT_CONFIGS: dict[AgentRole, AgentLLMConfig] = {
    AgentRole.SUPERVISOR: AgentLLMConfig(
        system_prompt=(
            "You are the Supervisor Agent — the only user-facing travel assistant. "
            "Classify intent, ask clarifying questions (max 6), confirm constraints, "
            "and synthesize responses. Never call tools directly."
        ),
        allowed_tools=[],
    ),
    AgentRole.PLANNING: AgentLLMConfig(
        system_prompt=(
            "You are the Planning Agent. Build day-wise itineraries from constraints. "
            "Submit PlanArtifact to Review Agent only."
        ),
        allowed_tools=["search_pois", "build_itinerary"],
    ),
    AgentRole.KNOWLEDGE: AgentLLMConfig(
        system_prompt=(
            "You are the Knowledge Agent. Answer with cited facts only. "
            "Return results to Supervisor."
        ),
        allowed_tools=["search_pois", "retrieve_guidance", "get_weather"],
    ),
    AgentRole.EDIT: AgentLLMConfig(
        system_prompt=(
            "You are the Edit Agent. Apply scoped itinerary patches. "
            "Submit EditArtifact to Review Agent only."
        ),
        allowed_tools=["rebuild_day", "estimate_travel_time"],
    ),
    AgentRole.EXPORT: AgentLLMConfig(
        system_prompt="You are the Export Agent. Trigger PDF/email export via Gateway.",
        allowed_tools=["trigger_export"],
    ),
    AgentRole.REVIEW: AgentLLMConfig(
        system_prompt=(
            "You are the Review Agent. Run evaluations and return ReviewVerdict. "
            "Never communicate with the user."
        ),
        allowed_tools=[],
    ),
}


class LLMAdapter:
    """Model-agnostic adapter. Phase 0 stub — swap provider via config in later phases."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        provider: str = "openai",
        agent_configs: dict[AgentRole, AgentLLMConfig] | None = None,
    ) -> None:
        self.model = model
        self.provider = provider
        self.agent_configs = agent_configs or DEFAULT_AGENT_CONFIGS

    def get_config(self, role: AgentRole) -> AgentLLMConfig:
        return self.agent_configs[role]

    async def complete(
        self,
        agent_role: AgentRole,
        messages: list[dict[str, str]],
        tools_allowed: list[str] | None = None,
    ) -> dict[str, Any]:
        """Phase 0 stub: returns structured placeholder. Real provider wired in Phase 4."""
        config = self.get_config(agent_role)
        effective_tools = tools_allowed if tools_allowed is not None else config.allowed_tools
        return {
            "role": agent_role.value,
            "model": self.model,
            "provider": self.provider,
            "content": f"[stub response for {agent_role.value}]",
            "tools_allowed": effective_tools,
            "message_count": len(messages),
        }
