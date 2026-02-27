"""Unit tests for the interview preparation service."""

from __future__ import annotations

import pytest

from src.catalog.service import CatalogService
from src.data.ingestion import IngestionPipeline
from src.features.interview import InterviewService
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
) -> InterviewService:
    return InterviewService(
        llm_client=llm_client,
        vector_store=vector_store,
        embedding_model=embedding_model,
        catalog=catalog_service,
        cache=cache_store,
    )


def test_start_generates_questions(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    ingestion_pipeline.ingest_text("Python is used for web development.", title="Python")
    service = _create_service(
        llm_client, vector_store, embedding_model, catalog_service, cache_store
    )
    session = service.start_session("Python", question_count=5)
    assert session.id
    assert len(session.questions) > 0


def test_submit_answer_returns_feedback(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    ingestion_pipeline.ingest_text("FastAPI is fast and modern.", title="FastAPI")
    service = _create_service(
        llm_client, vector_store, embedding_model, catalog_service, cache_store
    )
    session = service.start_session("FastAPI", question_count=3)
    question = service.submit_answer(session.id, "FastAPI is great for building APIs.")
    assert question.answered
    assert question.feedback


def test_answer_advances_index(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    ingestion_pipeline.ingest_text("Docker containers are lightweight.", title="Docker")
    service = _create_service(
        llm_client, vector_store, embedding_model, catalog_service, cache_store
    )
    session = service.start_session("Docker", question_count=3)
    service.submit_answer(session.id, "First answer.")

    reloaded = service.get_session(session.id)
    assert reloaded is not None
    assert reloaded.current_index == 1


def test_session_completes(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    ingestion_pipeline.ingest_text("Testing is important for quality.", title="Testing")
    service = _create_service(
        llm_client, vector_store, embedding_model, catalog_service, cache_store
    )
    session = service.start_session("Testing", question_count=2)
    for _ in range(len(session.questions)):
        service.submit_answer(session.id, "My answer.")

    final = service.get_session(session.id)
    assert final is not None
    assert final.completed


def test_submit_to_completed_raises(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    ingestion_pipeline.ingest_text("Kubernetes orchestrates containers.", title="K8s")
    service = _create_service(
        llm_client, vector_store, embedding_model, catalog_service, cache_store
    )
    session = service.start_session("Kubernetes", question_count=1)
    service.submit_answer(session.id, "My answer.")

    with pytest.raises(AppError) as exc_info:
        service.submit_answer(session.id, "Extra answer.")
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_get_summary(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    ingestion_pipeline.ingest_text("CI/CD automates deployment.", title="CI/CD")
    service = _create_service(
        llm_client, vector_store, embedding_model, catalog_service, cache_store
    )
    session = service.start_session("CI/CD", question_count=2)
    for _ in range(len(session.questions)):
        service.submit_answer(session.id, "My answer.")

    summary = service.get_session_summary(session.id)
    assert summary.completed
    assert summary.overall_feedback


def test_session_not_found(
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
        service.submit_answer("nonexistent", "answer")
    assert exc_info.value.code == "SESSION_NOT_FOUND"
