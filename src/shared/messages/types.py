"""Inter-agent message types for the multi-agent travel planner."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentRole(StrEnum):
    SUPERVISOR = "supervisor"
    PLANNING = "planning"
    KNOWLEDGE = "knowledge"
    EDIT = "edit"
    EXPORT = "export"
    REVIEW = "review"


class TaskType(StrEnum):
    CLARIFY = "clarify"
    CONFIRM = "confirm"
    PLAN = "plan"
    EDIT = "edit"
    EXPLAIN = "explain"
    EXPORT = "export"


class ConversationPhase(StrEnum):
    INTAKE = "intake"
    CONFIRM = "confirm"
    ACTIVE = "active"


class ReviewStatus(StrEnum):
    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    FAIL = "fail"


class TripConstraints(BaseModel):
    city: str | None = None
    days: int | None = None
    interests: list[str] = Field(default_factory=list)
    pace: str | None = None
    party_size: int | None = None
    mobility_notes: str | None = None


class TaskMessage(BaseModel):
    """Supervisor → specialist delegation."""

    task_type: TaskType
    session_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str


class PlanArtifact(BaseModel):
    """Planning Agent → Review Agent (not to Supervisor)."""

    itinerary: dict[str, Any]
    poi_registry: dict[str, Any] = Field(default_factory=dict)
    rag_citations: list[dict[str, Any]] = Field(default_factory=list)
    correlation_id: str


class EditScope(BaseModel):
    day: int | None = None
    block: str | None = None
    intent: str = ""


class EditArtifact(BaseModel):
    """Edit Agent → Review Agent (not to Supervisor)."""

    itinerary: dict[str, Any]
    edit_scope: EditScope
    before_snapshot: dict[str, Any]
    correlation_id: str


class RegenRequest(BaseModel):
    """Review Agent → originating agent (max one per operation)."""

    target_agent: AgentRole
    failure_reasons: list[str] = Field(default_factory=list)
    hints: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str


class ReviewRequest(BaseModel):
    """Supervisor → Review Agent submission envelope."""

    artifact_type: str  # "plan" | "edit"
    plan_artifact: PlanArtifact | None = None
    edit_artifact: EditArtifact | None = None
    session_id: str
    correlation_id: str


class EvalReportEntry(BaseModel):
    name: str
    passed: bool
    reasons: list[str] = Field(default_factory=list)


class EvalReport(BaseModel):
    entries: list[EvalReportEntry] = Field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(e.passed for e in self.entries)


class ReviewVerdict(BaseModel):
    """Review Agent → Supervisor (sole path for approved itineraries)."""

    status: ReviewStatus
    eval_report: EvalReport = Field(default_factory=EvalReport)
    final_artifact: dict[str, Any] | None = None
    regen_attempted: bool = False
    correlation_id: str


class AgentResult(BaseModel):
    """Knowledge / Export Agent → Supervisor."""

    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    correlation_id: str
