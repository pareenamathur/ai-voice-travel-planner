"""Embeddings generation for RAG (Phase 2 Task 4).

Reads chunk JSON from ``data/chunks/``, generates vectors via a pluggable
provider, and persists results under ``data/embeddings/<city>/<source>.json``.
"""

from src.rag.embeddings.config import EmbeddingsConfig
from src.rag.embeddings.factory import EmbeddingsProviderFactory
from src.rag.embeddings.pipeline import (
    DEFAULT_CHUNKS_DIR,
    DEFAULT_EMBEDDINGS_DIR,
    chunk_metadata_reference,
    chunks_fingerprint,
    embedding_record_to_dict,
    embeddings_file_path,
    generate_embeddings_for_chunks_file,
    generate_embeddings_for_city,
    load_chunks_payload,
    load_embeddings_payload,
    should_skip_embedding,
)
from src.rag.embeddings.providers.base import EmbeddingsProvider
from src.rag.embeddings.providers.google import GoogleEmbeddingsProvider
from src.rag.embeddings.providers.openai import OpenAIEmbeddingsProvider

# Backward-compatible alias for earlier Phase 2 naming.
OpenAICompatibleEmbeddingsProvider = OpenAIEmbeddingsProvider

__all__ = [
    "DEFAULT_CHUNKS_DIR",
    "DEFAULT_EMBEDDINGS_DIR",
    "EmbeddingsConfig",
    "EmbeddingsProvider",
    "EmbeddingsProviderFactory",
    "GoogleEmbeddingsProvider",
    "OpenAIEmbeddingsProvider",
    "OpenAICompatibleEmbeddingsProvider",
    "chunk_metadata_reference",
    "chunks_fingerprint",
    "embedding_record_to_dict",
    "embeddings_file_path",
    "generate_embeddings_for_chunks_file",
    "generate_embeddings_for_city",
    "load_chunks_payload",
    "load_embeddings_payload",
    "should_skip_embedding",
]
