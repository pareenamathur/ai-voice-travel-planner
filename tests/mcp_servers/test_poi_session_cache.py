"""POI search session cache."""

from unittest.mock import AsyncMock

import pytest

from src.mcp_servers.poi_search.overpass import OverpassClient
from src.mcp_servers.poi_search.service import POISearchService


@pytest.mark.asyncio
async def test_search_pois_reuses_session_cache_for_same_interests(tmp_path) -> None:
    elements = [
        {
            "type": "node",
            "id": index,
            "lat": 26.9 + index * 0.001,
            "lon": 75.8,
            "tags": {"name": f"Test Palace {index}", "tourism": "museum"},
        }
        for index in range(1, 7)
    ]
    overpass = OverpassClient(base_urls=["https://example.test/api"], cache_dir=tmp_path)
    overpass.run_query = AsyncMock(return_value={"elements": elements})
    service = POISearchService(overpass=overpass, city_cache_ttl_seconds=0)

    first = await service.search_pois(
        city="Jaipur",
        interests=["culture"],
        session_id="session-abc",
        use_cache=False,
    )
    second = await service.search_pois(
        city="Jaipur",
        interests=["culture"],
        session_id="session-abc",
        use_cache=False,
    )

    assert first["live_poi_lookup"] is True
    assert second["live_poi_lookup"] is True
    assert overpass.run_query.await_count == 1


@pytest.mark.asyncio
async def test_search_pois_does_not_reuse_cache_for_different_interests(tmp_path) -> None:
    elements = [
        {
            "type": "node",
            "id": index,
            "lat": 26.9 + index * 0.001,
            "lon": 75.8,
            "tags": {"name": f"Test Palace {index}", "tourism": "museum"},
        }
        for index in range(1, 7)
    ]
    overpass = OverpassClient(base_urls=["https://example.test/api"], cache_dir=tmp_path)
    overpass.run_query = AsyncMock(return_value={"elements": elements})
    service = POISearchService(overpass=overpass, city_cache_ttl_seconds=0)

    await service.search_pois(
        city="Jaipur",
        interests=["culture"],
        session_id="session-abc",
        use_cache=False,
    )
    await service.search_pois(
        city="Jaipur",
        interests=["landmark"],
        session_id="session-abc",
        use_cache=False,
    )

    assert overpass.run_query.await_count == 2
