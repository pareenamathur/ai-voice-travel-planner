"""Export Agent and gateway integration tests."""

from __future__ import annotations

import base64

import pytest

from src.agents.export.agent import ExportAgent
from src.export.service import ExportService
from src.platform.mcp_gateway.gateway import MCPGateway, PermissionDeniedError
from src.platform.observability.tracer import Observability
from src.platform.llm.adapter import LLMAdapter
from src.shared.messages.types import AgentRole, TaskMessage, TaskType

_ITINERARY = {
    "city": "Jaipur",
    "total_days": 1,
    "traveler_constraints": {},
    "days": [
        {
            "day_number": 1,
            "activities": [
                {
                    "id": "a1",
                    "title": "Hawa Mahal",
                    "start_time": "10:00",
                    "end_time": "11:30",
                    "duration_minutes": 90,
                }
            ],
            "travel_segments": [],
        }
    ],
    "poi_registry": [],
    "citations": [],
}


@pytest.fixture
def export_agent() -> ExportAgent:
    obs = Observability()
    gateway = MCPGateway(observability=obs)
    gateway.register("trigger_export", _trigger_export_stub)
    return ExportAgent(LLMAdapter(), gateway, obs)


async def _trigger_export_stub(**kwargs):
    return ExportService().export(
        itinerary=kwargs["itinerary"],
        export_format=kwargs["export_format"],
        trip_title=kwargs.get("trip_title"),
        extra_citations=kwargs.get("rag_citations"),
    )


@pytest.mark.asyncio
async def test_export_agent_returns_base64_payload(export_agent: ExportAgent):
    task = TaskMessage(
        task_type=TaskType.EXPORT,
        session_id="sess-1",
        payload={"itinerary": _ITINERARY, "format": "markdown"},
        correlation_id="corr-export",
    )
    result = await export_agent.run(task)
    assert result.status == "ok"
    decoded = base64.b64decode(result.payload["content_base64"])
    assert b"Hawa Mahal" in decoded
    assert result.payload["filename"].endswith(".md")


@pytest.mark.asyncio
async def test_gateway_blocks_non_export_role():
    obs = Observability()
    gateway = MCPGateway(observability=obs)
    gateway.register("trigger_export", _trigger_export_stub)

    with pytest.raises(PermissionDeniedError):
        await gateway.invoke(
            AgentRole.PLANNING,
            "trigger_export",
            {"itinerary": _ITINERARY, "export_format": "json"},
        )
