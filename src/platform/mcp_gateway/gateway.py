"""MCP Gateway — Tool Registry with per-agent permissions."""

from collections.abc import Awaitable, Callable
from typing import Any

from src.platform.observability.tracer import Observability
from src.shared.messages.types import AgentRole

ToolHandler = Callable[..., Awaitable[Any]]


class PermissionDeniedError(Exception):
    """Raised when an agent invokes a tool it is not permitted to use."""

    def __init__(self, role: AgentRole, tool_name: str) -> None:
        super().__init__(f"Agent '{role}' is not permitted to invoke '{tool_name}'")
        self.role = role
        self.tool_name = tool_name


class ToolNotFoundError(Exception):
    def __init__(self, tool_name: str) -> None:
        super().__init__(f"Tool '{tool_name}' is not registered")
        self.tool_name = tool_name


# Phase 0: permission matrix from architecture.md
DEFAULT_PERMISSIONS: dict[str, set[AgentRole]] = {
    "search_pois": {AgentRole.PLANNING, AgentRole.KNOWLEDGE},
    "build_itinerary": {AgentRole.PLANNING},
    "rebuild_day": {AgentRole.EDIT},
    "estimate_travel_time": {AgentRole.EDIT},
    "retrieve_guidance": {AgentRole.KNOWLEDGE},
    "get_weather": {AgentRole.KNOWLEDGE},
    "trigger_export": {AgentRole.EXPORT},
}


class MCPGateway:
    """Routes tool invocations to registered handlers; enforces role permissions."""

    def __init__(
        self,
        observability: Observability | None = None,
        permissions: dict[str, set[AgentRole]] | None = None,
    ) -> None:
        self._handlers: dict[str, ToolHandler] = {}
        self._permissions = permissions or DEFAULT_PERMISSIONS
        self._observability = observability

    def register(self, tool_name: str, handler: ToolHandler) -> None:
        self._handlers[tool_name] = handler

    def is_permitted(self, role: AgentRole, tool_name: str) -> bool:
        allowed = self._permissions.get(tool_name)
        if allowed is None:
            return False
        return role in allowed

    async def invoke(
        self,
        role: AgentRole,
        tool_name: str,
        params: dict[str, Any],
        correlation_id: str = "",
    ) -> Any:
        if tool_name not in self._handlers:
            raise ToolNotFoundError(tool_name)
        if not self.is_permitted(role, tool_name):
            raise PermissionDeniedError(role, tool_name)

        start_event = {
            "agent": "mcp_gateway",
            "event": "tool_call_start",
            "tool": tool_name,
            "role": role.value,
            "correlation_id": correlation_id,
        }
        if self._observability:
            self._observability.record_span(**start_event)

        try:
            result = await self._handlers[tool_name](**params)
        except Exception as exc:
            if self._observability:
                self._observability.record_span(
                    agent="mcp_gateway",
                    event="tool_call_error",
                    tool=tool_name,
                    role=role.value,
                    correlation_id=correlation_id,
                    error=str(exc),
                )
            raise

        if self._observability:
            self._observability.record_span(
                agent="mcp_gateway",
                event="tool_call_complete",
                tool=tool_name,
                role=role.value,
                correlation_id=correlation_id,
            )
        return result

    def list_tools(self) -> list[str]:
        return sorted(self._handlers.keys())

    def list_tools_for_role(self, role: AgentRole) -> list[str]:
        return sorted(
            name
            for name, roles in self._permissions.items()
            if role in roles and name in self._handlers
        )
