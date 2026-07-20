"""Application configuration."""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_OVERPASS_MIRRORS = (
    "https://lz4.overpass-api.de/api/interpreter,"
    "https://overpass.kumi.systems/api/interpreter"
)
DEFAULT_POI_CITY_CACHE_TTL_SECONDS = 24 * 3600


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Chat LLM (agent generation — OpenAI-compatible API)
    chat_provider: str = "openai"
    chat_api_key: str = ""
    chat_model: str = "gpt-4o-mini"
    chat_base_url: str = ""

    # Embeddings (RAG indexing/retrieval — OpenAI-compatible API)
    embedding_provider: str = "openai"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_base_url: str = ""

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    session_ttl_seconds: int = 3600

    # Phase 1 — OpenStreetMap / Overpass (prefer OVERPASS_URL; OVERPASS_API_URL still accepted)
    overpass_api_url: str = Field(
        default=DEFAULT_OVERPASS_URL,
        validation_alias=AliasChoices("OVERPASS_URL", "OVERPASS_API_URL", "overpass_api_url"),
    )
    overpass_mirrors: str = Field(
        default=DEFAULT_OVERPASS_MIRRORS,
        validation_alias=AliasChoices("OVERPASS_MIRRORS", "overpass_mirrors"),
        description="Comma-separated Overpass mirror interpreter URLs tried after the primary.",
    )
    osm_cache_dir: Path = Path("data/cache/osm")
    poi_city_cache_ttl_seconds: int = Field(
        default=DEFAULT_POI_CITY_CACHE_TTL_SECONDS,
        validation_alias=AliasChoices(
            "POI_CITY_CACHE_TTL_SECONDS",
            "poi_city_cache_ttl_seconds",
        ),
    )

    # Phase 2 Task 5 — Chroma vector store
    chroma_persist_dir: Path = Path("data/rag/index/chroma")
    chroma_collection_name: str = "travel_guidance"

    def overpass_urls(self) -> list[str]:
        """Primary Overpass URL plus configured mirrors (deduplicated, order preserved)."""
        urls: list[str] = []
        for candidate in [self.overpass_api_url, *self.overpass_mirrors.split(",")]:
            url = candidate.strip()
            if url and url not in urls:
                urls.append(url)
        return urls or [DEFAULT_OVERPASS_URL]


settings = Settings()
