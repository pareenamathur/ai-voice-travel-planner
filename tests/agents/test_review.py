"""Phase 7 Task 2 — Review Agent evaluation orchestration tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.agents.review.agent import ReviewAgent
from src.platform.llm.adapter import LLMAdapter
from src.platform.observability.tracer import Observability
from src.shared.messages.types import (
    EditArtifact,
    EditScope,
    PlanArtifact,
    ReviewStatus,
    ReviewVerdict,
)


def _healthy_itinerary() -> dict[str, Any]:
    return {
        "city": "Jaipur",
        "total_days": 2,
        "traveler_constraints": {"pace": "relaxed", "interests": ["culture"]},
        "metadata": {"live_poi_lookup": True},
        "poi_registry": [
            {
                "poi_id": "well_known/jaipur-city-palace",
                "name": "City Palace",
                "latitude": 26.9258,
                "longitude": 75.8237,
                "category": "culture",
                "source": "well_known",
            },
            {
                "poi_id": "well_known/jaipur-hawa-mahal",
                "name": "Hawa Mahal",
                "latitude": 26.9239,
                "longitude": 75.8267,
                "category": "sightseeing",
                "source": "well_known",
            },
        ],
        "days": [
            {
                "day_number": 1,
                "activities": [
                    {
                        "id": "d1-a1",
                        "title": "City Palace",
                        "poi_id": "well_known/jaipur-city-palace",
                        "duration_minutes": 90,
                    }
                ],
                "travel_segments": [],
            },
            {
                "day_number": 2,
                "activities": [
                    {
                        "id": "d2-a1",
                        "title": "Hawa Mahal",
                        "poi_id": "well_known/jaipur-hawa-mahal",
                        "duration_minutes": 90,
                    }
                ],
                "travel_segments": [],
            },
        ],
    }


def _overbudget_itinerary() -> dict[str, Any]:
    itinerary = _healthy_itinerary()
    itinerary["total_days"] = 1
    itinerary["days"] = [
        {
            "day_number": 1,
            "activities": [
                {"id": f"d1-a{i}", "title": f"Stop {i}", "duration_minutes": 180}
                for i in range(1, 5)
            ],
            "travel_segments": [
                {
                    "from_activity_id": "d1-a1",
                    "to_activity_id": "d1-a2",
                    "travel_minutes": 40,
                    "transport_mode": "drive",
                },
                {
                    "from_activity_id": "d1-a2",
                    "to_activity_id": "d1-a3",
                    "travel_minutes": 40,
                    "transport_mode": "drive",
                },
                {
                    "from_activity_id": "d1-a3",
                    "to_activity_id": "d1-a4",
                    "travel_minutes": 40,
                    "transport_mode": "drive",
                },
            ],
        }
    ]
    itinerary["poi_registry"] = [
        {
            "poi_id": f"well_known/stop-{i}",
            "name": f"Stop {i}",
            "latitude": 26.92,
            "longitude": 75.82,
            "source": "well_known",
        }
        for i in range(1, 5)
    ]
    for activity, ref in zip(
        itinerary["days"][0]["activities"], itinerary["poi_registry"], strict=True
    ):
        activity["poi_id"] = ref["poi_id"]
    return itinerary


def _overbudget_registry() -> dict[str, Any]:
    return {
        f"well_known/stop-{i}": {
            "osm_id": f"well_known/stop-{i}",
            "name": f"Stop {i}",
            "lat": 26.92,
            "lon": 75.82,
            "source": "well_known",
        }
        for i in range(1, 5)
    }


def _valid_plan(**overrides: Any) -> PlanArtifact:
    itinerary = _healthy_itinerary()
    data: dict[str, Any] = {
        "itinerary": itinerary,
        "poi_registry": {
            ref["poi_id"]: {
                "osm_id": ref["poi_id"],
                "name": ref["name"],
                "lat": ref["latitude"],
                "lon": ref["longitude"],
                "source": ref["source"],
            }
            for ref in itinerary["poi_registry"]
        },
        "rag_citations": [],
        "correlation_id": "corr-review-1",
        "constraints": {"city": "Jaipur", "days": 2},
        "metadata": {"source": "planning_agent"},
    }
    data.update(overrides)
    return PlanArtifact.model_validate(data)


def _valid_edit(
    *,
    itinerary: dict[str, Any] | None = None,
    before: dict[str, Any] | None = None,
    day: int = 2,
    correlation_id: str = "corr-edit-review",
) -> EditArtifact:
    base = itinerary or _healthy_itinerary()
    snapshot = before if before is not None else _healthy_itinerary()
    return EditArtifact(
        itinerary=base,
        edit_scope=EditScope(day=day, intent="relax_day"),
        before_snapshot=snapshot,
        correlation_id=correlation_id,
    )


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
def planning() -> MagicMock:
    agent = MagicMock()
    agent.handle_regen = AsyncMock()
    return agent


@pytest.fixture
def edit_agent() -> MagicMock:
    agent = MagicMock()
    agent.handle_regen = AsyncMock()
    return agent


@pytest.fixture
def review(
    llm: MagicMock,
    gateway: MagicMock,
    obs: Observability,
    planning: MagicMock,
    edit_agent: MagicMock,
) -> ReviewAgent:
    return ReviewAgent(
        llm=llm,
        gateway=gateway,
        observability=obs,
        planning=planning,
        edit=edit_agent,
    )


@pytest.mark.asyncio
async def test_pass_on_first_review(review: ReviewAgent, planning: MagicMock):
    artifact = _valid_plan()
    verdict = await review.run(artifact)

    assert isinstance(verdict, ReviewVerdict)
    assert verdict.status == ReviewStatus.PASS
    assert verdict.regen_attempted is False
    assert verdict.correlation_id == "corr-review-1"
    assert verdict.final_artifact == artifact.itinerary
    assert verdict.eval_report.all_passed
    assert {e.name for e in verdict.eval_report.entries} == {"feasibility", "grounding"}
    planning.handle_regen.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_plan_alias(review: ReviewAgent):
    verdict = await review.review_plan(_valid_plan())
    assert verdict.status == ReviewStatus.PASS


@pytest.mark.asyncio
async def test_valid_plan_artifact_from_dict(review: ReviewAgent):
    payload = _valid_plan().model_dump(mode="json")
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
async def test_fail_then_regen_succeeds(review: ReviewAgent, planning: MagicMock):
    bad = _valid_plan(
        itinerary=_overbudget_itinerary(),
        poi_registry=_overbudget_registry(),
        correlation_id="corr-regen-ok",
    )
    fixed = _valid_plan(correlation_id="corr-regen-ok")
    planning.handle_regen = AsyncMock(return_value=fixed)

    verdict = await review.run(bad)

    assert verdict.status == ReviewStatus.PASS
    assert verdict.regen_attempted is True
    assert verdict.final_artifact == fixed.itinerary
    assert verdict.eval_report.all_passed
    planning.handle_regen.assert_awaited_once()
    hints = planning.handle_regen.await_args.args[0]
    assert "feasibility" in hints["failed_evals"]


@pytest.mark.asyncio
async def test_fail_then_regen_also_fails(review: ReviewAgent, planning: MagicMock):
    bad = _valid_plan(
        itinerary=_overbudget_itinerary(),
        poi_registry=_overbudget_registry(),
        correlation_id="corr-regen-fail",
    )
    still_bad = _valid_plan(
        itinerary=_overbudget_itinerary(),
        poi_registry=bad.poi_registry,
        correlation_id="corr-regen-fail",
    )
    planning.handle_regen = AsyncMock(return_value=still_bad)

    verdict = await review.run(bad)

    assert verdict.status == ReviewStatus.FAIL
    assert verdict.regen_attempted is True
    assert verdict.final_artifact
    assert not verdict.eval_report.all_passed
    feasibility = next(e for e in verdict.eval_report.entries if e.name == "feasibility")
    assert feasibility.passed is False
    planning.handle_regen.assert_awaited_once()


@pytest.mark.asyncio
async def test_regeneration_happens_only_once(review: ReviewAgent, planning: MagicMock):
    bad = _valid_plan(
        itinerary=_overbudget_itinerary(),
        poi_registry=_overbudget_registry(),
        correlation_id="corr-regen-once",
    )
    planning.handle_regen = AsyncMock(return_value=bad)

    await review.run(bad)
    assert planning.handle_regen.await_count == 1


@pytest.mark.asyncio
async def test_eval_report_aggregates_rerun_of_failed_only(
    review: ReviewAgent, planning: MagicMock
):
    bad = _valid_plan(
        itinerary=_overbudget_itinerary(),
        poi_registry=_overbudget_registry(),
        correlation_id="corr-aggregate",
    )
    fixed = _valid_plan(correlation_id="corr-aggregate")
    planning.handle_regen = AsyncMock(return_value=fixed)

    verdict = await review.run(bad)
    names = [e.name for e in verdict.eval_report.entries]
    assert names == ["feasibility", "grounding"]
    assert all(e.passed for e in verdict.eval_report.entries)


@pytest.mark.asyncio
async def test_fail_without_planning_originator_skips_regen(
    llm: MagicMock, gateway: MagicMock, obs: Observability
):
    review = ReviewAgent(llm=llm, gateway=gateway, observability=obs, planning=None)
    bad = _valid_plan(
        itinerary=_overbudget_itinerary(),
        poi_registry=_overbudget_registry(),
    )
    verdict = await review.run(bad)
    assert verdict.status == ReviewStatus.FAIL
    assert verdict.regen_attempted is False
    events = [s["event"] for s in obs.get_spans(bad.correlation_id)]
    assert "regen_skipped" in events
    assert "regen_requested" not in events


@pytest.mark.asyncio
async def test_no_gateway_or_llm_usage(
    review: ReviewAgent, gateway: MagicMock, llm: MagicMock
):
    await review.run(_valid_plan())
    gateway.invoke.assert_not_called()
    llm.complete.assert_not_called()


@pytest.mark.asyncio
async def test_observability_spans_on_pass(review: ReviewAgent, obs: Observability):
    await review.run(_valid_plan())
    spans = obs.get_spans("corr-review-1")
    events = [span["event"] for span in spans]

    assert events == [
        "review_started",
        "artifact_validated",
        "eval_completed",
        "review_completed",
    ]
    assert all(span.get("correlation_id") == "corr-review-1" for span in spans)
    assert all(span.get("agent") == "review" for span in spans)
    eval_span = next(s for s in spans if s["event"] == "eval_completed")
    assert eval_span["feasibility"] == "pass"
    assert eval_span["grounding"] == "pass"
    assert spans[-1]["status"] == "pass"


@pytest.mark.asyncio
async def test_observability_spans_on_regen(
    review: ReviewAgent, planning: MagicMock, obs: Observability
):
    bad = _valid_plan(
        itinerary=_overbudget_itinerary(),
        poi_registry=_overbudget_registry(),
        correlation_id="corr-obs-regen",
    )
    planning.handle_regen = AsyncMock(
        return_value=_valid_plan(correlation_id="corr-obs-regen")
    )

    await review.run(bad)
    events = [s["event"] for s in obs.get_spans("corr-obs-regen")]
    assert events.count("eval_completed") == 2
    assert "regen_requested" in events
    assert events[-1] == "review_completed"


@pytest.mark.asyncio
async def test_edit_review_path_passes(review: ReviewAgent, edit_agent: MagicMock):
    artifact = _valid_edit()
    verdict = await review.review_edit(artifact)

    assert verdict.status == ReviewStatus.PASS
    assert verdict.final_artifact == artifact.itinerary
    assert verdict.correlation_id == "corr-edit-review"
    assert {e.name for e in verdict.eval_report.entries} == {
        "feasibility",
        "grounding",
        "edit_correctness",
    }
    edit_agent.handle_regen.assert_not_awaited()


@pytest.mark.asyncio
async def test_edit_review_regen_on_collateral_change(
    review: ReviewAgent, edit_agent: MagicMock
):
    before = _healthy_itinerary()
    collateral = _healthy_itinerary()
    collateral["days"][0]["activities"][0]["title"] = "City Palace Extended"
    collateral["days"][1]["activities"][0]["duration_minutes"] = 60

    fixed = _healthy_itinerary()
    fixed["days"][1]["activities"][0]["duration_minutes"] = 60

    bad = _valid_edit(
        itinerary=collateral, before=before, day=2, correlation_id="corr-edit-regen"
    )
    good = _valid_edit(
        itinerary=fixed, before=before, day=2, correlation_id="corr-edit-regen"
    )
    edit_agent.handle_regen = AsyncMock(return_value=good)

    verdict = await review.review_edit(bad)

    assert verdict.status == ReviewStatus.PASS
    assert verdict.regen_attempted is True
    edit_agent.handle_regen.assert_awaited_once()
    hints = edit_agent.handle_regen.await_args.args[0]
    assert "edit_correctness" in hints["failed_evals"]
