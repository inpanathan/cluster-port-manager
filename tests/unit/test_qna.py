"""Unit tests for the Q&A generation service."""

from __future__ import annotations

import pytest

from src.catalog.service import CatalogService
from src.data.ingestion import IngestionPipeline
from src.features.qna import QnAService
from src.models.embeddings import MockEmbeddingModel
from src.models.llm import MockLLMClient
from src.utils.cache import InMemoryCacheStore
from src.utils.errors import AppError
from src.utils.vector_store import VectorStore


def _create_service(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    cache_store: InMemoryCacheStore,
) -> QnAService:
    return QnAService(
        llm_client=llm_client,
        vector_store=vector_store,
        embedding_model=embedding_model,
        catalog=catalog_service,
        cache=cache_store,
    )


def test_generate_with_topic(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    ingestion_pipeline.ingest_text("Machine learning uses algorithms to learn.", title="ML")
    service = _create_service(
        llm_client, vector_store, embedding_model, catalog_service, cache_store
    )
    qa_set = service.generate(topic="machine learning", count=5)
    assert qa_set.id
    assert qa_set.topic == "machine learning"


def test_generate_with_sources(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    result = ingestion_pipeline.ingest_text("Python is great for scripting.", title="Python")
    service = _create_service(
        llm_client, vector_store, embedding_model, catalog_service, cache_store
    )
    qa_set = service.generate(source_ids=[result.source_id], count=3)
    assert qa_set.id


def test_requires_topic_or_sources(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    cache_store: InMemoryCacheStore,
) -> None:
    service = _create_service(
        llm_client, vector_store, embedding_model, catalog_service, cache_store
    )
    with pytest.raises(AppError) as exc_info:
        service.generate()
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_get_from_cache(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    ingestion_pipeline.ingest_text("Caching test content for Q&A.", title="Cache QA")
    service = _create_service(
        llm_client, vector_store, embedding_model, catalog_service, cache_store
    )
    qa_set = service.generate(topic="caching", count=3)

    loaded = service.get_set(qa_set.id)
    assert loaded is not None
    assert loaded.id == qa_set.id


def test_export_json(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    ingestion_pipeline.ingest_text("Export JSON test content.", title="Export JSON")
    service = _create_service(
        llm_client, vector_store, embedding_model, catalog_service, cache_store
    )
    qa_set = service.generate(topic="export", count=3)

    exported = service.export_set(qa_set.id, fmt="json")
    assert '"topic"' in exported
    assert '"pairs"' in exported


def test_export_markdown(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    ingestion_pipeline.ingest_text("Export Markdown test content.", title="Export MD")
    service = _create_service(
        llm_client, vector_store, embedding_model, catalog_service, cache_store
    )
    qa_set = service.generate(topic="export", count=3)

    exported = service.export_set(qa_set.id, fmt="markdown")
    assert "# Q&A:" in exported
