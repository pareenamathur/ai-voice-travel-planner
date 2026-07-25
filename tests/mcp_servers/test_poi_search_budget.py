"""Bounded POI search budget and supplemental lookup regression tests."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from src.mcp_servers.poi_search.overpass import OverpassClient, OverpassError
from src.mcp_servers.poi_search.service import POISearchService


def _food_element() -> dict:
    return {
        "type": "node",
        "id": 1,
        "lat": 26.91,
        "lon": 75.79,
        "tags": {"name": "Alpha Cafe", "amenity": "cafe"},
    }


def _adventure_element() -> dict:
    return {
        "type": "node",
        "id": 2,
        "lat": 26.92,
        "lon": 75.78,
        "tags": {"name": "Adventure Park", "leisure": "sports_centre"},
    }


def _elements_for_query(query: str) -> list[dict]:
    elements: list[dict] = []
    if any(token in query for token in ("restaurant", "cafe", "fast_food", "amenity")):
        elements.append(_food_element())
    if any(token in query for token in ("sports_centre", "sport", "theme_park")):
        elements.append(_adventure_element())
    return elements


@pytest.mark.asyncio
async def test_combined_search_covers_both_interests_without_supplemental(tmp_path) -> None:
    calls: list[str] = []

    async def run_query(query: str, *, use_cache: bool = True) -> dict:
        calls.append(query)
        return {"elements": _elements_for_query(query)}

    overpass = OverpassClient(base_urls=["https://example.test/api"], cache_dir=tmp_path)
    overpass.run_query = AsyncMock(side_effect=run_query)
    service = POISearchService(overpass=overpass, city_cache_ttl_seconds=0)

    result = await service.search_pois(
        city="Jaipur",
        interests=["food", "adventure"],
        use_cache=False,
    )

    categories = {poi.get("category") for poi in result["pois"]}
    assert result["live_poi_lookup"] is True
    assert "food" in categories
    assert "adventure" in categories
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_combined_success_skips_supplemental_even_when_interest_missing(tmp_path) -> None:
    """Successful combined lookup must not re-query tags already searched."""
    calls: list[str] = []

    async def run_query(query: str, *, use_cache: bool = True) -> dict:
        calls.append(query)
        return {"elements": [_food_element()]}

    overpass = OverpassClient(base_urls=["https://example.test/api"], cache_dir=tmp_path)
    overpass.run_query = AsyncMock(side_effect=run_query)
    service = POISearchService(overpass=overpass, city_cache_ttl_seconds=0)

    result = await service.search_pois(
        city="Jaipur",
        interests=["food", "adventure"],
        use_cache=False,
    )

    assert result["live_poi_lookup"] is True
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_combined_failure_triggers_one_supplemental_per_missing_interest(tmp_path) -> None:
    calls: list[str] = []

    async def run_query(query: str, *, use_cache: bool = True) -> dict:
        calls.append(query)
        if len(calls) == 1:
            raise OverpassError("combined failed")
        if "sports_centre" in query or "sport" in query:
            return {"elements": [_adventure_element()]}
        return {"elements": [_food_element()]}

    overpass = OverpassClient(base_urls=["https://example.test/api"], cache_dir=tmp_path)
    overpass.run_query = AsyncMock(side_effect=run_query)
    service = POISearchService(overpass=overpass, city_cache_ttl_seconds=0)

    result = await service.search_pois(
        city="Jaipur",
        interests=["food", "adventure"],
        use_cache=False,
    )

    categories = {poi.get("category") for poi in result["pois"]}
    assert result["live_poi_lookup"] is True
    assert "food" in categories
    assert "adventure" in categories
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_supplemental_searches_run_concurrently_on_combined_failure(tmp_path) -> None:
    active = 0
    peak = 0
    calls: list[str] = []

    async def run_query(query: str, *, use_cache: bool = True) -> dict:
        nonlocal active, peak
        calls.append(query)
        if len(calls) == 1:
            raise OverpassError("combined failed")
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.05)
        active -= 1
        if "sports_centre" in query or "sport" in query:
            return {"elements": [_adventure_element()]}
        return {"elements": [_food_element()]}

    overpass = OverpassClient(base_urls=["https://example.test/api"], cache_dir=tmp_path)
    overpass.run_query = AsyncMock(side_effect=run_query)
    service = POISearchService(overpass=overpass, city_cache_ttl_seconds=0)

    await service.search_pois(
        city="Jaipur",
        interests=["food", "adventure"],
        use_cache=False,
    )

    assert peak >= 2


@pytest.mark.asyncio
async def test_overpass_timeout_preserves_partial_results_and_finishes(tmp_path) -> None:
    calls = {"n": 0}

    async def run_query(query: str, *, use_cache: bool = True) -> dict:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OverpassError("combined failed")
        if "sports_centre" in query or "sport" in query:
            await asyncio.sleep(0.2)
            return {"elements": [_adventure_element()]}
        return {"elements": [_food_element()]}

    overpass = OverpassClient(base_urls=["https://example.test/api"], cache_dir=tmp_path)
    overpass.run_query = AsyncMock(side_effect=run_query)
    service = POISearchService(
        overpass=overpass,
        city_cache_ttl_seconds=0,
        search_budget_seconds=0.15,
    )

    started = time.perf_counter()
    result = await service.search_pois(
        city="Jaipur",
        interests=["food", "adventure"],
        use_cache=False,
    )
    elapsed = time.perf_counter() - started

    assert result["live_poi_lookup"] is True
    assert any(poi.get("name") == "Alpha Cafe" for poi in result["pois"])
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_all_live_lookups_fail_finish_within_budget(tmp_path) -> None:
    overpass = OverpassClient(base_urls=["https://example.test/api"], cache_dir=tmp_path)
    overpass.run_query = AsyncMock(side_effect=OverpassError("all mirrors failed"))
    service = POISearchService(
        overpass=overpass,
        city_cache_ttl_seconds=0,
        search_budget_seconds=2.0,
    )

    started = time.perf_counter()
    result = await service.search_pois(
        city="Jaipur",
        interests=["food", "adventure"],
        use_cache=False,
    )
    elapsed = time.perf_counter() - started

    assert result["live_poi_lookup"] is False
    assert result["pois"] == []
    assert elapsed < 3.0


@pytest.mark.asyncio
async def test_broader_fallback_skipped_when_live_results_are_sufficient(tmp_path) -> None:
    elements = [
        {
            "type": "node",
            "id": index,
            "lat": 26.9 + index * 0.001,
            "lon": 75.8,
            "tags": {"name": f"Palace {index}", "tourism": "attraction"},
        }
        for index in range(1, 8)
    ]
    overpass = OverpassClient(base_urls=["https://example.test/api"], cache_dir=tmp_path)
    overpass.run_query = AsyncMock(return_value={"elements": elements})
    service = POISearchService(overpass=overpass, city_cache_ttl_seconds=0)

    result = await service.search_pois(
        city="Jaipur",
        interests=["food", "adventure"],
        use_cache=False,
    )

    assert result["live_poi_lookup"] is True
    assert len(result["pois"]) >= 6
    assert overpass.run_query.await_count == 1
