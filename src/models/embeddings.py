"""Embedding model wrapper with mock and real backends."""

from __future__ import annotations

import hashlib
from typing import Protocol

from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingModel(Protocol):
    """Protocol for embedding models."""

    @property
    def dimension(self) -> int: ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class MockEmbeddingModel:
    """Deterministic mock embedding model for testing.

    Generates consistent embeddings based on text content hash.
    """

    def __init__(self, dimension: int = 384) -> None:
        self._dimension = dimension
        logger.info("mock_embedding_model_loaded", dimension=dimension)

    @property
    def dimension(self) -> int:
        return self._dimension

    def _text_to_vector(self, text: str) -> list[float]:
        """Generate a deterministic vector from text."""
        h = hashlib.sha256(text.encode()).hexdigest()
        # Use hash bytes to generate floats between -1 and 1
        values: list[float] = []
        for i in range(self._dimension):
            byte_idx = i % len(h)
            val = (int(h[byte_idx], 16) / 15.0) * 2 - 1  # normalize to [-1, 1]
            values.append(val)
        # Normalize to unit length
        norm = sum(v * v for v in values) ** 0.5
        if norm > 0:
            values = [v / norm for v in values]
        return values

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
        return [self._text_to_vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        return self._text_to_vector(text)


class SentenceTransformerEmbeddingModel:
    """Real embedding model using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", dimension: int = 384) -> None:
        self._dimension = dimension
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name)
            logger.info("embedding_model_loaded", model=model_name)
        except ImportError as e:
            raise AppError(
                code=ErrorCode.MODEL_LOAD_FAILED,
                message="sentence-transformers not installed",
                cause=e,
            ) from e

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts using the sentence transformer."""
        try:
            embeddings = self._model.encode(texts, show_progress_bar=False)
            return [e.tolist() for e in embeddings]
        except Exception as e:
            raise AppError(
                code=ErrorCode.EMBEDDING_FAILED,
                message="Failed to compute embeddings",
                cause=e,
            ) from e

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        results = self.embed_texts([text])
        return results[0]


def create_embedding_model(backend: str, model_name: str, dimension: int) -> EmbeddingModel:
    """Factory to create the appropriate embedding model."""
    if backend == "mock":
        return MockEmbeddingModel(dimension=dimension)
    return SentenceTransformerEmbeddingModel(model_name=model_name, dimension=dimension)
