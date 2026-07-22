"""Phase 4 Task 2 — Supervisor Agent unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from src.agents.planning.agent import LIVE_POI_UNAVAILABLE_NOTE, PlanningAgent
from src.agents.review.agent import ReviewAgent
from src.agents.supervisor.agent import SupervisorAgent
from src.agents.supervisor.intent import (
    classify_intent,
    is_explicit_confirmation,
    is_greeting,
)
from src.agents.supervisor.slots import (
    extract_slots,
    has_sufficient_constraints,
    merge_constraints,
)
from src.platform.llm.adapter import LLMAdapter
from src.platform.observability.tracer import Observability
from src.platform.session.manager import SessionManager
from src.shared.messages.types import (
    ConversationPhase,
    EvalReport,
    PlanArtifact,
    ReviewStatus,
    ReviewVerdict,
    TaskType,
    TripConstraints,
)


@pytest.fixture
def sessions() -> SessionManager:
    return SessionManager()


@pytest.fixture
def obs() -> Observability:
    return Observability()


@pytest.fixture
def supervisor(sessions: SessionManager, obs: Observability) -> SupervisorAgent:
    return SupervisorAgent(
        llm=LLMAdapter(),
        gateway=None,
        observability=obs,
        session_manager=sessions,
    )


# --- Intent / slot helpers ---


def test_is_greeting():
    assert is_greeting("Hello!")
    assert is_greeting("hi")
    assert not is_greeting("Plan a trip to Jaipur")


def test_is_explicit_confirmation():
    assert is_explicit_confirmation("yes")
    assert is_explicit_confirmation("Go ahead")
    assert is_explicit_confirmation("generate")
    assert not is_explicit_confirmation("yes but change the city")
    assert not is_explicit_confirmation("Plan a 3-day trip")


@pytest.mark.parametrize(
    "message",
    [
        "yes?",
        "yes,",
        "Yes please",
        "yeah thanks",
        "ok thank you",
        "yes\u200b",
    ],
)
def test_is_explicit_confirmation_speech_variants(message: str):
    """Web Speech often appends punctuation or politeness after short affirmatives."""
    assert is_explicit_confirmation(message)


@pytest.mark.parametrize(
    "message",
    [
        "yes yes",
        "yes yes yes",
        "yeah yeah",
        "ok ok",
        "sure sure please",
        "yes yes?",
        "yes yes thanks",
    ],
)
def test_is_explicit_confirmation_repeated_affirmatives(message: str):
    """Spoken stutters like 'yes yes' must normalize to a single affirmative."""
    assert is_explicit_confirmation(message)


def test_normalize_confirmation_collapses_repeated_affirmatives():
    from src.agents.supervisor.intent import normalize_confirmation_text

    assert normalize_confirmation_text("yes yes") == "yes"
    assert normalize_confirmation_text("yes yes yes") == "yes"
    assert normalize_confirmation_text("YEAH   YEAH") == "yeah"
    assert normalize_confirmation_text("ok ok") == "ok"
    assert normalize_confirmation_text("sure sure please") == "sure please"
    assert normalize_confirmation_text("yes yes?") == "yes?"
    assert normalize_confirmation_text("yes yes thanks") == "yes thanks"


def test_extract_slots_from_rich_message():
    slots = extract_slots(
        "Plan a 3-day trip to Jaipur for food and culture, relaxed pace, "
        "medium budget, vegetarian, walking, couple"
    )
    assert slots["city"] == "jaipur"
    assert slots["days"] == 3
    assert "food" in slots["interests"]
    assert "culture" in slots["interests"]
    assert slots["pace"] == "relaxed"
    assert slots["budget"] == "medium"
    assert "vegetarian" in slots["food_preferences"]
    assert "walk" in slots["transport_preferences"]
    assert slots["party_size"] == 2


def test_merge_constraints_unions_list_fields():
    existing = TripConstraints(city="jaipur", interests=["food"])
    merged = merge_constraints(existing, {"interests": ["culture"], "days": 3})
    assert merged.city == "jaipur"
    assert merged.days == 3
    assert merged.interests == ["food", "culture"]


def test_classify_intent_paths():
    empty = TripConstraints()
    full = TripConstraints(city="jaipur", days=3)

    assert (
        classify_intent(
            message="hello",
            constraints=empty,
            phase=ConversationPhase.INTAKE,
            has_sufficient=False,
        )
        == TaskType.CLARIFY
    )
    assert (
        classify_intent(
            message="Plan Jaipur",
            constraints=full,
            phase=ConversationPhase.INTAKE,
            has_sufficient=True,
        )
        == TaskType.CONFIRM
    )
    assert (
        classify_intent(
            message="yes",
            constraints=full,
            phase=ConversationPhase.CONFIRM,
            has_sufficient=True,
        )
        == TaskType.PLAN
    )


# --- Supervisor flows ---


@pytest.mark.asyncio
async def test_greeting_flow(supervisor: SupervisorAgent, sessions: SessionManager):
    result = await supervisor.handle_message(None, "Hello", correlation_id="corr-greet")

    assert result["intent"] == TaskType.CLARIFY.value
    assert "city" in result["response"].lower() or "trip" in result["response"].lower()
    assert result["task_message"] is None
    session = sessions.read(result["session_id"])
    assert len(session.conversation_history) == 2
    assert session.conversation_history[0].role == "user"


@pytest.mark.asyncio
async def test_slot_extraction_persisted_via_session_manager(
    supervisor: SupervisorAgent,
    sessions: SessionManager,
):
    result = await supervisor.handle_message(
        None,
        "Plan a 3-day trip to Jaipur with food and culture, relaxed pace",
        correlation_id="corr-slots",
    )
    session = sessions.read(result["session_id"])

    assert session.trip_constraints.city == "jaipur"
    assert session.trip_constraints.days == 3
    assert "food" in session.trip_constraints.interests
    assert session.trip_constraints.pace == "relaxed"
    assert has_sufficient_constraints(session.trip_constraints)
    assert result["intent"] == TaskType.CONFIRM.value
    assert "I understood the following" in result["response"]
    assert "Jaipur" in result["response"]
    assert "Would you like me to generate your itinerary?" in result["response"]


@pytest.mark.asyncio
async def test_clarification_flow_asks_for_missing_days(
    supervisor: SupervisorAgent,
    sessions: SessionManager,
):
    result = await supervisor.handle_message(None, "I want to visit Jaipur")
    session = sessions.read(result["session_id"])

    assert result["intent"] == TaskType.CLARIFY.value
    assert "days" in result["response"].lower()
    assert session.trip_constraints.city == "jaipur"
    assert session.trip_constraints.days is None
    assert session.clarifying_questions_asked == 1


@pytest.mark.asyncio
async def test_clarification_limit_stops_new_questions(
    supervisor: SupervisorAgent,
    sessions: SessionManager,
):
    first = await supervisor.handle_message(None, "I need a trip")
    sid = first["session_id"]

    # Force the clarification counter to the cap without filling required slots.
    sessions.update_fields(sid, clarifying_questions_asked=6)

    result = await supervisor.handle_message(sid, "still thinking")
    session = sessions.read(sid)

    assert session.clarifying_questions_asked == 6
    assert "clarification limit" in result["response"].lower()
    # Must not increment beyond the cap.
    assert session.clarifying_questions_asked == 6


@pytest.mark.asyncio
@pytest.mark.parametrize("confirmation", ["yes", "yes?", "Yes please", "yes,", "yes yes"])
async def test_confirm_phase_transitions_to_plan_with_speech_variants(
    sessions: SessionManager,
    obs: Observability,
    confirmation: str,
):
    """Regression: confirm-phase affirmatives must create TaskMessage(PLAN), not re-confirm."""
    planning = AsyncMock(spec=PlanningAgent)
    planning.run = AsyncMock(
        return_value=PlanArtifact(
            itinerary={"city": "Jaipur", "total_days": 2, "days": []},
            correlation_id="corr-plan",
        )
    )
    review = AsyncMock(spec=ReviewAgent)
    review.run = AsyncMock(
        return_value=ReviewVerdict(
            status=ReviewStatus.PASS,
            eval_report=EvalReport(entries=[]),
            final_artifact={"city": "Jaipur", "total_days": 2, "days": []},
            regen_attempted=False,
            correlation_id="corr-plan",
        )
    )
    supervisor = SupervisorAgent(
        llm=LLMAdapter(),
        gateway=None,
        observability=obs,
        session_manager=sessions,
        planning=planning,
        review=review,
    )

    confirm = await supervisor.handle_message(
        None,
        "Plan a 2-day trip to Jaipur",
        correlation_id="corr-confirm-variant",
    )
    assert confirm["intent"] == TaskType.CONFIRM.value
    assert sessions.read(confirm["session_id"]).conversation_phase == ConversationPhase.CONFIRM

    plan = await supervisor.handle_message(
        confirm["session_id"],
        confirmation,
        correlation_id="corr-plan-variant",
    )

    assert plan["intent"] == TaskType.PLAN.value
    assert plan["task_message"] is not None
    assert plan["task_message"]["task_type"] == TaskType.PLAN.value
    assert sessions.read(confirm["session_id"]).conversation_phase == ConversationPhase.ACTIVE
    planning.run.assert_awaited_once()
    review.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_approved_response_includes_live_poi_unavailable_note(
    sessions: SessionManager,
    obs: Observability,
):
    planning = AsyncMock(spec=PlanningAgent)
    planning.run = AsyncMock(
        return_value=PlanArtifact(
            itinerary={
                "city": "Jaipur",
                "total_days": 2,
                "days": [{"day_number": 1, "activities": [{"title": "City Palace"}]}],
                "metadata": {
                    "live_poi_lookup": False,
                    "user_note": LIVE_POI_UNAVAILABLE_NOTE,
                },
            },
            correlation_id="corr-degraded",
            metadata={"live_poi_lookup": False},
        )
    )
    review = AsyncMock(spec=ReviewAgent)
    review.run = AsyncMock(
        return_value=ReviewVerdict(
            status=ReviewStatus.PASS,
            eval_report=EvalReport(entries=[]),
            final_artifact={
                "city": "Jaipur",
                "total_days": 2,
                "days": [{"day_number": 1, "activities": [{"title": "City Palace"}]}],
                "metadata": {
                    "live_poi_lookup": False,
                    "user_note": LIVE_POI_UNAVAILABLE_NOTE,
                },
            },
            regen_attempted=False,
            correlation_id="corr-degraded",
        )
    )
    supervisor = SupervisorAgent(
        llm=LLMAdapter(),
        gateway=None,
        observability=obs,
        session_manager=sessions,
        planning=planning,
        review=review,
    )

    confirm = await supervisor.handle_message(None, "Plan a 2-day trip to Jaipur")
    plan = await supervisor.handle_message(confirm["session_id"], "yes")

    assert LIVE_POI_UNAVAILABLE_NOTE in plan["response"]
    assert "Live place lookup was temporarily unavailable" in plan["response"]


@pytest.mark.asyncio
async def test_confirmation_summary_then_plan_requires_agents(
    supervisor: SupervisorAgent,
    sessions: SessionManager,
    obs: Observability,
):
    confirm = await supervisor.handle_message(
        None,
        "Plan a 3-day trip to Jaipur, medium budget, food and culture",
        correlation_id="corr-confirm",
    )
    assert confirm["intent"] == TaskType.CONFIRM.value
    assert confirm["task_message"] is None
    assert sessions.read(confirm["session_id"]).conversation_phase == ConversationPhase.CONFIRM

    # Unit fixture has no Planning/Review wired — orchestration requires them.
    with pytest.raises(ValueError, match="Planning and Review"):
        await supervisor.handle_message(
            confirm["session_id"],
            "yes",
            correlation_id="corr-plan",
        )

@pytest.mark.asyncio
async def test_plan_not_created_without_confirmation(supervisor: SupervisorAgent):
    result = await supervisor.handle_message(
        None,
        "Plan a 3-day trip to Jaipur",
    )
    assert result["intent"] == TaskType.CONFIRM.value
    assert result["task_message"] is None


@pytest.mark.asyncio
async def test_supervisor_does_not_store_state_on_instance(
    supervisor: SupervisorAgent,
    sessions: SessionManager,
):
    result = await supervisor.handle_message(None, "Plan a 2-day trip to Delhi")
    # Only SessionManager reference — no conversation caches on the agent.
    assert not hasattr(supervisor, "trip_constraints")
    assert not hasattr(supervisor, "conversation_history")
    assert sessions.read(result["session_id"]).trip_constraints.city == "delhi"


@pytest.mark.asyncio
async def test_observability_spans_for_clarify_and_confirm(
    supervisor: SupervisorAgent,
    obs: Observability,
):
    clarify = await supervisor.handle_message(
        None,
        "I want to visit Jaipur",
        correlation_id="corr-clarify",
    )
    clarify_events = [s["event"] for s in obs.get_spans("corr-clarify")]
    assert "receive_message" in clarify_events
    assert "slot_extraction" in clarify_events
    assert "intent_classification" in clarify_events
    assert "clarification" in clarify_events

    confirm = await supervisor.handle_message(
        clarify["session_id"],
        "3 days, relaxed pace",
        correlation_id="corr-conf2",
    )
    assert confirm["intent"] == TaskType.CONFIRM.value
    confirm_events = [s["event"] for s in obs.get_spans("corr-conf2")]
    assert "confirmation" in confirm_events


@pytest.mark.asyncio
async def test_multi_turn_slot_merge(supervisor: SupervisorAgent, sessions: SessionManager):
    first = await supervisor.handle_message(None, "Trip to Jaipur")
    sid = first["session_id"]
    second = await supervisor.handle_message(sid, "Make it 4 days with shopping")
    session = sessions.read(sid)

    assert session.trip_constraints.city == "jaipur"
    assert session.trip_constraints.days == 4
    assert "shopping" in session.trip_constraints.interests
    assert second["intent"] == TaskType.CONFIRM.value


def test_classify_intent_edit_when_itinerary_approved():
    constraints = TripConstraints(city="Jaipur", days=2)
    intent = classify_intent(
        message="Make Day 2 more relaxing",
        constraints=constraints,
        phase=ConversationPhase.ACTIVE,
        has_sufficient=True,
        has_itinerary=True,
        itinerary_approved=True,
    )
    assert intent == TaskType.EDIT


def test_classify_intent_explain_when_itinerary_present():
    constraints = TripConstraints(city="Jaipur", days=2)
    intent = classify_intent(
        message="Tell me more about Amber Fort",
        constraints=constraints,
        phase=ConversationPhase.ACTIVE,
        has_sufficient=True,
        has_itinerary=True,
        itinerary_approved=True,
    )
    assert intent == TaskType.EXPLAIN


def test_classify_intent_edit_requires_approval():
    constraints = TripConstraints(city="Jaipur", days=2)
    intent = classify_intent(
        message="Make Day 2 more relaxing",
        constraints=constraints,
        phase=ConversationPhase.ACTIVE,
        has_sufficient=True,
        has_itinerary=True,
        itinerary_approved=False,
    )
    assert intent == TaskType.CONFIRM


@pytest.mark.asyncio
async def test_review_pass_persists_eval_report_and_approval(
    sessions: SessionManager,
    obs: Observability,
):
    """Phase 7 Task 3 — PASS path keeps approved itinerary + eval report."""
    itinerary = {
        "city": "Jaipur",
        "total_days": 2,
        "days": [{"day_number": 1, "activities": [{"title": "City Palace"}]}],
    }
    report = EvalReport(
        entries=[
            {"name": "feasibility", "passed": True, "reasons": []},
            {"name": "grounding", "passed": True, "reasons": []},
        ]
    )
    planning = AsyncMock(spec=PlanningAgent)
    planning.run = AsyncMock(
        return_value=PlanArtifact(
            itinerary=itinerary,
            poi_registry={"node/1": {"name": "City Palace"}},
            correlation_id="corr-pass",
        )
    )
    review = AsyncMock(spec=ReviewAgent)
    review.run = AsyncMock(
        return_value=ReviewVerdict(
            status=ReviewStatus.PASS,
            eval_report=report,
            final_artifact=itinerary,
            regen_attempted=False,
            correlation_id="corr-pass",
        )
    )
    supervisor = SupervisorAgent(
        llm=LLMAdapter(),
        gateway=None,
        observability=obs,
        session_manager=sessions,
        planning=planning,
        review=review,
    )

    confirm = await supervisor.handle_message(None, "Plan a 2-day trip to Jaipur")
    result = await supervisor.handle_message(confirm["session_id"], "yes")
    session = sessions.read(result["session_id"])

    assert result["itinerary_approved"] is True
    assert result["itinerary"] == itinerary
    assert "approved by Review" in result["response"]
    assert result["review_verdict"]["status"] == ReviewStatus.PASS.value
    assert session.itinerary_approved is True
    assert session.itinerary == itinerary
    assert session.last_review_verdict == ReviewStatus.PASS.value
    assert session.last_eval_report == report.model_dump(mode="json")
    planning.run.assert_awaited_once()
    review.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_review_pass_after_regeneration_returns_regenerated_itinerary(
    sessions: SessionManager,
    obs: Observability,
):
    """Phase 7 Task 3 — PASS after Review regen uses final_artifact."""
    original = {
        "city": "Jaipur",
        "total_days": 1,
        "days": [{"day_number": 1, "activities": [{"title": "Overloaded Day"}]}],
    }
    regenerated = {
        "city": "Jaipur",
        "total_days": 2,
        "days": [
            {"day_number": 1, "activities": [{"title": "City Palace"}]},
            {"day_number": 2, "activities": [{"title": "Hawa Mahal"}]},
        ],
    }
    report = EvalReport(
        entries=[
            {"name": "feasibility", "passed": True, "reasons": []},
            {"name": "grounding", "passed": True, "reasons": []},
        ]
    )
    planning = AsyncMock(spec=PlanningAgent)
    planning.run = AsyncMock(
        return_value=PlanArtifact(itinerary=original, correlation_id="corr-regen-pass")
    )
    planning.handle_regen = AsyncMock()
    review = AsyncMock(spec=ReviewAgent)
    review.run = AsyncMock(
        return_value=ReviewVerdict(
            status=ReviewStatus.PASS,
            eval_report=report,
            final_artifact=regenerated,
            regen_attempted=True,
            correlation_id="corr-regen-pass",
        )
    )
    supervisor = SupervisorAgent(
        llm=LLMAdapter(),
        gateway=None,
        observability=obs,
        session_manager=sessions,
        planning=planning,
        review=review,
    )

    confirm = await supervisor.handle_message(None, "Plan a 2-day trip to Jaipur")
    result = await supervisor.handle_message(confirm["session_id"], "yes")
    session = sessions.read(result["session_id"])

    assert result["itinerary_approved"] is True
    assert result["itinerary"] == regenerated
    assert "trip panel" in result["response"].lower() or "ready" in result["response"].lower()
    assert result["review_verdict"]["regen_attempted"] is True
    assert session.itinerary == regenerated
    assert session.itinerary_approved is True
    assert session.last_eval_report == report.model_dump(mode="json")
    # Supervisor must not request a second regeneration itself.
    planning.handle_regen.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_fail_after_regeneration_returns_best_and_explains(
    sessions: SessionManager,
    obs: Observability,
):
    """Phase 7 Task 3 — FAIL after regen returns best draft, not approved."""
    best = {
        "city": "Jaipur",
        "total_days": 1,
        "days": [{"day_number": 1, "activities": [{"title": "City Palace"}]}],
    }
    report = EvalReport(
        entries=[
            {
                "name": "feasibility",
                "passed": False,
                "reasons": ["day 1 over budget"],
            },
            {"name": "grounding", "passed": True, "reasons": []},
        ]
    )
    planning = AsyncMock(spec=PlanningAgent)
    planning.run = AsyncMock(
        return_value=PlanArtifact(itinerary=best, correlation_id="corr-regen-fail")
    )
    planning.handle_regen = AsyncMock()
    review = AsyncMock(spec=ReviewAgent)
    review.run = AsyncMock(
        return_value=ReviewVerdict(
            status=ReviewStatus.FAIL,
            eval_report=report,
            final_artifact=best,
            regen_attempted=True,
            correlation_id="corr-regen-fail",
        )
    )
    supervisor = SupervisorAgent(
        llm=LLMAdapter(),
        gateway=None,
        observability=obs,
        session_manager=sessions,
        planning=planning,
        review=review,
    )

    confirm = await supervisor.handle_message(None, "Plan a 2-day trip to Jaipur")
    result = await supervisor.handle_message(confirm["session_id"], "yes")
    session = sessions.read(result["session_id"])

    assert result["itinerary_approved"] is False
    assert result["itinerary"] == best
    assert "quality checks did not fully pass" in result["response"].lower()
    assert "one regeneration was already attempted" in result["response"].lower()
    assert "feasibility" in result["response"].lower()
    assert "day 1 over budget" in result["response"].lower()
    assert session.itinerary_approved is False
    assert session.itinerary == best
    assert session.last_review_verdict == ReviewStatus.FAIL.value
    assert session.last_eval_report == report.model_dump(mode="json")
    planning.handle_regen.assert_not_awaited()
