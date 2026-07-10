"""Itinerary Builder MCP server (Phase 3).

In this codebase, MCP servers are accessed behind the ``MCPGateway`` tool registry.
Phase 3 Task 3 implements the deterministic service layer; Gateway registration is
a later task.
"""

from src.mcp_servers.itinerary_builder.scheduler import (
    group_nearby_pois,
    schedule_day,
    schedule_itinerary,
)
from src.mcp_servers.itinerary_builder.service import (
    ItineraryBuilderService,
    build_default_itinerary_service,
)
from src.mcp_servers.itinerary_builder.travel import estimate_travel_time

__all__ = [
    "ItineraryBuilderService",
    "build_default_itinerary_service",
    "estimate_travel_time",
    "group_nearby_pois",
    "schedule_day",
    "schedule_itinerary",
]
