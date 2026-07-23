"""Supervisor Agent — sole user-facing component (Phase 4)."""

from __future__ import annotations

import base64
import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from src.agents.base import BaseAgent
from src.agents.supervisor.intent import classify_intent, is_greeting, is_new_trip_request
from src.agents.supervisor.recommend import recommend_search_interests
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
    EditArtifact,
    PlanArtifact,
    ReviewStatus,
    ReviewVerdict,
    TaskMessage,
    TaskType,
)

if TYPE_CHECKING:
    from src.agents.edit.agent import EditAgent
    from src.agents.export.agent import ExportAgent
    from src.agents.knowledge.agent import KnowledgeAgent
    from src.agents.planning.agent import PlanningAgent
    from src.agents.review.agent import ReviewAgent

APPROVED_STATUSES = frozenset({ReviewStatus.PASS, ReviewStatus.PASS_WITH_WARNINGS})

EXPORT_NOT_APPROVED_MESSAGE = (
    "This itinerary isn't approved yet. Please finalize it before exporting."
)


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
        edit: EditAgent | None = None,
        knowledge: KnowledgeAgent | None = None,
        export: ExportAgent | None = None,
    ) -> None:
        super().__init__(llm, gateway, observability)
        self.sessions = session_manager
        self.planning = planning
        self.review = review
        self.edit = edit
        self.knowledge = knowledge
        self.export = export

    async def handle_message(
        self,
        session_id: str | None,
        message: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        corr_id = self._resolve_correlation_id(correlation_id)
        turn_started = time.perf_counter()
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

        if is_new_trip_request(message) and (
            session.itinerary_approved or bool(session.itinerary)
        ):
            self.sessions.reset_trip_plan(sid)
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
        has_itinerary = bool(session.itinerary)
        intent = classify_intent(
            message=message,
            constraints=constraints,
            phase=session.conversation_phase,
            has_sufficient=sufficient,
            has_itinerary=has_itinerary,
            itinerary_approved=session.itinerary_approved,
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
        # Only set when the itinerary document actually changed (PLAN / EDIT).
        # Informational turns must not re-send the itinerary (avoids chat duplication).
        itinerary: dict[str, Any] | None = None

        if intent == TaskType.PLAN:
            plan_started = time.perf_counter()
            response_text, task_message, review_verdict, itinerary = await self._handle_plan(
                sid, corr_id
            )
            self._trace(
                "supervisor_plan_flow",
                corr_id,
                session_id=sid,
                duration_ms=round((time.perf_counter() - plan_started) * 1000, 2),
            )
        elif intent == TaskType.EDIT:
            edit_started = time.perf_counter()
            response_text, task_message, review_verdict, itinerary = await self._handle_edit(
                sid, corr_id, message
            )
            self._trace(
                "supervisor_edit_flow",
                corr_id,
                session_id=sid,
                duration_ms=round((time.perf_counter() - edit_started) * 1000, 2),
            )
        elif intent == TaskType.EXPLAIN:
            explain_started = time.perf_counter()
            response_text, task_message = await self._handle_explain(sid, corr_id, message)
            review_verdict = None
            self._trace(
                "supervisor_explain_flow",
                corr_id,
                session_id=sid,
                duration_ms=round((time.perf_counter() - explain_started) * 1000, 2),
            )
        elif intent == TaskType.RECOMMEND:
            recommend_started = time.perf_counter()
            response_text, task_message = await self._handle_recommend(sid, corr_id, message)
            review_verdict = None
            self._trace(
                "supervisor_recommend_flow",
                corr_id,
                session_id=sid,
                duration_ms=round((time.perf_counter() - recommend_started) * 1000, 2),
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
        self._trace(
            "handle_message_complete",
            corr_id,
            session_id=sid,
            intent=intent.value,
            duration_ms=round((time.perf_counter() - turn_started) * 1000, 2),
        )

        result: dict[str, Any] = {
            "session_id": sid,
            "correlation_id": corr_id,
            "response": response_text,
            "conversation_phase": session.conversation_phase.value,
            "itinerary_approved": session.itinerary_approved,
            "intent": intent.value,
            "task_message": task_message.model_dump(mode="json") if task_message else None,
            "itinerary": itinerary,
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

        review_started = time.perf_counter()
        verdict: ReviewVerdict = await self.review.run(artifact)
        self._trace(
            "review_completed",
            corr_id,
            session_id=session_id,
            status=verdict.status.value,
            regen_attempted=verdict.regen_attempted,
            duration_ms=round((time.perf_counter() - review_started) * 1000, 2),
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
                regen_attempted=verdict.regen_attempted,
            )
            response = _format_approved_itinerary_response(itinerary, session.trip_constraints)
            return response, task, verdict, itinerary

        # FAIL after Review's one allowed regeneration (Supervisor never retries).
        best = dict(verdict.final_artifact or artifact.itinerary or {})
        self.sessions.record_eval_report(
            session_id,
            verdict.eval_report.model_dump(mode="json"),
            verdict=verdict.status,
        )
        self.sessions.set_itinerary_approved(session_id, False)
        if best:
            self.sessions.set_itinerary(
                session_id,
                best,
                poi_registry=dict(artifact.poi_registry),
                rag_citations=list(artifact.rag_citations),
            )
            self._trace(
                "itinerary_saved_unapproved",
                corr_id,
                session_id=session_id,
                itinerary_approved=False,
                regen_attempted=verdict.regen_attempted,
            )
        response = _format_failed_review_response(
            best,
            verdict,
            subject="itinerary",
        )
        return response, task, verdict, best if best else None

    async def _handle_edit(
        self,
        session_id: str,
        corr_id: str,
        message: str,
    ) -> tuple[str, TaskMessage, ReviewVerdict | None, dict[str, Any] | None]:
        if self.edit is None or self.review is None:
            raise ValueError("Supervisor requires Edit and Review agents to orchestrate EDIT")

        session = self.sessions.read(session_id)
        if not session.itinerary or not session.itinerary_approved:
            return (
                "Please generate and confirm an itinerary before requesting edits.",
                TaskMessage(
                    task_type=TaskType.EDIT,
                    session_id=session_id,
                    payload={},
                    correlation_id=corr_id,
                ),
                None,
                None,
            )

        before_snapshot = dict(session.itinerary)
        task = TaskMessage(
            task_type=TaskType.EDIT,
            session_id=session_id,
            payload={
                "edit_intent": message,
                "message": message,
                "itinerary": dict(session.itinerary),
                "before_snapshot": before_snapshot,
                "city": session.itinerary.get("city") or session.trip_constraints.city,
            },
            correlation_id=corr_id,
        )
        self._trace(
            "supervisor_dispatch_edit",
            corr_id,
            session_id=session_id,
            task_type=TaskType.EDIT.value,
        )

        artifact: EditArtifact = await self.edit.run(task)
        review_started = time.perf_counter()
        verdict: ReviewVerdict = await self.review.review_edit(artifact)
        self._trace(
            "review_completed",
            corr_id,
            session_id=session_id,
            status=verdict.status.value,
            regen_attempted=verdict.regen_attempted,
            duration_ms=round((time.perf_counter() - review_started) * 1000, 2),
            artifact_type="edit",
        )

        if verdict.status in APPROVED_STATUSES:
            itinerary = dict(verdict.final_artifact or artifact.itinerary or {})
            self.sessions.set_itinerary(
                session_id,
                itinerary,
                poi_registry=dict(session.poi_registry),
                rag_citations=list(session.rag_citations),
            )
            self.sessions.set_itinerary_approved(session_id, True)
            self.sessions.record_eval_report(
                session_id,
                verdict.eval_report.model_dump(mode="json"),
                verdict=verdict.status,
            )
            response = _format_edit_response(itinerary, artifact.edit_scope)
            return response, task, verdict, itinerary

        # Keep the previously approved itinerary; surface best failed draft in the response.
        self.sessions.record_eval_report(
            session_id,
            verdict.eval_report.model_dump(mode="json"),
            verdict=verdict.status,
        )
        self.sessions.set_itinerary_approved(session_id, False)
        best = dict(verdict.final_artifact or artifact.itinerary or {})
        response = _format_failed_review_response(
            best,
            verdict,
            subject="edit",
            previous_preserved=True,
        )
        return response, task, verdict, before_snapshot

    async def _handle_explain(
        self,
        session_id: str,
        corr_id: str,
        message: str,
    ) -> tuple[str, TaskMessage]:
        if self.knowledge is None:
            raise ValueError("Supervisor requires Knowledge agent to orchestrate EXPLAIN")

        session = self.sessions.read(session_id)
        if not session.itinerary:
            return (
                "I can explain places after your itinerary is ready. "
                "Start by planning a trip first.",
                TaskMessage(
                    task_type=TaskType.EXPLAIN,
                    session_id=session_id,
                    payload={},
                    correlation_id=corr_id,
                ),
            )

        task = TaskMessage(
            task_type=TaskType.EXPLAIN,
            session_id=session_id,
            payload={
                "question": message,
                "message": message,
                "city": session.itinerary.get("city") or session.trip_constraints.city,
                "itinerary": dict(session.itinerary),
                "poi_registry": dict(session.poi_registry),
                "trip_constraints": constraints_payload(session.trip_constraints),
                "eval_report": session.last_eval_report,
            },
            correlation_id=corr_id,
        )
        self._trace(
            "supervisor_dispatch_knowledge",
            corr_id,
            session_id=session_id,
            task_type=TaskType.EXPLAIN.value,
        )

        result = await self.knowledge.run(task)
        if result.citations:
            self.sessions.append_rag_citations(session_id, list(result.citations))

        answer = str(result.payload.get("answer") or "").strip()
        if not answer:
            answer = "I couldn't find grounded guidance for that question right now."
        return answer, task

    async def _handle_recommend(
        self,
        session_id: str,
        corr_id: str,
        message: str,
    ) -> tuple[str, TaskMessage]:
        if self.knowledge is None:
            raise ValueError("Supervisor requires Knowledge agent to orchestrate RECOMMEND")

        session = self.sessions.read(session_id)
        city = (
            (session.itinerary or {}).get("city")
            or session.trip_constraints.city
            or ""
        )
        city = str(city).strip()
        if not city:
            return (
                "Tell me which city you are asking about (for example, Jaipur), "
                "and I can suggest places there.",
                TaskMessage(
                    task_type=TaskType.RECOMMEND,
                    session_id=session_id,
                    payload={},
                    correlation_id=corr_id,
                ),
            )

        interests = recommend_search_interests(message)
        task = TaskMessage(
            task_type=TaskType.RECOMMEND,
            session_id=session_id,
            payload={
                "question": message,
                "message": message,
                "city": city,
                "interests": interests,
                "itinerary": dict(session.itinerary) if session.itinerary else {},
                "poi_registry": dict(session.poi_registry),
                "trip_constraints": constraints_payload(session.trip_constraints),
            },
            correlation_id=corr_id,
        )
        self._trace(
            "supervisor_dispatch_knowledge",
            corr_id,
            session_id=session_id,
            task_type=TaskType.RECOMMEND.value,
            interests=interests,
        )

        result = await self.knowledge.run(task)
        if result.citations:
            self.sessions.append_rag_citations(session_id, list(result.citations))

        answer = str(result.payload.get("answer") or "").strip()
        if not answer:
            answer = f"I couldn't find specific recommendations for {city} right now."
        return answer, task

    async def handle_export(
        self,
        session_id: str,
        export_format: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """User → Supervisor → Export Agent → Gateway (approved itineraries only)."""
        corr_id = self._resolve_correlation_id(correlation_id)
        session = self.sessions.read(session_id)

        if not session.itinerary or not session.itinerary_approved:
            self._trace(
                "export_blocked",
                corr_id,
                session_id=session_id,
                itinerary_approved=session.itinerary_approved,
            )
            return {
                "error": EXPORT_NOT_APPROVED_MESSAGE,
                "approved": False,
            }

        if self.export is None:
            raise ValueError("Supervisor requires Export agent to orchestrate EXPORT")

        city = str(session.itinerary.get("city") or session.trip_constraints.city or "Trip")
        days = session.itinerary.get("total_days") or session.trip_constraints.days or "?"
        trip_title = f"{_title(city)} — {days}-Day Trip"

        task = TaskMessage(
            task_type=TaskType.EXPORT,
            session_id=session_id,
            payload={
                "format": export_format,
                "itinerary": dict(session.itinerary),
                "trip_title": trip_title,
                "rag_citations": list(session.rag_citations),
            },
            correlation_id=corr_id,
        )
        self._trace(
            "supervisor_dispatch_export",
            corr_id,
            session_id=session_id,
            export_format=export_format,
        )

        result = await self.export.run(task)
        encoded = str(result.payload.get("content_base64") or "")
        content = base64.b64decode(encoded) if encoded else b""
        self._trace(
            "export_complete",
            corr_id,
            session_id=session_id,
            filename=result.payload.get("filename"),
        )
        return {
            "approved": True,
            "filename": result.payload.get("filename"),
            "media_type": result.payload.get("media_type"),
            "content": content,
            "format": result.payload.get("format"),
        }


def _format_edit_response(itinerary: dict[str, Any], scope: Any) -> str:
    day_number = getattr(scope, "day", None) or "?"
    lines = [
        "Your itinerary has been updated.",
        f"Day {day_number} is refreshed in the trip panel — check the timeline on the right "
        "for stops, travel times, and durations.",
    ]
    for day in itinerary.get("days") or []:
        if day.get("day_number") != day_number:
            continue
        activities = [
            a
            for a in (day.get("activities") or [])
            if str(a.get("category") or "").lower() not in {"rest", "food"}
            or a.get("poi_id")
        ]
        titles = [str(a.get("title") or "Stop") for a in activities[:4]]
        if titles:
            lines.append(f"Highlights: {', '.join(titles)}.")
        break
    sources = _format_sources_blurb(itinerary)
    if sources:
        lines.append("")
        lines.append(sources)
    return "\n".join(lines)


def _format_failed_review_response(
    itinerary: dict[str, Any],
    verdict: ReviewVerdict,
    *,
    subject: str,
    previous_preserved: bool = False,
) -> str:
    """Explain quality issues to the user without internal agent names."""
    lines = [
        f"I couldn't finalize this {subject} after checking pace, routing, and place details.",
    ]
    if verdict.regen_attempted:
        lines.append("I tried one automatic revision, but it still needs your input.")
    else:
        lines.append("The draft needs a few adjustments before it's ready.")

    failed = [entry for entry in verdict.eval_report.entries if not entry.passed]
    if failed:
        lines.append("")
        lines.append("What to try:")
        for entry in failed:
            detail = "; ".join(entry.reasons) if entry.reasons else "needs adjustment"
            lines.append(f"- {entry.name.replace('_', ' ')}: {detail}")

    if previous_preserved:
        lines.append("")
        lines.append("Your previous itinerary is unchanged.")
    elif itinerary:
        lines.append("")
        lines.append(
            "A draft is in the trip panel — export and edits stay paused until it's ready."
        )

    lines.append("")
    lines.append("You can adjust your request and try again.")
    return "\n".join(lines)


def _format_approved_itinerary_response(itinerary: dict[str, Any], constraints: Any) -> str:
    city = itinerary.get("city") or getattr(constraints, "city", None) or "your destination"
    total_days = itinerary.get("total_days") or getattr(constraints, "days", None) or "?"
    lines = [
        f"Your {total_days}-day itinerary for {_title(str(city))} is ready. "
        "Open the trip panel for the full day-by-day timeline "
        "with travel times and visit durations.",
    ]

    metadata = itinerary.get("metadata") or {}
    if metadata.get("live_poi_lookup") is False and metadata.get("user_note"):
        lines.append("")
        lines.append(str(metadata["user_note"]))

    sources = _format_sources_blurb(itinerary)
    if sources:
        lines.append("")
        lines.append(sources)

    lines.append("")
    lines.append("You can ask to adjust a day, or ask why a place was recommended.")
    return "\n".join(lines)


def _format_sources_blurb(itinerary: dict[str, Any]) -> str:
    names = _friendly_source_names(itinerary)
    if not names:
        return "Sources: trusted travel guidance and map data used for this plan."
    return "Sources: " + "; ".join(names) + "."


def _friendly_source_names(itinerary: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()

    def add(label: str) -> None:
        key = label.lower()
        if key in seen:
            return
        seen.add(key)
        labels.append(label)

    metadata = itinerary.get("metadata") or {}
    if metadata.get("live_poi_lookup") is True:
        add("OpenStreetMap")
    elif metadata.get("live_poi_lookup") is False:
        add("Trusted travel guidance")

    for citation in itinerary.get("citations") or []:
        friendly = _citation_display_name(citation)
        if friendly:
            add(friendly)

    if not labels:
        city = str(itinerary.get("city") or "").strip()
        if city:
            add(f"{_title(city)} Tourism")
    return labels


def _citation_display_name(citation: dict[str, Any]) -> str | None:
    meta = citation.get("metadata") or {}
    for key in ("label", "source"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    url = str(citation.get("source_url") or "").lower()
    section = str(citation.get("section") or "").strip()
    document_id = str(citation.get("document_id") or "").lower()
    if "wikivoyage" in url or "wikivoyage" in document_id:
        return "Wikivoyage"
    if "wikipedia" in url or "wikipedia" in document_id:
        return "Wikipedia"
    if "rajasthan" in url or "rajasthan" in document_id:
        return "Rajasthan Tourism"
    if "openstreetmap" in url or "openstreetmap" in document_id:
        return "OpenStreetMap"
    if "tourism" in url or "tourism" in document_id:
        return "Official tourism guides"
    if section:
        return section
    return None


def _title(value: str) -> str:
    return value[:1].upper() + value[1:] if value else value
