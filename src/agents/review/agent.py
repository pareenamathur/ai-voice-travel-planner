"""Review Agent stub — passthrough quality gate (Phase 4 Task 4)."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.agents.base import BaseAgent
from src.shared.messages.types import (
    AgentRole,
    EditArtifact,
    EvalReport,
    PlanArtifact,
    ReviewStatus,
    ReviewVerdict,
)


class ReviewAgent(BaseAgent):
    """Validate PlanArtifact and return ReviewVerdict(PASS).

    Phase 4 Task 4 stub: no evaluations, no LLM, no Gateway, no regeneration.
    Never user-facing — returns verdicts for the Supervisor only.
    """

    role = AgentRole.REVIEW

    async def run(self, artifact: PlanArtifact | dict[str, Any]) -> ReviewVerdict:
        """Accept a PlanArtifact and always return a PASS ReviewVerdict."""
        correlation_id = self._peek_correlation_id(artifact)
        self._trace("review_started", correlation_id)

        plan = self._validate_plan_artifact(artifact)
        self._trace(
            "artifact_validated",
            plan.correlation_id,
            artifact_type="plan",
            has_itinerary=bool(plan.itinerary),
        )

        verdict = ReviewVerdict(
            status=ReviewStatus.PASS,
            eval_report=EvalReport(entries=[]),
            final_artifact=dict(plan.itinerary) if plan.itinerary else {},
            regen_attempted=False,
            correlation_id=plan.correlation_id,
        )

        self._trace(
            "review_completed",
            plan.correlation_id,
            status=verdict.status.value,
            regen_attempted=False,
        )
        return verdict

    async def review_plan(self, artifact: PlanArtifact | dict[str, Any]) -> ReviewVerdict:
        """Alias for ``run`` — Planning → Review entry point."""
        return await self.run(artifact)

    async def review_edit(self, artifact: EditArtifact | dict[str, Any]) -> ReviewVerdict:
        """Validate EditArtifact and return ReviewVerdict(PASS)."""
        correlation_id = self._peek_edit_correlation_id(artifact)
        self._trace("review_started", correlation_id, artifact_type="edit")

        edit = self._validate_edit_artifact(artifact)
        self._trace(
            "artifact_validated",
            edit.correlation_id,
            artifact_type="edit",
            has_itinerary=bool(edit.itinerary),
            edit_day=edit.edit_scope.day,
        )

        verdict = ReviewVerdict(
            status=ReviewStatus.PASS,
            eval_report=EvalReport(entries=[]),
            final_artifact=dict(edit.itinerary) if edit.itinerary else {},
            regen_attempted=False,
            correlation_id=edit.correlation_id,
        )

        self._trace(
            "review_completed",
            edit.correlation_id,
            status=verdict.status.value,
            regen_attempted=False,
            artifact_type="edit",
        )
        return verdict

    def _validate_plan_artifact(self, artifact: PlanArtifact | dict[str, Any]) -> PlanArtifact:
        if isinstance(artifact, PlanArtifact):
            try:
                return PlanArtifact.model_validate(artifact.model_dump(mode="json"))
            except ValidationError as exc:
                raise ValueError(f"invalid PlanArtifact: {exc}") from exc

        if isinstance(artifact, dict):
            try:
                return PlanArtifact.model_validate(artifact)
            except ValidationError as exc:
                raise ValueError(f"invalid PlanArtifact: {exc}") from exc

        raise ValueError(
            f"Review Agent expects a PlanArtifact, got {type(artifact).__name__}"
        )

    def _validate_edit_artifact(self, artifact: EditArtifact | dict[str, Any]) -> EditArtifact:
        if isinstance(artifact, EditArtifact):
            try:
                return EditArtifact.model_validate(artifact.model_dump(mode="json"))
            except ValidationError as exc:
                raise ValueError(f"invalid EditArtifact: {exc}") from exc

        if isinstance(artifact, dict):
            try:
                return EditArtifact.model_validate(artifact)
            except ValidationError as exc:
                raise ValueError(f"invalid EditArtifact: {exc}") from exc

        raise ValueError(
            f"Review Agent expects an EditArtifact, got {type(artifact).__name__}"
        )

    @staticmethod
    def _peek_correlation_id(artifact: PlanArtifact | dict[str, Any]) -> str:
        if isinstance(artifact, PlanArtifact):
            return artifact.correlation_id
        if isinstance(artifact, dict):
            value = artifact.get("correlation_id")
            return str(value) if value else ""
        return ""

    @staticmethod
    def _peek_edit_correlation_id(artifact: EditArtifact | dict[str, Any]) -> str:
        if isinstance(artifact, EditArtifact):
            return artifact.correlation_id
        if isinstance(artifact, dict):
            value = artifact.get("correlation_id")
            return str(value) if value else ""
        return ""
