"""Tests for inter-agent message types."""

from src.shared.messages.types import (
    AgentResult,
    AgentRole,
    EditArtifact,
    EditScope,
    PlanArtifact,
    RegenRequest,
    ReviewStatus,
    ReviewVerdict,
    TaskMessage,
    TaskType,
)


def test_plan_artifact_defined():
    artifact = PlanArtifact(itinerary={"days": []}, correlation_id="c1")
    assert artifact.correlation_id == "c1"
    assert artifact.itinerary == {"days": []}


def test_edit_artifact_defined():
    artifact = EditArtifact(
        itinerary={"days": []},
        edit_scope=EditScope(day=2, intent="relax"),
        before_snapshot={},
        correlation_id="c2",
    )
    assert artifact.edit_scope.day == 2


def test_review_verdict_defined():
    verdict = ReviewVerdict(status=ReviewStatus.PASS, correlation_id="c3")
    assert verdict.status == ReviewStatus.PASS
    assert verdict.regen_attempted is False


def test_task_message_and_regen_request():
    task = TaskMessage(task_type=TaskType.PLAN, session_id="s1", correlation_id="c4")
    assert task.task_type == TaskType.PLAN

    regen = RegenRequest(
        target_agent=AgentRole.PLANNING,
        failure_reasons=["grounding fail"],
        correlation_id="c5",
    )
    assert regen.failure_reasons == ["grounding fail"]


def test_agent_result_defined():
    result = AgentResult(status="ok", correlation_id="c6")
    assert result.citations == []
