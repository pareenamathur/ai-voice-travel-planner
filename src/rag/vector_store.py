"""Vector store for RAG (Phase 2 Task 5).

Persists embedded chunks in a local ChromaDB collection. Indexing reads embedding
JSON from ``data/embeddings/`` and joins chunk text from ``data/chunks/``.
Similarity search is intentionally not implemented in this task.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from src.api.config import settings
from src.rag.embeddings import DEFAULT_CHUNKS_DIR, DEFAULT_EMBEDDINGS_DIR, load_embeddings_payload
from src.rag.models import Chunk, EmbeddingVector, RetrievalQuery, RetrievedChunk

DEFAULT_CHROMA_PERSIST_DIR = Path("data/rag/index/chroma")
DEFAULT_COLLECTION_NAME = "travel_guidance"
INDEX_MANIFEST_FILENAME = "index_manifest.json"


@dataclass(frozen=True, slots=True)
class VectorStoreConfig:
    """Vector store configuration."""

    backend: str
    collection: str
    persist_dir: Path = DEFAULT_CHROMA_PERSIST_DIR

    @classmethod
    def from_settings(cls) -> VectorStoreConfig:
        """Build config from application settings."""
        return cls(
            backend="chroma",
            collection=settings.chroma_collection_name,
            persist_dir=settings.chroma_persist_dir,
        )


class VectorStore(ABC):
    """Storage abstraction for embedded chunks."""

    @abstractmethod
    async def upsert(
        self,
        *,
        chunks: Iterable[Chunk],
        embeddings: Iterable[EmbeddingVector],
    ) -> None:
        """Insert or update chunks + their embeddings."""

    @abstractmethod
    async def query(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        """Return top-k most similar chunks for a query."""

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Return basic store status/diagnostics (for observability)."""


def embeddings_fingerprint(embeddings_path: Path) -> str:
    """Stable fingerprint of an embeddings JSON file."""
    return hashlib.sha256(embeddings_path.read_bytes()).hexdigest()


def manifest_path(persist_dir: Path) -> Path:
    return persist_dir / INDEX_MANIFEST_FILENAME


def load_index_manifest(persist_dir: Path) -> dict[str, Any]:
    path = manifest_path(persist_dir)
    if not path.exists():
        return {"files": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_index_manifest(persist_dir: Path, manifest: dict[str, Any]) -> None:
    path = manifest_path(persist_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _manifest_key(city: str, source: str) -> str:
    return f"{city}/{source}.json"


def _chunks_path_for_embeddings(
    embeddings_path: Path,
    *,
    chunks_dir: Path,
) -> Path:
    city = embeddings_path.parent.name
    source = embeddings_path.stem
    return chunks_dir / city / f"{source}.json"


def build_index_records(
    *,
    embeddings_payload: dict[str, Any],
    chunks_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Join embeddings with chunk text and normalize metadata for indexing."""
    chunk_text_by_id = {
        str(chunk["chunk_id"]): str(chunk["text"]) for chunk in chunks_payload["chunks"]
    }

    records: list[dict[str, Any]] = []
    for embedding_record in embeddings_payload["embeddings"]:
        chunk_id = str(embedding_record["chunk_id"])
        if chunk_id not in chunk_text_by_id:
            raise ValueError(f"Missing chunk text for chunk_id={chunk_id}")

        metadata = embedding_record.get("metadata") or {}
        records.append(
            {
                "id": chunk_id,
                "embedding": embedding_record["embedding"],
                "document": chunk_text_by_id[chunk_id],
                "metadata": {
                    "chunk_id": chunk_id,
                    "citation_id": str(embedding_record["citation_id"]),
                    "city": str(metadata.get("city", embeddings_payload.get("city", ""))),
                    "source": str(metadata.get("source", embeddings_payload.get("source", ""))),
                    "section": str(metadata.get("section", "")),
                    "chunk_index": int(metadata.get("chunk_index", 0)),
                    "document_id": str(
                        metadata.get("document_id", embeddings_payload.get("document_id", ""))
                    ),
                    "source_url": str(metadata.get("source_url", "")),
                },
            }
        )

    return records


class ChromaVectorStore(VectorStore):
    """ChromaDB-backed vector store (replaceable via VectorStore interface)."""

    def __init__(
        self,
        *,
        config: VectorStoreConfig | None = None,
        client: ClientAPI | None = None,
        collection: Collection | None = None,
    ) -> None:
        self._config = config or VectorStoreConfig.from_settings()
        self._client = client or chromadb.PersistentClient(path=str(self._config.persist_dir))
        self._collection = collection or self._client.get_or_create_collection(
            name=self._config.collection,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def collection(self) -> Collection:
        return self._collection

    @property
    def config(self) -> VectorStoreConfig:
        return self._config

    def _delete_ids(self, ids: list[str]) -> None:
        if not ids:
            return
        self._collection.delete(ids=ids)

    def _upsert_records(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        self._collection.upsert(
            ids=[record["id"] for record in records],
            embeddings=[record["embedding"] for record in records],
            documents=[record["document"] for record in records],
            metadatas=[record["metadata"] for record in records],
        )

    async def upsert(
        self,
        *,
        chunks: Iterable[Chunk],
        embeddings: Iterable[EmbeddingVector],
    ) -> None:
        chunk_list = list(chunks)
        embedding_list = list(embeddings)
        if len(chunk_list) != len(embedding_list):
            raise ValueError("chunks and embeddings must have the same length")

        records: list[dict[str, Any]] = []
        for chunk, embedding in zip(chunk_list, embedding_list, strict=True):
            metadata = chunk.metadata or {}
            records.append(
                {
                    "id": chunk.chunk_id,
                    "embedding": embedding.vector,
                    "document": chunk.text,
                    "metadata": {
                        "chunk_id": chunk.chunk_id,
                        "citation_id": str(chunk.citation_id or ""),
                        "city": str(metadata.get("city", "")),
                        "source": str(metadata.get("source", "")),
                        "section": str(chunk.section or ""),
                        "chunk_index": int(metadata.get("chunk_index", 0)),
                        "document_id": str(metadata.get("document_id", chunk.doc_id)),
                        "source_url": str(chunk.source_url or metadata.get("source_url", "")),
                    },
                }
            )

        self._upsert_records(records)

    async def query(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        raise NotImplementedError(
            "Similarity search is not implemented in Phase 2 Task 5 (vector indexing only)."
        )

    async def health(self) -> dict[str, Any]:
        return {
            "backend": self._config.backend,
            "collection": self._config.collection,
            "persist_dir": str(self._config.persist_dir),
            "count": self._collection.count(),
        }

    def rebuild_collection(self) -> None:
        """Delete and recreate the Chroma collection (used by force_refresh)."""
        self._client.delete_collection(name=self._config.collection)
        self._collection = self._client.get_or_create_collection(name=self._config.collection)
        save_index_manifest(self._config.persist_dir, {"files": {}})

    async def index_embeddings_file(
        self,
        embeddings_path: Path,
        *,
        chunks_dir: Path = DEFAULT_CHUNKS_DIR,
        force_refresh: bool = False,
    ) -> bool:
        """Index one embeddings JSON file. Returns True when writes occurred."""
        embeddings_payload = load_embeddings_payload(embeddings_path)
        city = str(embeddings_payload["city"])
        source = str(embeddings_payload["source"])
        key = _manifest_key(city, source)
        fingerprint = embeddings_fingerprint(embeddings_path)

        manifest = load_index_manifest(self._config.persist_dir)
        files = manifest.setdefault("files", {})
        existing = files.get(key)

        if (
            not force_refresh
            and existing is not None
            and existing.get("fingerprint") == fingerprint
        ):
            return False

        chunks_path = _chunks_path_for_embeddings(embeddings_path, chunks_dir=chunks_dir)
        if not chunks_path.exists():
            raise FileNotFoundError(f"Missing chunks file for embeddings: {chunks_path}")

        chunks_payload = json.loads(chunks_path.read_text(encoding="utf-8"))
        records = build_index_records(
            embeddings_payload=embeddings_payload,
            chunks_payload=chunks_payload,
        )
        chunk_ids = [record["id"] for record in records]

        if existing and existing.get("chunk_ids"):
            self._delete_ids(list(existing["chunk_ids"]))

        self._upsert_records(records)
        files[key] = {"fingerprint": fingerprint, "chunk_ids": chunk_ids}
        save_index_manifest(self._config.persist_dir, manifest)
        return True

    async def index_city(
        self,
        city: str,
        *,
        embeddings_dir: Path = DEFAULT_EMBEDDINGS_DIR,
        chunks_dir: Path = DEFAULT_CHUNKS_DIR,
        force_refresh: bool = False,
    ) -> list[Path]:
        """Index all embedding files for a city. Returns paths that were written."""
        city_dir = embeddings_dir / city
        if not city_dir.is_dir():
            return []

        if force_refresh:
            self.rebuild_collection()

        written: list[Path] = []
        for embeddings_path in sorted(city_dir.glob("*.json")):
            indexed = await self.index_embeddings_file(
                embeddings_path,
                chunks_dir=chunks_dir,
                force_refresh=False,
            )
            if indexed:
                written.append(embeddings_path)

        return written


async def index_embeddings_file(
    embeddings_path: Path,
    *,
    store: VectorStore | None = None,
    chunks_dir: Path = DEFAULT_CHUNKS_DIR,
    force_refresh: bool = False,
) -> bool:
    """Convenience entry point for indexing one embeddings file."""
    if not isinstance(store, ChromaVectorStore):
        store = ChromaVectorStore()
    return await store.index_embeddings_file(
        embeddings_path,
        chunks_dir=chunks_dir,
        force_refresh=force_refresh,
    )


async def index_city(
    city: str,
    *,
    store: VectorStore | None = None,
    embeddings_dir: Path = DEFAULT_EMBEDDINGS_DIR,
    chunks_dir: Path = DEFAULT_CHUNKS_DIR,
    force_refresh: bool = False,
) -> list[Path]:
    """Convenience entry point for indexing all embeddings for a city."""
    if not isinstance(store, ChromaVectorStore):
        store = ChromaVectorStore()
    return await store.index_city(
        city,
        embeddings_dir=embeddings_dir,
        chunks_dir=chunks_dir,
        force_refresh=force_refresh,
    )
