"""Vector store abstraction over Qdrant."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """A single search result from the vector store."""

    chunk_id: str
    text: str
    score: float
    metadata: dict


class VectorStore:
    """Qdrant-backed vector store for document chunks.

    Supports two modes:
    - in_memory=True  → QdrantClient(":memory:") for tests and mock backend
    - in_memory=False → QdrantClient(url=url) for Docker Qdrant
    """

    def __init__(
        self,
        *,
        url: str = "",
        collection_name: str = "knowledge_hub",
        dimension: int = 1024,
        in_memory: bool = False,
    ) -> None:
        self._collection_name = collection_name
        self._dimension = dimension

        try:
            if in_memory:
                self._client = QdrantClient(location=":memory:")
            else:
                self._client = QdrantClient(url=url)

            self._ensure_collection()

            logger.info(
                "vector_store_initialized",
                collection=collection_name,
                dimension=dimension,
                in_memory=in_memory,
            )
        except AppError:
            raise
        except Exception as e:
            raise AppError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to initialize vector store: {e}",
                cause=e,
            ) from e

    def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        collections = self._client.get_collections().collections
        if not any(c.name == self._collection_name for c in collections):
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=self._dimension,
                    distance=Distance.COSINE,
                ),
            )

    @staticmethod
    def _translate_where(where: dict | None) -> Filter | None:
        """Translate ChromaDB-style where filters to Qdrant Filter objects.

        Supports:
        - None → None
        - {"key": "value"} → Filter(must=[FieldCondition(key, MatchValue(value))])
        - {"key": {"$in": [...]}} → Filter(must=[FieldCondition(key, MatchAny(any=[...]))])
        """
        if not where:
            return None

        conditions: list = []
        for key, value in where.items():
            if isinstance(value, dict) and "$in" in value:
                conditions.append(FieldCondition(key=key, match=MatchAny(any=value["$in"])))
            else:
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

        return Filter(must=conditions)

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        """Add documents with embeddings to the store."""
        points = []
        for i, chunk_id in enumerate(ids):
            payload = {"text": documents[i]}
            if metadatas and i < len(metadatas):
                payload.update(metadatas[i])

            # Use UUID5 from chunk_id for deterministic point IDs
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embeddings[i],
                    payload={**payload, "_chunk_id": chunk_id},
                )
            )

        self._client.upsert(
            collection_name=self._collection_name,
            points=points,
        )
        logger.info("vectors_added", count=len(ids))

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents using a query embedding."""
        query_filter = self._translate_where(where)

        try:
            results = self._client.query_points(
                collection_name=self._collection_name,
                query=query_embedding,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )
        except Exception as e:
            raise AppError(
                code=ErrorCode.RAG_RETRIEVAL_FAILED,
                message=f"Vector search failed: {e}",
                cause=e,
            ) from e

        search_results: list[SearchResult] = []
        for point in results.points:
            payload = point.payload or {}
            chunk_id = payload.pop("_chunk_id", str(point.id))
            text = payload.pop("text", "")
            search_results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    text=text,
                    score=point.score,
                    metadata=payload,
                )
            )

        return search_results

    def delete_by_source(self, source_id: str) -> None:
        """Delete all chunks belonging to a source."""
        try:
            self._client.delete(
                collection_name=self._collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="source_id", match=MatchValue(value=source_id))]
                ),
            )
            logger.info("vectors_deleted", source_id=source_id)
        except Exception as e:
            logger.warning("vector_delete_failed", source_id=source_id, error=str(e))

    def count(self) -> int:
        """Return total number of documents in the collection."""
        info = self._client.get_collection(self._collection_name)
        return info.points_count or 0

    # ---- Book-specific methods (Phase 2) ----

    def ensure_books_collection(self, collection_name: str, dimension: int) -> None:
        """Create a dedicated books collection with payload indexing if it doesn't exist."""
        collections = self._client.get_collections().collections
        if any(c.name == collection_name for c in collections):
            return

        from qdrant_client.models import (
            HnswConfigDiff,
            PayloadSchemaType,
        )

        self._client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=dimension,
                distance=Distance.COSINE,
            ),
            hnsw_config=HnswConfigDiff(m=16, ef_construct=200),
        )

        # Create payload indexes for filtered search
        for field_name in ("book_id", "author", "content_type"):
            self._client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        self._client.create_payload_index(
            collection_name=collection_name,
            field_name="chapter_number",
            field_schema=PayloadSchemaType.INTEGER,
        )

        logger.info(
            "books_collection_created",
            collection=collection_name,
            dimension=dimension,
        )

    def add_book_chunks(
        self,
        collection_name: str,
        book_id: str,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Store book chunks with rich metadata in the books collection."""
        points = []
        for i, chunk_id in enumerate(chunk_ids):
            payload = {"text": documents[i], "book_id": book_id, "_chunk_id": chunk_id}
            if i < len(metadatas):
                payload.update(metadatas[i])

            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))
            points.append(PointStruct(id=point_id, vector=embeddings[i], payload=payload))

        self._client.upsert(collection_name=collection_name, points=points)
        logger.info("book_vectors_added", book_id=book_id, count=len(chunk_ids))

    def delete_book_vectors(self, collection_name: str, book_id: str) -> None:
        """Delete all vectors for a specific book from the books collection."""
        try:
            collections = self._client.get_collections().collections
            if not any(c.name == collection_name for c in collections):
                return
            self._client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="book_id", match=MatchValue(value=book_id))]
                ),
            )
            logger.info("book_vectors_deleted", book_id=book_id)
        except Exception as e:
            logger.warning("book_vector_delete_failed", book_id=book_id, error=str(e))

    def search_books(
        self,
        collection_name: str,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        book_id: str | None = None,
        author: str | None = None,
        chapter_number: int | None = None,
    ) -> list[SearchResult]:
        """Search the books collection with optional filters."""
        conditions: list = []
        if book_id:
            conditions.append(FieldCondition(key="book_id", match=MatchValue(value=book_id)))
        if author:
            conditions.append(FieldCondition(key="author", match=MatchValue(value=author)))
        if chapter_number is not None:
            conditions.append(
                FieldCondition(key="chapter_number", match=MatchValue(value=chapter_number))
            )

        query_filter = Filter(must=conditions) if conditions else None

        try:
            results = self._client.query_points(
                collection_name=collection_name,
                query=query_embedding,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )
        except Exception as e:
            raise AppError(
                code=ErrorCode.RAG_RETRIEVAL_FAILED,
                message=f"Book vector search failed: {e}",
                cause=e,
            ) from e

        search_results: list[SearchResult] = []
        for point in results.points:
            payload = point.payload or {}
            chunk_id = payload.pop("_chunk_id", str(point.id))
            text = payload.pop("text", "")
            search_results.append(
                SearchResult(chunk_id=chunk_id, text=text, score=point.score, metadata=payload)
            )
        return search_results

    def count_collection(self, collection_name: str) -> int:
        """Return total number of documents in a specific collection."""
        try:
            info = self._client.get_collection(collection_name)
            return info.points_count or 0
        except Exception:
            return 0
