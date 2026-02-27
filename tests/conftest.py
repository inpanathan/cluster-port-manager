"""Root test configuration.

Overrides environment variables before any app imports (REQ-TST-051).
Provides shared fixtures for all test categories.
"""

from __future__ import annotations

import os
import tempfile

# Override environment BEFORE any app imports
os.environ["APP_ENV"] = "test"
os.environ["MODEL_BACKEND"] = "mock"
os.environ["APP_DEBUG"] = "true"
os.environ["USE_MOCKS"] = "true"

from collections.abc import Iterator
from pathlib import Path

import pytest

from src.catalog.repository import CatalogRepository
from src.catalog.service import CatalogService
from src.data.file_store import FileStore
from src.data.ingestion import IngestionPipeline
from src.models.embeddings import MockEmbeddingModel
from src.models.llm import MockLLMClient
from src.pipelines.rag import RAGPipeline
from src.utils.cache import InMemoryCacheStore
from src.utils.vector_store import VectorStore


@pytest.fixture()
def tmp_dir() -> Iterator[Path]:
    """Provide a temporary directory cleaned up after the test."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture()
def cache_store() -> InMemoryCacheStore:
    """Provide an in-memory cache store for testing."""
    return InMemoryCacheStore()


@pytest.fixture()
def embedding_model() -> MockEmbeddingModel:
    """Provide a mock embedding model."""
    return MockEmbeddingModel(dimension=384)


@pytest.fixture()
def llm_client() -> MockLLMClient:
    """Provide a mock LLM client."""
    return MockLLMClient()


@pytest.fixture()
def catalog_repo(tmp_dir: Path) -> CatalogRepository:
    """Provide a catalog repository with a temp SQLite database."""
    db_path = str(tmp_dir / "test_catalog.db")
    return CatalogRepository(db_path)


@pytest.fixture()
def catalog_service(catalog_repo: CatalogRepository) -> CatalogService:
    """Provide a catalog service."""
    return CatalogService(catalog_repo)


@pytest.fixture()
def file_store(tmp_dir: Path) -> FileStore:
    """Provide a file store using a temp directory."""
    return FileStore(str(tmp_dir / "originals"))


@pytest.fixture()
def vector_store(tmp_dir: Path) -> VectorStore:
    """Provide a vector store using a temp directory."""
    return VectorStore(
        persist_directory=str(tmp_dir / "vectorstore"),
        collection_name="test_collection",
    )


@pytest.fixture()
def ingestion_pipeline(
    catalog_service: CatalogService,
    file_store: FileStore,
    embedding_model: MockEmbeddingModel,
    vector_store: VectorStore,
) -> IngestionPipeline:
    """Provide an ingestion pipeline with all mock dependencies."""
    return IngestionPipeline(
        catalog=catalog_service,
        file_store=file_store,
        embedding_model=embedding_model,
        vector_store=vector_store,
    )


@pytest.fixture()
def rag_pipeline(
    embedding_model: MockEmbeddingModel,
    vector_store: VectorStore,
    llm_client: MockLLMClient,
    catalog_service: CatalogService,
) -> RAGPipeline:
    """Provide a RAG pipeline with all mock dependencies."""
    return RAGPipeline(
        embedding_model=embedding_model,
        vector_store=vector_store,
        llm_client=llm_client,
        catalog=catalog_service,
    )
