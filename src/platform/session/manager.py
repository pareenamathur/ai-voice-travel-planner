"""Session Manager — owns all conversation and itinerary state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.platform.session.schema import (
    MAX_CLARIFYING_QUESTIONS,
    ConversationTurn,
    SessionData,
)
from src.shared.messages.types import ConversationPhase, ReviewStatus, TripConstraints


class SessionNotFoundError(Exception):
    """Raised when a session_id does not exist in the store."""

    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session '{session_id}' not found")
        self.session_id = session_id


class ClarificationLimitReachedError(Exception):
    """Raised when the clarifying-question cap would be exceeded."""

    def __init__(self, session_id: str, limit: int = MAX_CLARIFYING_QUESTIONS) -> None:
        super().__init__(
            f"Session '{session_id}' has reached the clarifying question limit ({limit})"
        )
        self.session_id = session_id
        self.limit = limit


class SessionManager:
    """In-memory session store.

    The Supervisor is the only component that should mutate session state in later phases.
    Review and specialist agents receive snapshots via task payloads, not direct writes.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}

    def create(self) -> SessionData:
        session = SessionData(session_id=str(uuid4()))
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> SessionData | None:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str | None) -> SessionData:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        return self.create()

    def save(self, session: SessionData) -> SessionData:
        session.updated_at = datetime.now(UTC)
        self._sessions[session.session_id] = session
        return session

    def update_fields(self, session_id: str, **fields: Any) -> SessionData:
        session = self._require(session_id)
        for key, value in fields.items():
            setattr(session, key, value)
        return self.save(session)

    def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def list_session_ids(self) -> list[str]:
        return sorted(self._sessions.keys())

    # --- Supervisor-oriented read/write APIs (Phase 4+) ---

    def read(self, session_id: str) -> SessionData:
        """Return the current session snapshot."""
        return self._require(session_id)

    def update_constraints(
        self,
        session_id: str,
        constraints: TripConstraints | dict[str, Any],
    ) -> SessionData:
        """Merge user constraints onto the session."""
        session = self._require(session_id)
        if isinstance(constraints, dict):
            constraints = TripConstraints.model_validate(constraints)
        session.trip_constraints = session.trip_constraints.model_copy(
            update=constraints.model_dump(exclude_unset=True)
        )
        return self.save(session)

    def append_conversation_turn(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionData:
        """Append a turn to conversation history."""
        session = self._require(session_id)
        session.conversation_history.append(
            ConversationTurn(
                role=role,
                content=content,
                correlation_id=correlation_id,
                metadata=metadata or {},
            )
        )
        return self.save(session)

    def can_ask_clarification(
        self,
        session_id: str,
        *,
        max_questions: int = MAX_CLARIFYING_QUESTIONS,
    ) -> bool:
        session = self._require(session_id)
        return session.clarifying_questions_asked < max_questions

    def increment_clarification_count(
        self,
        session_id: str,
        *,
        max_questions: int = MAX_CLARIFYING_QUESTIONS,
    ) -> SessionData:
        """Increment the clarifying-question counter, enforcing the session cap."""
        session = self._require(session_id)
        if session.clarifying_questions_asked >= max_questions:
            raise ClarificationLimitReachedError(session_id, max_questions)
        session.clarifying_questions_asked += 1
        return self.save(session)

    def set_conversation_phase(self, session_id: str, phase: ConversationPhase) -> SessionData:
        session = self._require(session_id)
        session.conversation_phase = phase
        return self.save(session)

    def set_itinerary(
        self,
        session_id: str,
        itinerary: dict[str, Any],
        *,
        poi_registry: dict[str, Any] | None = None,
        rag_citations: list[dict[str, Any]] | None = None,
    ) -> SessionData:
        """Persist a canonical itinerary artifact on the session."""
        session = self._require(session_id)
        session.itinerary = itinerary
        if poi_registry is not None:
            session.poi_registry = poi_registry
        if rag_citations is not None:
            session.rag_citations = rag_citations
        return self.save(session)

    def append_rag_citations(
        self,
        session_id: str,
        citations: list[dict[str, Any]],
    ) -> SessionData:
        """Append unique RAG citations from Knowledge Agent explain flows."""
        session = self._require(session_id)
        seen = {
            str(c.get("citation_id"))
            for c in session.rag_citations
            if c.get("citation_id")
        }
        for citation in citations:
            citation_id = citation.get("citation_id")
            if citation_id and str(citation_id) in seen:
                continue
            session.rag_citations.append(citation)
            if citation_id:
                seen.add(str(citation_id))

        # Keep itinerary Sources panel in sync when guidance is retrieved later.
        if session.itinerary is not None and citations:
            itinerary = dict(session.itinerary)
            existing = list(itinerary.get("citations") or [])
            existing_ids = {
                str(c.get("citation_id")) for c in existing if c.get("citation_id")
            }
            for citation in citations:
                citation_id = citation.get("citation_id")
                if citation_id and str(citation_id) in existing_ids:
                    continue
                existing.append(citation)
                if citation_id:
                    existing_ids.add(str(citation_id))
            itinerary["citations"] = existing
            session.itinerary = itinerary

        return self.save(session)

    def set_itinerary_approved(self, session_id: str, approved: bool) -> SessionData:
        session = self._require(session_id)
        session.itinerary_approved = approved
        return self.save(session)

    def record_eval_report(
        self,
        session_id: str,
        report: dict[str, Any],
        *,
        verdict: ReviewStatus | str | None = None,
    ) -> SessionData:
        """Store the most recent Review Agent eval report."""
        session = self._require(session_id)
        session.last_eval_report = report
        if verdict is not None:
            session.last_review_verdict = (
                verdict.value if isinstance(verdict, ReviewStatus) else str(verdict)
            )
        return self.save(session)

    def update_metadata(self, session_id: str, **metadata: Any) -> SessionData:
        """Merge key/value pairs into session metadata."""
        session = self._require(session_id)
        session.metadata.update(metadata)
        return self.save(session)

    def _require(self, session_id: str) -> SessionData:
        session = self.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session
