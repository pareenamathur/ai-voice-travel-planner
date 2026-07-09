"""Application configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    session_ttl_seconds: int = 3600

    # Phase 1 — OpenStreetMap / Overpass
    overpass_api_url: str = "https://overpass-api.de/api/interpreter"
    osm_cache_dir: Path = Path("data/cache/osm")


settings = Settings()
