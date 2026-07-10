"""Application configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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

    # Phase 1 — OpenStreetMap / Overpass
    overpass_api_url: str = "https://overpass-api.de/api/interpreter"
    osm_cache_dir: Path = Path("data/cache/osm")

    # Phase 2 Task 5 — Chroma vector store
    chroma_persist_dir: Path = Path("data/rag/index/chroma")
    chroma_collection_name: str = "travel_guidance"


settings = Settings()
