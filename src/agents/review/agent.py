"""Review Agent — final quality gate for plan and edit workflows (Phase 7+)."""

from src.agents.base import BaseAgent
from src.shared.messages.types import (
    AgentRole,
    EditArtifact,
    PlanArtifact,
    RegenRequest,
    ReviewRequest,
    ReviewStatus,
    ReviewVerdict,
)


class ReviewAgent(BaseAgent):
    """
    Runs Feasibility, Grounding, Edit Correctness evals.
    Returns ReviewVerdict to Supervisor only. Phase 0: passthrough stub.
    """

    role = AgentRole.REVIEW

    async def run(self, request: ReviewRequest) -> ReviewVerdict:
        self._trace("review_started", request.correlation_id, artifact_type=request.artifact_type)
        # Phase 7: run real evals + optional one regen
        return ReviewVerdict(
            status=ReviewStatus.PASS,
            final_artifact=self._extract_artifact(request),
            regen_attempted=False,
            correlation_id=request.correlation_id,
        )

    async def review_plan(self, artifact: PlanArtifact) -> ReviewVerdict:
        return await self.run(
            ReviewRequest(
                artifact_type="plan",
                plan_artifact=artifact,
                session_id="",
                correlation_id=artifact.correlation_id,
            )
        )

    async def review_edit(self, artifact: EditArtifact) -> ReviewVerdict:
        return await self.run(
            ReviewRequest(
                artifact_type="edit",
                edit_artifact=artifact,
                session_id="",
                correlation_id=artifact.correlation_id,
            )
        )

    async def request_regen(self, regen: RegenRequest) -> None:
        self._trace("regen_dispatch", regen.correlation_id, target=regen.target_agent.value)

    @staticmethod
    def _extract_artifact(request: ReviewRequest) -> dict | None:
        if request.plan_artifact:
            return request.plan_artifact.itinerary
        if request.edit_artifact:
            return request.edit_artifact.itinerary
        return None
