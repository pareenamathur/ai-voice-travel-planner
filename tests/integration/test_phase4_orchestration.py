"""Phase 4 Task 5 — Supervisor → Planning → Review orchestration integration tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from src.agents.planning.agent import PlanningAgent
from src.agents.registry import AgentRegistry
from src.agents.review.agent import ReviewAgent
from src.agents.supervisor.agent import SupervisorAgent
from src.platform.llm.adapter import LLMAdapter
from src.platform.mcp_gateway.gateway import MCPGateway
from src.platform.observability.tracer import Observability
from src.platform.session.manager import SessionManager
from src.shared.itinerary import Itinerary
from src.shared.messages.types import (
    EvalReport,
    ReviewStatus,
    ReviewVerdict,
    TaskType,
)

SAMPLE_POIS = [
    {
        "osm_id": "node/1",
        "name": "City Palace",
        "lat": 26.9855,
        "lon": 75.8513,
        "category": "culture",
        "source": "osm",
    },
    {
        "osm_id": "node/2",
        "name": "Hawa Mahal",
        "lat": 26.9239,
        "lon": 75.8267,
        "category": "culture",
        "source": "osm",
    },
    {
        "osm_id": "node/3",
        "name": "Jantar Mantar",
        "lat": 26.9248,
        "lon": 75.8246,
        "category": "culture",
        "source": "osm",
    },
]

SAMPLE_ITINERARY = {
    "city": "Jaipur",
    "total_days": 2,
    "traveler_constraints": {"pace": "relaxed", "interests": ["food", "culture"]},
    "days": [
        {
            "day_number": 1,
            "activities": [
                {
                    "id": "d1-a1",
                    "title": "City Palace",
                    "poi_id": "node/1",
                    "start_time": "09:00",
                    "end_time": "10:30",
                    "duration_minutes": 90,
                },
                {
                    "id": "d1-a2",
                    "title": "Hawa Mahal",
                    "poi_id": "node/2",
                    "start_time": "11:00",
                    "end_time": "12:30",
                    "duration_minutes": 90,
                },
            ],
            "travel_segments": [],
        },
        {
            "day_number": 2,
            "activities": [
                {
                    "id": "d2-a1",
                    "title": "Jantar Mantar",
                    "poi_id": "node/3",
                    "start_time": "09:00",
                    "end_time": "10:30",
                    "duration_minutes": 90,
                }
            ],
            "travel_segments": [],
        },
    ],
    "poi_registry": [
        {
            "poi_id": "node/1",
            "name": "City Palace",
            "latitude": 26.9855,
            "longitude": 75.8513,
            "category": "culture",
            "source": "osm",
        }
    ],
    "citations": [],
    "metadata": {"scheduler": "heuristic_v1"},
}


class RecordingGateway(MCPGateway):
    def __init__(self, observability: Observability | None = None) -> None:
        super().__init__(observability=observability)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.register("search_pois", self._search_pois)
        self.register("build_itinerary", self._build_itinerary)
        self.register("retrieve_guidance", self._retrieve_guidance)

    async def _retrieve_guidance(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "source": "rag",
            "chunks": [
                {
                    "chunk_id": "jaipur:see:1",
                    "text": "Amber Fort is best visited in the morning.",
                    "section": "See",
                }
            ],
            "citations": [],
        }

    async def invoke(self, role, tool_name, params, correlation_id=""):  # type: ignore[no-untyped-def]
        self.calls.append((tool_name, params))
        return await super().invoke(role, tool_name, params, correlation_id)

    async def _search_pois(self, **kwargs: Any) -> dict[str, Any]:
        return {"source": "osm", "pois": list(SAMPLE_POIS)}

    async def _build_itinerary(self, **kwargs: Any) -> dict[str, Any]:
        return {"source": "itinerary_builder", "itinerary": dict(SAMPLE_ITINERARY)}


@pytest.fixture
def obs() -> Observability:
    return Observability()


@pytest.fixture
def sessions() -> SessionManager:
    return SessionManager()


@pytest.fixture
def gateway(obs: Observability) -> RecordingGateway:
    return RecordingGateway(observability=obs)


@pytest.fixture
def registry(
    sessions: SessionManager,
    gateway: RecordingGateway,
    obs: Observability,
) -> AgentRegistry:
    return AgentRegistry(
        session_manager=sessions,
        llm=LLMAdapter(),
        gateway=gateway,
        observability=obs,
    )


async def _confirm_then_plan(
    supervisor: SupervisorAgent,
    *,
    correlation_id: str = "corr-e2e",
) -> dict[str, Any]:
    confirm = await supervisor.handle_message(
        None,
        "Plan a 2-day trip to Jaipur for food and culture, relaxed pace",
        correlation_id=f"{correlation_id}-confirm",
    )
    assert confirm["intent"] == TaskType.CONFIRM.value
    return await supervisor.handle_message(
        confirm["session_id"],
        "yes",
        correlation_id=correlation_id,
    )


@pytest.mark.asyncio
async def test_full_supervisor_planning_review_flow(
    registry: AgentRegistry,
    gateway: RecordingGateway,
):
    result = await _confirm_then_plan(registry.supervisor, correlation_id="corr-pass")

    assert result["intent"] == TaskType.PLAN.value
    assert result["itinerary_approved"] is True
    assert result["review_verdict"]["status"] == ReviewStatus.PASS.value
    assert result["task_message"]["task_type"] == TaskType.PLAN.value
    assert "approved by Review" not in result["response"]
    assert "is ready" in result["response"].lower()
    assert result["itinerary"] is not None
    assert "City Palace" in str(result["itinerary"])

    itinerary = Itinerary.model_validate(result["itinerary"])
    assert itinerary.city == "Jaipur"
    assert itinerary.total_days == 2
    assert [name for name, _ in gateway.calls] == ["search_pois", "build_itinerary"]


@pytest.mark.asyncio
async def test_session_updated_and_itinerary_approved(
    registry: AgentRegistry,
    sessions: SessionManager,
):
    result = await _confirm_then_plan(registry.supervisor, correlation_id="corr-session")
    session = sessions.read(result["session_id"])

    assert session.itinerary_approved is True
    assert session.itinerary is not None
    assert session.itinerary["city"] == "Jaipur"
    assert session.last_review_verdict == ReviewStatus.PASS.value
    assert session.last_eval_report is not None
    entry_names = {e["name"] for e in session.last_eval_report["entries"]}
    assert entry_names == {"feasibility", "grounding"}
    assert all(e["passed"] for e in session.last_eval_report["entries"])
    assert "node/1" in session.poi_registry
    assert session.conversation_phase.value == "active"


@pytest.mark.asyncio
async def test_orchestration_observability_spans(
    registry: AgentRegistry,
    obs: Observability,
):
    await _confirm_then_plan(registry.supervisor, correlation_id="corr-spans")
    events = [span["event"] for span in obs.get_spans("corr-spans")]

    assert "supervisor_dispatch_planning" in events
    assert "planning_completed" in events
    assert "review_completed" in events
    assert "itinerary_saved" in events
    assert "supervisor_response" in events
    assert "planning_started" in events
    assert "plan_artifact_created" in events
    assert "review_started" in events
    assert "artifact_validated" in events


@pytest.mark.asyncio
async def test_orchestration_is_deterministic(registry: AgentRegistry):
    first = await _confirm_then_plan(registry.supervisor, correlation_id="corr-det-1")
    second = await _confirm_then_plan(registry.supervisor, correlation_id="corr-det-2")

    assert first["itinerary"] == second["itinerary"]
    assert first["response"] == second["response"]
    assert first["review_verdict"]["status"] == second["review_verdict"]["status"]


@pytest.mark.asyncio
async def test_review_pass_path(registry: AgentRegistry):
    result = await _confirm_then_plan(registry.supervisor, correlation_id="corr-pass-path")
    assert result["review_verdict"]["status"] == "pass"
    assert result["itinerary_approved"] is True
    assert result["itinerary"] is not None


@pytest.mark.asyncio
async def test_review_fail_after_regen_returns_best_available(
    sessions: SessionManager,
    gateway: RecordingGateway,
    obs: Observability,
):
    planning = PlanningAgent(llm=LLMAdapter(), gateway=gateway, observability=obs)
    best_draft = {
        "city": "Jaipur",
        "total_days": 2,
        "days": [
            {
                "day_number": 1,
                "activities": [{"title": "City Palace"}],
                "travel_segments": [],
            }
        ],
    }
    review = ReviewAgent(llm=LLMAdapter(), gateway=None, observability=obs)
    review.run = AsyncMock(  # type: ignore[method-assign]
        return_value=ReviewVerdict(
            status=ReviewStatus.FAIL,
            eval_report=EvalReport(
                entries=[
                    {
                        "name": "feasibility",
                        "passed": False,
                        "reasons": ["day 1: scheduled 840 min exceeds the 600 min daily window"],
                    },
                    {"name": "grounding", "passed": True, "reasons": []},
                ]
            ),
            final_artifact=best_draft,
            regen_attempted=True,
            correlation_id="corr-fail",
        )
    )
    supervisor = SupervisorAgent(
        llm=LLMAdapter(),
        gateway=gateway,
        observability=obs,
        session_manager=sessions,
        planning=planning,
        review=review,
    )

    result = await _confirm_then_plan(supervisor, correlation_id="corr-fail")
    session = sessions.read(result["session_id"])

    assert result["intent"] == TaskType.PLAN.value
    assert result["itinerary_approved"] is False
    assert result["itinerary"] == best_draft
    assert "couldn't finalize" in result["response"].lower()
    assert "automatic revision" in result["response"].lower()
    assert "feasibility" in result["response"].lower()
    assert result["review_verdict"]["status"] == ReviewStatus.FAIL.value
    assert result["review_verdict"]["regen_attempted"] is True
    assert session.itinerary_approved is False
    assert session.itinerary == best_draft
    assert session.last_review_verdict == ReviewStatus.FAIL.value
    assert session.last_eval_report is not None
    assert session.last_eval_report["entries"][0]["name"] == "feasibility"
    assert session.last_eval_report["entries"][0]["passed"] is False

    events = [span["event"] for span in obs.get_spans("corr-fail")]
    assert "supervisor_dispatch_planning" in events
    assert "planning_completed" in events
    assert "review_completed" in events
    assert "itinerary_saved" not in events
    assert "itinerary_saved_unapproved" in events


@pytest.mark.asyncio
async def test_planning_never_returns_directly_to_user(registry: AgentRegistry):
    result = await _confirm_then_plan(registry.supervisor, correlation_id="corr-gate")
    assert "approved by Review" not in result["response"]
    assert "is ready" in result["response"].lower()
    assert result["review_verdict"] is not None
    assert "plan_artifact" not in result
