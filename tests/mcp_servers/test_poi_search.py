"""Phase 1 tests — Overpass client + POI search service."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from src.mcp_servers.poi_search.models import POI, osm_element_to_poi
from src.mcp_servers.poi_search.overpass import OverpassClient
from src.mcp_servers.poi_search.service import POISearchService


def test_poi_schema_normalization_node():
    poi = osm_element_to_poi(
        {
            "type": "node",
            "id": 123,
            "lat": 26.9124,
            "lon": 75.7873,
            "tags": {"name": "Test Place"},
        },
        category="food",
    )
    assert poi is not None
    assert isinstance(poi, POI)
    assert poi.osm_id == "node/123"
    assert poi.name == "Test Place"
    assert poi.source == "osm"
    assert poi.category == "food"


def test_poi_schema_normalization_way_center():
    poi = osm_element_to_poi(
        {
            "type": "way",
            "id": 456,
            "center": {"lat": 26.9, "lon": 75.8},
            "tags": {"name": "Way Place"},
        }
    )
    assert poi is not None
    assert poi.osm_id == "way/456"
    assert poi.lat == 26.9
    assert poi.lon == 75.8


@pytest.mark.asyncio
async def test_overpass_client_caches(tmp_path: Path):
    query = "[out:json];node(0,0,1,1);out;"
    payload = {"elements": []}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        oc = OverpassClient(base_url="https://overpass.test/api", cache_dir=tmp_path, client=client)
        first = await oc.run_query(query, use_cache=True)
        assert first == payload

        # Second call should hit cache; change transport payload to prove it isn't used.
        payload2 = {"elements": [{"type": "node", "id": 1}]}
        transport2 = httpx.MockTransport(lambda req: httpx.Response(200, json=payload2))
        async with httpx.AsyncClient(transport=transport2) as client2:
            oc2 = OverpassClient(
                base_url="https://overpass.test/api",
                cache_dir=tmp_path,
                client=client2,
            )
            second = await oc2.run_query(query, use_cache=True)
            assert second == payload

    # Ensure cache file exists and is valid JSON.
    cached_files = list(tmp_path.glob("overpass-*.json"))
    assert cached_files
    json.loads(cached_files[0].read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_poi_search_service_returns_pois(tmp_path: Path):
    overpass_payload = {
        "elements": [
            {
                "type": "node",
                "id": 1,
                "lat": 26.91,
                "lon": 75.79,
                "tags": {"name": "Alpha Cafe", "amenity": "cafe"},
            },
            {
                "type": "way",
                "id": 2,
                "center": {"lat": 26.92, "lon": 75.78},
                "tags": {"name": "Beta Museum", "tourism": "museum"},
            },
        ]
    }

    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=overpass_payload))
    async with httpx.AsyncClient(transport=transport) as client:
        oc = OverpassClient(base_url="https://overpass.test/api", cache_dir=tmp_path, client=client)
        service = POISearchService(overpass=oc)
        result = await service.search_pois(city="Jaipur", interests=["food"], max_results=10)

    assert result["source"] == "osm"
    assert len(result["pois"]) == 2
    assert result["pois"][0]["osm_id"].startswith(("node/", "way/", "relation/"))
    assert result["pois"][0]["category"] == "food"

