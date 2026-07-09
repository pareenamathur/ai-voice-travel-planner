"""Session Manager — owns all conversation and itinerary state."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.shared.messages.types import ConversationPhase, TripConstraints


class SessionData(BaseModel):
    session_id: str
    trip_constraints: TripConstraints = Field(default_factory=TripConstraints)
    itinerary: dict[str, Any] | None = None
    poi_registry: dict[str, Any] = Field(default_factory=dict)
    rag_citations: list[dict[str, Any]] = Field(default_factory=list)
    clarifying_questions_asked: int = 0
    conversation_phase: ConversationPhase = ConversationPhase.INTAKE
    itinerary_approved: bool = False
    last_eval_report: dict[str, Any] | None = None
    last_review_verdict: str | None = None
    user_email: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SessionManager:
    """In-memory session store. Supervisor reads/writes; Review reads."""

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
        session = self._sessions[session_id]
        for key, value in fields.items():
            setattr(session, key, value)
        return self.save(session)

    def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None
