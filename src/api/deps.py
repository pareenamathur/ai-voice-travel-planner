"""Application factory and dependency wiring."""

from src.agents.registry import AgentRegistry
from src.api.config import settings
from src.mcp_servers.itinerary_builder import build_default_itinerary_service
from src.mcp_servers.poi_search import build_default_poi_service
from src.platform.llm.adapter import LLMAdapter
from src.platform.mcp_gateway.gateway import MCPGateway
from src.platform.observability.tracer import Observability
from src.platform.session.manager import SessionManager
from src.mcp_servers.export import trigger_export
from src.rag.guidance import retrieve_guidance

_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        observability = Observability()
        session_manager = SessionManager()
        gateway = MCPGateway(observability=observability)

        poi_service = build_default_poi_service(
            overpass_urls=settings.overpass_urls(),
            cache_dir=settings.osm_cache_dir,
            city_cache_ttl_seconds=settings.poi_city_cache_ttl_seconds,
        )
        gateway.register("search_pois", poi_service.search_pois)

        itinerary_service = build_default_itinerary_service()
        gateway.register("build_itinerary", itinerary_service.build_itinerary)
        gateway.register("rebuild_day", itinerary_service.rebuild_day)
        gateway.register("retrieve_guidance", retrieve_guidance)
        gateway.register("trigger_export", trigger_export)

        llm = LLMAdapter()
        _registry = AgentRegistry(session_manager, llm, gateway, observability)
    return _registry


def reset_registry() -> None:
    """Reset singleton — for tests."""
    global _registry
    _registry = None
