"""Supervisor Agent — sole user-facing component (Phase 4)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from src.agents.base import BaseAgent
from src.agents.supervisor.intent import classify_intent, is_greeting
from src.agents.supervisor.slots import (
    clarification_question,
    constraints_payload,
    extract_slots,
    format_confirmation_summary,
    has_sufficient_constraints,
    merge_constraints,
    next_clarification_slot,
)
from src.platform.session.manager import SessionManager
from src.shared.messages.types import (
    AgentRole,
    ConversationPhase,
    PlanArtifact,
    ReviewStatus,
    ReviewVerdict,
    TaskMessage,
    TaskType,
)

if TYPE_CHECKING:
    from src.agents.planning.agent import PlanningAgent
    from src.agents.review.agent import ReviewAgent

APPROVED_STATUSES = frozenset({ReviewStatus.PASS, ReviewStatus.PASS_WITH_WARNINGS})


class SupervisorAgent(BaseAgent):
    """
    Owns user conversation, intent routing, and response synthesis.
    Reads/writes session state only via SessionManager.
    On PLAN: delegates Planning → Review, then responds from ReviewVerdict only.
    """

    role = AgentRole.SUPERVISOR

    def __init__(
        self,
        llm,
        gateway,
        observability,
        session_manager: SessionManager,
        *,
        planning: PlanningAgent | None = None,
        review: ReviewAgent | None = None,
    ) -> None:
        super().__init__(llm, gateway, observability)
        self.sessions = session_manager
        self.planning = planning
        self.review = review

    async def handle_message(
        self,
        session_id: str | None,
        message: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        corr_id = self._resolve_correlation_id(correlation_id)
        session = self.sessions.get_or_create(session_id)
        sid = session.session_id

        self._trace("receive_message", corr_id, session_id=sid, message_preview=message[:80])

        self.sessions.append_conversation_turn(
            sid,
            role="user",
            content=message,
            correlation_id=corr_id,
        )

        # Always re-read after writes — never cache mutable session state locally.
        session = self.sessions.read(sid)
        extracted = extract_slots(message)
        self._trace(
            "slot_extraction",
            corr_id,
            session_id=sid,
            extracted_slots=sorted(extracted.keys()),
        )

        if extracted:
            merged = merge_constraints(session.trip_constraints, extracted)
            self.sessions.update_constraints(sid, merged)
            session = self.sessions.read(sid)

        constraints = session.trip_constraints
        sufficient = has_sufficient_constraints(constraints)
        intent = classify_intent(
            message=message,
            constraints=constraints,
            phase=session.conversation_phase,
            has_sufficient=sufficient,
        )
        self._trace(
            "intent_classification",
            corr_id,
            session_id=sid,
            intent=intent.value,
            conversation_phase=session.conversation_phase.value,
        )

        task_message: TaskMessage | None = None
        review_verdict: ReviewVerdict | None = None
        itinerary: dict[str, Any] | None = None

        if intent == TaskType.PLAN:
            response_text, task_message, review_verdict, itinerary = await self._handle_plan(
                sid, corr_id
            )
        elif intent == TaskType.CONFIRM:
            response_text = self._handle_confirm(sid, corr_id)
        else:
            response_text = self._handle_clarify(sid, corr_id, message=message)

        session = self.sessions.read(sid)
        self.sessions.append_conversation_turn(
            sid,
            role="assistant",
            content=response_text,
            correlation_id=corr_id,
        )
        session = self.sessions.read(sid)

        self._trace(
            "supervisor_response",
            corr_id,
            session_id=sid,
            intent=intent.value,
            itinerary_approved=session.itinerary_approved,
        )
        self._trace("user_response_sent", corr_id, session_id=sid, intent=intent.value)

        result: dict[str, Any] = {
            "session_id": sid,
            "correlation_id": corr_id,
            "response": response_text,
            "conversation_phase": session.conversation_phase.value,
            "itinerary_approved": session.itinerary_approved,
            "intent": intent.value,
            "task_message": task_message.model_dump(mode="json") if task_message else None,
            "itinerary": itinerary if itinerary is not None else session.itinerary,
            "review_verdict": (
                review_verdict.model_dump(mode="json") if review_verdict is not None else None
            ),
        }
        return result

    async def run(
        self,
        session_id: str | None = None,
        message: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        return await self.handle_message(session_id, message, kwargs.get("correlation_id"))

    def _resolve_correlation_id(self, correlation_id: str | None) -> str:
        if correlation_id:
            return correlation_id
        if self.observability:
            return self.observability.new_correlation_id()
        return str(uuid4())

    def _handle_clarify(self, session_id: str, corr_id: str, *, message: str) -> str:
        session = self.sessions.read(session_id)
        constraints = session.trip_constraints

        if is_greeting(message) and not constraints.city and constraints.days is None:
            response = (
                "Hello! I can help you plan a trip. "
                "Which city would you like to visit, and for how many days?"
            )
            self._trace("clarification", corr_id, session_id=session_id, slot="greeting")
            return response

        slot = next_clarification_slot(constraints)
        if slot is None:
            return self._handle_confirm(session_id, corr_id)

        if self.sessions.can_ask_clarification(session_id):
            self.sessions.increment_clarification_count(session_id)
            question = clarification_question(slot)
            self._trace("clarification", corr_id, session_id=session_id, slot=slot)
            return question

        self._trace(
            "clarification",
            corr_id,
            session_id=session_id,
            slot=slot,
            limit_reached=True,
        )
        if has_sufficient_constraints(constraints):
            return self._handle_confirm(session_id, corr_id)

        summary = format_confirmation_summary(constraints)
        self.sessions.set_conversation_phase(session_id, ConversationPhase.CONFIRM)
        return (
            "I've reached the clarification limit, so I'll continue with what I have.\n\n"
            + summary
        )

    def _handle_confirm(self, session_id: str, corr_id: str) -> str:
        self.sessions.set_conversation_phase(session_id, ConversationPhase.CONFIRM)
        session = self.sessions.read(session_id)
        summary = format_confirmation_summary(session.trip_constraints)
        self._trace("confirmation", corr_id, session_id=session_id)
        return summary

    async def _handle_plan(
        self,
        session_id: str,
        corr_id: str,
    ) -> tuple[str, TaskMessage, ReviewVerdict | None, dict[str, Any] | None]:
        if self.planning is None or self.review is None:
            raise ValueError(
                "Supervisor requires Planning and Review agents to orchestrate PLAN"
            )

        session = self.sessions.read(session_id)
        task = TaskMessage(
            task_type=TaskType.PLAN,
            session_id=session_id,
            payload={
                "constraints": constraints_payload(session.trip_constraints),
                "conversation_phase": session.conversation_phase.value,
            },
            correlation_id=corr_id,
        )
        self.sessions.update_metadata(
            session_id,
            pending_task=task.model_dump(mode="json"),
        )
        self.sessions.set_conversation_phase(session_id, ConversationPhase.ACTIVE)
        self._trace(
            "task_creation",
            corr_id,
            session_id=session_id,
            task_type=TaskType.PLAN.value,
        )
        self._trace(
            "supervisor_dispatch_planning",
            corr_id,
            session_id=session_id,
            task_type=TaskType.PLAN.value,
        )

        artifact: PlanArtifact = await self.planning.run(task)
        self._trace(
            "planning_completed",
            corr_id,
            session_id=session_id,
            poi_count=len(artifact.poi_registry),
        )

        verdict: ReviewVerdict = await self.review.run(artifact)
        self._trace(
            "review_completed",
            corr_id,
            session_id=session_id,
            status=verdict.status.value,
            regen_attempted=verdict.regen_attempted,
        )

        if verdict.status in APPROVED_STATUSES:
            itinerary = dict(verdict.final_artifact or artifact.itinerary or {})
            self.sessions.set_itinerary(
                session_id,
                itinerary,
                poi_registry=dict(artifact.poi_registry),
                rag_citations=list(artifact.rag_citations),
            )
            self.sessions.set_itinerary_approved(session_id, True)
            self.sessions.record_eval_report(
                session_id,
                verdict.eval_report.model_dump(mode="json"),
                verdict=verdict.status,
            )
            self._trace(
                "itinerary_saved",
                corr_id,
                session_id=session_id,
                itinerary_approved=True,
                total_days=itinerary.get("total_days"),
            )
            response = _format_approved_itinerary_response(itinerary, session.trip_constraints)
            return response, task, verdict, itinerary

        # Future phase: regeneration. Do not retry here.
        self.sessions.record_eval_report(
            session_id,
            verdict.eval_report.model_dump(mode="json"),
            verdict=verdict.status,
        )
        self.sessions.set_itinerary_approved(session_id, False)
        response = (
            f"Review did not approve this itinerary (status: {verdict.status.value}). "
            "Regeneration will be implemented in a future phase."
        )
        return response, task, verdict, None


def _format_approved_itinerary_response(itinerary: dict[str, Any], constraints: Any) -> str:
    city = itinerary.get("city") or getattr(constraints, "city", None) or "your destination"
    total_days = itinerary.get("total_days") or getattr(constraints, "days", None) or "?"
    lines = [
        f"Your {total_days}-day itinerary for {_title(str(city))} is ready "
        "(approved by Review).",
        "",
    ]
    for day in itinerary.get("days") or []:
        day_number = day.get("day_number", "?")
        activities = day.get("activities") or []
        if not activities:
            lines.append(f"Day {day_number}: (no stops scheduled)")
            continue
        titles = [str(activity.get("title") or "Stop") for activity in activities]
        lines.append(f"Day {day_number}: {', '.join(titles)}")
    lines.append("")
    lines.append("You can ask to adjust a day later once editing is enabled.")
    return "\n".join(lines)


def _title(value: str) -> str:
    return value[:1].upper() + value[1:] if value else value
