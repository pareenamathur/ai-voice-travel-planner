"""Phase 4 Task 4 — Review Agent stub unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from src.agents.review.agent import ReviewAgent
from src.platform.llm.adapter import LLMAdapter
from src.platform.observability.tracer import Observability
from src.shared.messages.types import EditArtifact, EditScope, PlanArtifact, ReviewStatus, ReviewVerdict


def _valid_artifact(**overrides) -> PlanArtifact:
    data = {
        "itinerary": {
            "city": "Jaipur",
            "total_days": 2,
            "days": [
                {"day_number": 1, "activities": [], "travel_segments": []},
                {"day_number": 2, "activities": [], "travel_segments": []},
            ],
        },
        "poi_registry": {"node/1": {"name": "City Palace"}},
        "rag_citations": [],
        "correlation_id": "corr-review-1",
        "constraints": {"city": "Jaipur", "days": 2},
        "metadata": {"source": "planning_agent"},
    }
    data.update(overrides)
    return PlanArtifact.model_validate(data)


@pytest.fixture
def obs() -> Observability:
    return Observability()


@pytest.fixture
def llm() -> MagicMock:
    adapter = MagicMock(spec=LLMAdapter)
    adapter.complete = AsyncMock()
    return adapter


@pytest.fixture
def gateway() -> MagicMock:
    gw = MagicMock()
    gw.invoke = AsyncMock()
    return gw


@pytest.fixture
def review(llm: MagicMock, gateway: MagicMock, obs: Observability) -> ReviewAgent:
    return ReviewAgent(llm=llm, gateway=gateway, observability=obs)


@pytest.mark.asyncio
async def test_valid_plan_artifact_returns_pass(review: ReviewAgent):
    artifact = _valid_artifact()
    verdict = await review.run(artifact)

    assert isinstance(verdict, ReviewVerdict)
    assert verdict.status == ReviewStatus.PASS
    assert verdict.status.value == "pass"
    assert verdict.regen_attempted is False
    assert verdict.correlation_id == "corr-review-1"
    assert verdict.final_artifact == artifact.itinerary
    assert verdict.eval_report.entries == []


@pytest.mark.asyncio
async def test_review_plan_alias(review: ReviewAgent):
    verdict = await review.review_plan(_valid_artifact())
    assert verdict.status == ReviewStatus.PASS


@pytest.mark.asyncio
async def test_valid_plan_artifact_from_dict(review: ReviewAgent):
    payload = _valid_artifact().model_dump(mode="json")
    verdict = await review.run(payload)
    assert verdict.status == ReviewStatus.PASS
    assert verdict.final_artifact["city"] == "Jaipur"


@pytest.mark.asyncio
async def test_invalid_plan_artifact_missing_correlation_id(review: ReviewAgent):
    with pytest.raises(ValueError, match="invalid PlanArtifact"):
        await review.run(
            {
                "itinerary": {"city": "Jaipur", "total_days": 1, "days": []},
            }
        )


@pytest.mark.asyncio
async def test_invalid_plan_artifact_wrong_type(review: ReviewAgent):
    with pytest.raises(ValueError, match="expects a PlanArtifact"):
        await review.run("not-an-artifact")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_pass_verdict_always_returned(review: ReviewAgent):
    # Even a minimal valid artifact always PASSes in the stub.
    artifact = PlanArtifact(itinerary={}, correlation_id="corr-min")
    verdict = await review.run(artifact)
    assert verdict.status == ReviewStatus.PASS
    assert verdict.regen_attempted is False


@pytest.mark.asyncio
async def test_no_gateway_usage(review: ReviewAgent, gateway: MagicMock):
    await review.run(_valid_artifact())
    gateway.invoke.assert_not_called()


@pytest.mark.asyncio
async def test_no_llm_usage(review: ReviewAgent, llm: MagicMock):
    await review.run(_valid_artifact())
    llm.complete.assert_not_called()


@pytest.mark.asyncio
async def test_observability_spans(review: ReviewAgent, obs: Observability):
    await review.run(_valid_artifact())
    spans = obs.get_spans("corr-review-1")
    events = [span["event"] for span in spans]

    assert events == ["review_started", "artifact_validated", "review_completed"]
    assert all(span.get("correlation_id") == "corr-review-1" for span in spans)
    assert all(span.get("agent") == "review" for span in spans)
    assert spans[-1]["status"] == "pass"


@pytest.mark.asyncio
async def test_valid_edit_artifact_returns_pass(review: ReviewAgent):
    artifact = EditArtifact(
        itinerary={"city": "Jaipur", "total_days": 2, "days": []},
        edit_scope=EditScope(day=2, intent="relax_day"),
        before_snapshot={"city": "Jaipur", "total_days": 2, "days": []},
        correlation_id="corr-edit-review",
    )
    verdict = await review.review_edit(artifact)

    assert verdict.status == ReviewStatus.PASS
    assert verdict.final_artifact == artifact.itinerary
    assert verdict.correlation_id == "corr-edit-review"
