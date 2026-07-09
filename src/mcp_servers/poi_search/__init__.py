"""POI Search MCP server implementation (Phase 1).

In this codebase, MCP servers are accessed behind the `MCPGateway` tool registry.
Phase 1 implements Overpass API integration + POI normalization and registers the
logical tool `search_pois` in the gateway (Planning + Knowledge only).
"""

from src.mcp_servers.poi_search.service import POISearchService, build_default_poi_service

__all__ = ["POISearchService", "build_default_poi_service"]
