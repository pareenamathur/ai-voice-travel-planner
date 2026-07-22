"""Review Agent — final quality gate (Phase 7 Task 2).

Runs Feasibility / Grounding / Edit Correctness evals on PlanArtifact and
EditArtifact. On failure, issues exactly one RegenRequest to the originating
agent, re-runs only the failed evals, and returns a ReviewVerdict to Supervisor.
Never user-facing; never calls MCP tools.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from src.agents.base import BaseAgent
from src.evals import (
    evaluate_edit_correctness,
    evaluate_feasibility,
    evaluate_grounding,
)
from src.shared.messages.types import (
    AgentRole,
    EditArtifact,
    EvalReport,
    EvalReportEntry,
    PlanArtifact,
    RegenRequest,
    ReviewStatus,
    ReviewVerdict,
)

if TYPE_CHECKING:
    from src.agents.edit.agent import EditAgent
    from src.agents.planning.agent import PlanningAgent

PLAN_EVAL_NAMES = ("feasibility", "grounding")
EDIT_EVAL_NAMES = ("feasibility", "grounding", "edit_correctness")


class ReviewAgent(BaseAgent):
    """Evaluate plan/edit artifacts and request at most one regeneration."""

    role = AgentRole.REVIEW

    def __init__(
        self,
        llm: Any,
        gateway: Any = None,
        observability: Any = None,
        *,
        planning: PlanningAgent | None = None,
        edit: EditAgent | None = None,
    ) -> None:
        super().__init__(llm, gateway, observability)
        self.planning = planning
        self.edit = edit

    def set_originators(
        self,
        *,
        planning: PlanningAgent | None = None,
        edit: EditAgent | None = None,
    ) -> None:
        """Wire originating agents for RegenRequest dispatch (registry only)."""
        if planning is not None:
            self.planning = planning
        if edit is not None:
            self.edit = edit

    async def run(self, artifact: PlanArtifact | dict[str, Any]) -> ReviewVerdict:
        """Accept a PlanArtifact, evaluate, optionally regen once, return verdict."""
        return await self.review_plan(artifact)

    async def review_plan(self, artifact: PlanArtifact | dict[str, Any]) -> ReviewVerdict:
        correlation_id = self._peek_correlation_id(artifact)
        self._trace("review_started", correlation_id, artifact_type="plan")

        plan = self._validate_plan_artifact(artifact)
        self._trace(
            "artifact_validated",
            plan.correlation_id,
            artifact_type="plan",
            has_itinerary=bool(plan.itinerary),
        )

        report = self._evaluate_plan(plan)
        self._emit_eval_completed(plan.correlation_id, report, artifact_type="plan", attempt=0)

        if report.all_passed:
            return self._verdict(
                status=ReviewStatus.PASS,
                report=report,
                final_artifact=dict(plan.itinerary) if plan.itinerary else {},
                regen_attempted=False,
                correlation_id=plan.correlation_id,
                artifact_type="plan",
            )

        regenerated = await self._regen_plan(plan, report)
        if regenerated is None:
            return self._verdict(
                status=ReviewStatus.FAIL,
                report=report,
                final_artifact=dict(plan.itinerary) if plan.itinerary else {},
                regen_attempted=False,
                correlation_id=plan.correlation_id,
                artifact_type="plan",
            )

        failed_names = {entry.name for entry in report.entries if not entry.passed}
        regen_report = self._evaluate_plan(regenerated, only=failed_names)
        merged = self._merge_reports(report, regen_report)
        self._emit_eval_completed(
            plan.correlation_id, merged, artifact_type="plan", attempt=1
        )

        best_artifact, best_report = self._pick_best(
            (dict(plan.itinerary) if plan.itinerary else {}, report),
            (dict(regenerated.itinerary) if regenerated.itinerary else {}, merged),
        )
        status = ReviewStatus.PASS if best_report.all_passed else ReviewStatus.FAIL
        return self._verdict(
            status=status,
            report=best_report,
            final_artifact=best_artifact,
            regen_attempted=True,
            correlation_id=plan.correlation_id,
            artifact_type="plan",
        )

    async def review_edit(self, artifact: EditArtifact | dict[str, Any]) -> ReviewVerdict:
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

        report = self._evaluate_edit(edit)
        self._emit_eval_completed(edit.correlation_id, report, artifact_type="edit", attempt=0)

        if report.all_passed:
            return self._verdict(
                status=ReviewStatus.PASS,
                report=report,
                final_artifact=dict(edit.itinerary) if edit.itinerary else {},
                regen_attempted=False,
                correlation_id=edit.correlation_id,
                artifact_type="edit",
            )

        regenerated = await self._regen_edit(edit, report)
        if regenerated is None:
            return self._verdict(
                status=ReviewStatus.FAIL,
                report=report,
                final_artifact=dict(edit.itinerary) if edit.itinerary else {},
                regen_attempted=False,
                correlation_id=edit.correlation_id,
                artifact_type="edit",
            )

        failed_names = {entry.name for entry in report.entries if not entry.passed}
        regen_report = self._evaluate_edit(regenerated, only=failed_names)
        merged = self._merge_reports(report, regen_report)
        self._emit_eval_completed(
            edit.correlation_id, merged, artifact_type="edit", attempt=1
        )

        best_artifact, best_report = self._pick_best(
            (dict(edit.itinerary) if edit.itinerary else {}, report),
            (dict(regenerated.itinerary) if regenerated.itinerary else {}, merged),
        )
        status = ReviewStatus.PASS if best_report.all_passed else ReviewStatus.FAIL
        return self._verdict(
            status=status,
            report=best_report,
            final_artifact=best_artifact,
            regen_attempted=True,
            correlation_id=edit.correlation_id,
            artifact_type="edit",
        )

    def _evaluate_plan(
        self,
        plan: PlanArtifact,
        *,
        only: set[str] | None = None,
    ) -> EvalReport:
        names = only or set(PLAN_EVAL_NAMES)
        entries: list[EvalReportEntry] = []
        if "feasibility" in names:
            entries.append(evaluate_feasibility(plan.itinerary))
        if "grounding" in names:
            entries.append(
                evaluate_grounding(
                    plan.itinerary,
                    poi_registry=plan.poi_registry,
                    rag_citations=plan.rag_citations,
                )
            )
        return EvalReport(entries=entries)

    def _evaluate_edit(
        self,
        edit: EditArtifact,
        *,
        only: set[str] | None = None,
    ) -> EvalReport:
        names = only or set(EDIT_EVAL_NAMES)
        entries: list[EvalReportEntry] = []
        if "feasibility" in names:
            entries.append(evaluate_feasibility(edit.itinerary))
        if "grounding" in names:
            entries.append(evaluate_grounding(edit.itinerary))
        if "edit_correctness" in names:
            entries.append(
                evaluate_edit_correctness(
                    edit.itinerary,
                    edit.before_snapshot,
                    edit.edit_scope,
                )
            )
        return EvalReport(entries=entries)

    async def _regen_plan(
        self,
        plan: PlanArtifact,
        report: EvalReport,
    ) -> PlanArtifact | None:
        if self.planning is None:
            self._trace(
                "regen_skipped",
                plan.correlation_id,
                reason="planning_originator_unavailable",
            )
            return None

        request = self._build_regen_request(
            target=AgentRole.PLANNING,
            report=report,
            correlation_id=plan.correlation_id,
            hints={
                "itinerary": dict(plan.itinerary),
                "poi_registry": dict(plan.poi_registry),
                "rag_citations": list(plan.rag_citations),
                "constraints": dict(plan.constraints),
                "metadata": dict(plan.metadata),
                "failed_evals": [e.name for e in report.entries if not e.passed],
            },
        )
        self._trace(
            "regen_requested",
            plan.correlation_id,
            target_agent=AgentRole.PLANNING.value,
            failure_reasons=request.failure_reasons,
        )
        artifact = await self.planning.handle_regen(request.hints, plan.correlation_id)
        return self._validate_plan_artifact(artifact)

    async def _regen_edit(
        self,
        edit: EditArtifact,
        report: EvalReport,
    ) -> EditArtifact | None:
        if self.edit is None:
            self._trace(
                "regen_skipped",
                edit.correlation_id,
                reason="edit_originator_unavailable",
            )
            return None

        request = self._build_regen_request(
            target=AgentRole.EDIT,
            report=report,
            correlation_id=edit.correlation_id,
            hints={
                "itinerary": dict(edit.itinerary),
                "before_snapshot": dict(edit.before_snapshot),
                "edit_scope": edit.edit_scope.model_dump(mode="json"),
                "failed_evals": [e.name for e in report.entries if not e.passed],
            },
        )
        self._trace(
            "regen_requested",
            edit.correlation_id,
            target_agent=AgentRole.EDIT.value,
            failure_reasons=request.failure_reasons,
        )
        artifact = await self.edit.handle_regen(request.hints, edit.correlation_id)
        return self._validate_edit_artifact(artifact)

    @staticmethod
    def _build_regen_request(
        *,
        target: AgentRole,
        report: EvalReport,
        correlation_id: str,
        hints: dict[str, Any],
    ) -> RegenRequest:
        reasons: list[str] = []
        for entry in report.entries:
            if entry.passed:
                continue
            if entry.reasons:
                reasons.extend(f"{entry.name}: {reason}" for reason in entry.reasons)
            else:
                reasons.append(f"{entry.name}: failed")
        return RegenRequest(
            target_agent=target,
            failure_reasons=reasons,
            hints=hints,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _merge_reports(original: EvalReport, rerun: EvalReport) -> EvalReport:
        """Keep originally passing entries; replace re-run names with new results."""
        by_name = {entry.name: entry for entry in original.entries}
        for entry in rerun.entries:
            by_name[entry.name] = entry
        order = list(
            dict.fromkeys(
                [e.name for e in original.entries] + [e.name for e in rerun.entries]
            )
        )
        return EvalReport(entries=[by_name[name] for name in order if name in by_name])

    @staticmethod
    def _pick_best(
        first: tuple[dict[str, Any], EvalReport],
        second: tuple[dict[str, Any], EvalReport],
    ) -> tuple[dict[str, Any], EvalReport]:
        """Prefer the artifact with fewer failures; ties prefer the regenerated one."""
        first_failures = sum(1 for e in first[1].entries if not e.passed)
        second_failures = sum(1 for e in second[1].entries if not e.passed)
        if second_failures <= first_failures:
            return second
        return first

    def _verdict(
        self,
        *,
        status: ReviewStatus,
        report: EvalReport,
        final_artifact: dict[str, Any],
        regen_attempted: bool,
        correlation_id: str,
        artifact_type: str,
    ) -> ReviewVerdict:
        verdict = ReviewVerdict(
            status=status,
            eval_report=report,
            final_artifact=final_artifact,
            regen_attempted=regen_attempted,
            correlation_id=correlation_id,
        )
        self._trace(
            "review_completed",
            correlation_id,
            status=verdict.status.value,
            regen_attempted=regen_attempted,
            artifact_type=artifact_type,
            eval_passed=report.all_passed,
        )
        return verdict

    def _emit_eval_completed(
        self,
        correlation_id: str,
        report: EvalReport,
        *,
        artifact_type: str,
        attempt: int,
    ) -> None:
        per_eval = {entry.name: ("pass" if entry.passed else "fail") for entry in report.entries}
        self._trace(
            "eval_completed",
            correlation_id,
            artifact_type=artifact_type,
            attempt=attempt,
            all_passed=report.all_passed,
            **per_eval,
        )

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
