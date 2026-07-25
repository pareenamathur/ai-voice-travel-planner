"""Safety tests for curated and LLM POI fallback behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agents.planning.agent import LIVE_POI_UNAVAILABLE_NOTE, PlanningAgent
from src.mcp_servers.poi_search.fallback import (
    curated_pois_for_city,
    ensure_poi_source_labels,
    is_curated_poi,
    is_live_poi,
    merge_live_and_curated_pois,
    missing_curated_interests,
    parse_llm_pois_payload,
    well_known_pois_for_city,
)
from src.platform.llm.adapter import LLMAdapter
from src.platform.mcp_gateway.gateway import MCPGateway
from src.platform.observability.tracer import Observability
from src.shared.messages.types import AgentRole, TaskMessage, TaskType


def test_parse_llm_pois_payload_rejects_invented_place_with_coordinates():
    payload = """
    [
      {
        "name": "Totally Fake Adventure Tower",
        "lat": 12.34,
        "lon": 56.78,
        "category": "adventure",
        "opening_hours": "09:00-18:00",
        "rating": 4.9,
        "address": "123 Imaginary Street"
      }
    ]
    """
    assert parse_llm_pois_payload(payload, city="Jaipur") == []


def test_parse_llm_pois_payload_rejects_fabricated_coordinates_only():
    payload = '[{"name": "Mystery Spot", "lat": 0.0, "lon": 0.0}]'
    assert parse_llm_pois_payload(payload, city="Goa") == []


def test_curated_entries_are_marked_non_live():
    pois = curated_pois_for_city("Jaipur", interests=["adventure"])
    assert pois
    assert all(is_curated_poi(poi) for poi in pois)
    assert all(poi.get("verified_live") is False for poi in pois)
    assert all(poi.get("catalog") == "curated" for poi in pois)
    assert all("opening_hours" not in (poi.get("tags") or {}) for poi in pois)


def test_unknown_city_has_no_generic_fabricated_places():
    pois = well_known_pois_for_city("Kochi", interests=["adventure"])
    assert pois == []


def test_missing_curated_adventure_for_unknown_city():
    missing = missing_curated_interests("Kochi", ["adventure", "food"])
    assert "adventure" in missing
    assert "food" in missing


def test_jaipur_has_curated_adventure_entries():
    pois = curated_pois_for_city("Jaipur", interests=["adventure"])
    names = {poi["name"] for poi in pois}
    assert "Jhalana Leopard Safari Park" in names
    assert all(is_curated_poi(poi) for poi in pois)


def test_merge_live_and_curated_preserves_live_source_labels():
    live = [
        {
            "osm_id": "node/1",
            "name": "Live Museum",
            "lat": 26.9,
            "lon": 75.8,
            "source": "osm",
            "category": "culture",
        }
    ]
    curated = curated_pois_for_city("Jaipur", interests=["food"])[:1]
    merged = merge_live_and_curated_pois(live, curated)
    assert any(is_live_poi(poi) for poi in merged)
    assert any(is_curated_poi(poi) for poi in merged)


class _RecordingGateway(MCPGateway):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple] = []
        self.register("search_pois", self._search_pois)
        self.register("build_itinerary", self._build_itinerary)

    async def invoke(self, role, tool_name, params, correlation_id=""):
        self.calls.append((role, tool_name, params))
        return await super().invoke(role, tool_name, params, correlation_id)

    async def _search_pois(self, **kwargs):
        return {
            "source": "osm",
            "pois": [
                {
                    "osm_id": "node/99",
                    "name": "Live Palace",
                    "lat": 26.91,
                    "lon": 75.79,
                    "source": "osm",
                    "category": "culture",
                }
            ],
            "live_poi_lookup": True,
        }

    async def _build_itinerary(self, **kwargs):
        pois = kwargs.get("pois") or []
        return {
            "source": "itinerary_builder",
            "itinerary": {
                "city": kwargs["city"],
                "total_days": kwargs["total_days"],
                "traveler_constraints": kwargs.get("traveler_constraints") or {},
                "days": [
                    {
                        "day_number": 1,
                        "activities": [
                            {
                                "id": "d1-a1",
                                "title": pois[0]["name"],
                                "poi_id": pois[0]["osm_id"],
                                "duration_minutes": 90,
                            }
                        ],
                        "travel_segments": [],
                    }
                ],
                "poi_registry": [],
                "metadata": {},
            },
        }


@pytest.mark.asyncio
async def test_partial_live_results_do_not_trigger_full_unavailable_note():
    gateway = _RecordingGateway()
    agent = PlanningAgent(LLMAdapter(), gateway, Observability())
    task = TaskMessage(
        task_type=TaskType.PLAN,
        session_id="sess-partial-live",
        correlation_id="corr-partial-live",
        payload={
            "constraints": {
                "city": "Jaipur",
                "days": 2,
                "interests": ["culture", "food"],
            }
        },
    )
    artifact = await agent.run(task)
    metadata = artifact.itinerary["metadata"]
    assert metadata["live_poi_lookup"] is True
    assert LIVE_POI_UNAVAILABLE_NOTE not in str(metadata.get("user_note") or "")
    build_pois = gateway.calls[1][2]["pois"]
    assert any(is_live_poi(poi) for poi in build_pois)


@pytest.mark.asyncio
async def test_full_fallback_uses_only_curated_sources():
    class EmptyGateway(_RecordingGateway):
        async def _search_pois(self, **kwargs):
            return {"source": "osm", "pois": [], "live_poi_lookup": False}

    gateway = EmptyGateway()
    agent = PlanningAgent(LLMAdapter(), gateway, Observability())
    task = TaskMessage(
        task_type=TaskType.PLAN,
        session_id="sess-curated-only",
        correlation_id="corr-curated-only",
        payload={"constraints": {"city": "Jaipur", "days": 2, "interests": ["culture"]}},
    )
    artifact = await agent.run(task)
    build_pois = gateway.calls[1][2]["pois"]
    assert build_pois
    assert all(is_curated_poi(poi) for poi in build_pois)
    assert artifact.itinerary["metadata"]["live_poi_lookup"] is False
    assert LIVE_POI_UNAVAILABLE_NOTE in str(artifact.itinerary["metadata"].get("user_note") or "")


def test_cached_osm_without_source_counts_as_live():
    cached = {
        "osm_id": "node/555",
        "name": "Cached Fort",
        "lat": 26.9,
        "lon": 75.8,
        "category": "landmark",
    }
    assert is_live_poi(cached) is True
    labeled = ensure_poi_source_labels([cached])
    assert labeled[0]["source"] == "osm"


def test_well_known_ids_are_not_treated_as_live():
    curated = curated_pois_for_city("Jaipur", interests=["culture"])[0]
    assert is_live_poi(curated) is False


@pytest.mark.asyncio
async def test_cached_osm_without_source_does_not_trigger_unavailable_note():
    class CachedGateway(_RecordingGateway):
        async def _search_pois(self, **kwargs):
            return {
                "source": "city_cache",
                "live_poi_lookup": True,
                "pois": [
                    {
                        "osm_id": "node/777",
                        "name": "Cached Palace",
                        "lat": 26.91,
                        "lon": 75.79,
                        "category": "culture",
                    }
                ],
            }

    gateway = CachedGateway()
    agent = PlanningAgent(LLMAdapter(), gateway, Observability())
    task = TaskMessage(
        task_type=TaskType.PLAN,
        session_id="sess-cached-osm",
        correlation_id="corr-cached-osm",
        payload={"constraints": {"city": "Jaipur", "days": 2, "interests": ["culture"]}},
    )
    artifact = await agent.run(task)
    metadata = artifact.itinerary["metadata"]
    assert metadata["live_poi_lookup"] is True
    assert LIVE_POI_UNAVAILABLE_NOTE not in str(metadata.get("user_note") or "")
    build_pois = gateway.calls[1][2]["pois"]
    assert any(poi.get("source") == "osm" for poi in build_pois)


@pytest.mark.asyncio
async def test_all_live_results_do_not_show_unavailable_note():
    class LiveOnlyGateway(_RecordingGateway):
        async def _search_pois(self, **kwargs):
            return {
                "source": "osm",
                "live_poi_lookup": True,
                "pois": [
                    {
                        "osm_id": "node/1",
                        "name": "Live Museum",
                        "lat": 26.9,
                        "lon": 75.8,
                        "source": "osm",
                        "category": "culture",
                    },
                    {
                        "osm_id": "node/2",
                        "name": "Live Fort",
                        "lat": 26.91,
                        "lon": 75.81,
                        "source": "osm",
                        "category": "adventure",
                    },
                ],
            }

    gateway = LiveOnlyGateway()
    agent = PlanningAgent(LLMAdapter(), gateway, Observability())
    task = TaskMessage(
        task_type=TaskType.PLAN,
        session_id="sess-all-live",
        correlation_id="corr-all-live",
        payload={
            "constraints": {
                "city": "Jaipur",
                "days": 2,
                "interests": ["culture", "adventure"],
            }
        },
    )
    artifact = await agent.run(task)
    metadata = artifact.itinerary["metadata"]
    assert metadata["live_poi_lookup"] is True
    assert "user_note" not in metadata or LIVE_POI_UNAVAILABLE_NOTE not in str(
        metadata.get("user_note") or ""
    )
    build_pois = gateway.calls[1][2]["pois"]
    assert all(is_live_poi(poi) for poi in build_pois)
