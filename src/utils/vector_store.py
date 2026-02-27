"""Vector store abstraction over ChromaDB."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    """ChromaDB-backed vector store for document chunks."""

    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "knowledge_hub",
    ) -> None:
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        try:
            import chromadb

            self._client = chromadb.PersistentClient(path=persist_directory)
            self._collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                "vector_store_initialized",
                path=persist_directory,
                collection=collection_name,
            )
        except Exception as e:
            raise AppError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to initialize vector store: {e}",
                cause=e,
            ) from e

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        """Add documents with embeddings to the store."""
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info("vectors_added", count=len(ids))

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents using a query embedding."""
        kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        try:
            results = self._collection.query(**kwargs)
        except Exception as e:
            raise AppError(
                code=ErrorCode.RAG_RETRIEVAL_FAILED,
                message=f"Vector search failed: {e}",
                cause=e,
            ) from e

        search_results: list[SearchResult] = []
        if results and results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0.0
                score = 1.0 - distance  # cosine distance to similarity
                search_results.append(
                    SearchResult(
                        chunk_id=chunk_id,
                        text=results["documents"][0][i] if results["documents"] else "",
                        score=score,
                        metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    )
                )

        return search_results

    def delete_by_source(self, source_id: str) -> None:
        """Delete all chunks belonging to a source."""
        try:
            self._collection.delete(where={"source_id": source_id})
            logger.info("vectors_deleted", source_id=source_id)
        except Exception as e:
            logger.warning("vector_delete_failed", source_id=source_id, error=str(e))

    def count(self) -> int:
        """Return total number of documents in the collection."""
        return self._collection.count()
