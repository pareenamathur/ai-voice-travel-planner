"""POI search resilience and multi-interest preservation tests."""

from unittest.mock import AsyncMock

import httpx
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


@pytest.mark.asyncio
async def test_multi_interest_search_merges_supplemental_results(tmp_path) -> None:
    calls: list[str] = []

    async def run_query(query: str, *, use_cache: bool = True) -> dict:
        calls.append(query)
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
    assert len(calls) >= 2


@pytest.mark.asyncio
async def test_transient_failure_then_retry_success(tmp_path) -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"elements": [_food_element()]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        overpass = OverpassClient(
            base_url="https://overpass.test/api",
            cache_dir=tmp_path,
            client=client,
            max_attempts_per_mirror=2,
        )
        service = POISearchService(overpass=overpass, city_cache_ttl_seconds=0)
        result = await service.search_pois(city="Jaipur", interests=["food"], use_cache=False)

    assert attempts["n"] == 2
    assert result["live_poi_lookup"] is True
    assert result["pois"]


@pytest.mark.asyncio
async def test_primary_failure_uses_broader_fallback_with_partial_merge(tmp_path) -> None:
    calls = {"n": 0}

    async def run_query(query: str, *, use_cache: bool = True) -> dict:
        calls["n"] += 1
        if "restaurant" in query or "cafe" in query:
            raise OverpassError("Overpass HTTP 429: rate limited")
        return {
            "elements": [
                {
                    "type": "node",
                    "id": 9,
                    "lat": 26.93,
                    "lon": 75.77,
                    "tags": {"name": "City Palace", "tourism": "attraction"},
                }
            ]
        }

    overpass = OverpassClient(base_urls=["https://example.test/api"], cache_dir=tmp_path)
    overpass.run_query = AsyncMock(side_effect=run_query)
    service = POISearchService(overpass=overpass, city_cache_ttl_seconds=0)

    result = await service.search_pois(
        city="Jaipur",
        interests=["food"],
        use_cache=False,
    )

    assert calls["n"] >= 2
    assert result["live_poi_lookup"] is True
    assert result["pois"]


@pytest.mark.asyncio
async def test_all_providers_fail_returns_empty_without_fabricated_places(tmp_path) -> None:
    overpass = OverpassClient(base_urls=["https://example.test/api"], cache_dir=tmp_path)
    overpass.run_query = AsyncMock(side_effect=OverpassError("all mirrors failed"))
    service = POISearchService(overpass=overpass, city_cache_ttl_seconds=0)

    result = await service.search_pois(
        city="Jaipur",
        interests=["food", "adventure"],
        use_cache=False,
    )

    assert result["live_poi_lookup"] is False
    assert result["pois"] == []


@pytest.mark.asyncio
async def test_partial_poi_results_are_preserved(tmp_path) -> None:
    overpass = OverpassClient(base_urls=["https://example.test/api"], cache_dir=tmp_path)
    overpass.run_query = AsyncMock(
        return_value={
            "elements": [
                _food_element(),
                {"type": "node", "id": 3, "lat": 26.9, "lon": 75.8, "tags": {}},
            ]
        }
    )
    service = POISearchService(overpass=overpass, city_cache_ttl_seconds=0)
    result = await service.search_pois(city="Jaipur", interests=["food"], use_cache=False)

    assert len(result["pois"]) == 1
    assert result["pois"][0]["name"] == "Alpha Cafe"
    assert result["live_poi_lookup"] is True
