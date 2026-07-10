"""Session schema — canonical in-memory session document (Phase 4 Task 1)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from src.shared.messages.types import ConversationPhase, TripConstraints

MAX_CLARIFYING_QUESTIONS = 6


class ConversationTurn(BaseModel):
    """One message in the user-facing conversation history."""

    role: str = Field(..., min_length=1, description="Speaker role, e.g. user or assistant.")
    content: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionData(BaseModel):
    """Complete session state owned by the Session Manager.

    The Supervisor reads and writes this document exclusively through SessionManager APIs.
    """

    session_id: str
    trip_constraints: TripConstraints = Field(
        default_factory=TripConstraints,
        description="User-provided trip constraints (city, days, interests, pace, etc.).",
    )
    clarifying_questions_asked: int = Field(
        default=0,
        ge=0,
        description="Number of clarifying questions asked (cap enforced by Session Manager).",
    )
    itinerary: dict[str, Any] | None = None
    itinerary_approved: bool = False
    last_eval_report: dict[str, Any] | None = None
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    poi_registry: dict[str, Any] = Field(default_factory=dict)
    rag_citations: list[dict[str, Any]] = Field(default_factory=list)
    conversation_phase: ConversationPhase = ConversationPhase.INTAKE
    last_review_verdict: str | None = None
    user_email: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def user_constraints(self) -> TripConstraints:
        """Alias for ``trip_constraints`` used in architecture docs."""
        return self.trip_constraints

    @property
    def clarification_count(self) -> int:
        """Alias for ``clarifying_questions_asked``."""
        return self.clarifying_questions_asked
