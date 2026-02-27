"""Unit tests for the summarization service."""

from __future__ import annotations

import pytest

from src.catalog.service import CatalogService
from src.data.ingestion import IngestionPipeline
from src.features.summarization import SummarizationService, SummaryMode
from src.models.embeddings import MockEmbeddingModel
from src.models.llm import MockLLMClient
from src.utils.errors import AppError
from src.utils.vector_store import VectorStore


def _create_service(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
) -> SummarizationService:
    return SummarizationService(
        llm_client=llm_client,
        vector_store=vector_store,
        embedding_model=embedding_model,
        catalog=catalog_service,
    )


def test_summarize_sources_short(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    result = ingestion_pipeline.ingest_text("Machine learning is a subset of AI.", title="ML Intro")
    service = _create_service(llm_client, vector_store, embedding_model, catalog_service)
    summary = service.summarize_sources([result.source_id], mode=SummaryMode.SHORT)
    assert summary.summary
    assert summary.mode == SummaryMode.SHORT


def test_summarize_sources_detailed(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    result = ingestion_pipeline.ingest_text("Deep learning uses neural networks.", title="DL")
    service = _create_service(llm_client, vector_store, embedding_model, catalog_service)
    summary = service.summarize_sources([result.source_id], mode=SummaryMode.DETAILED)
    assert summary.summary
    assert summary.mode == SummaryMode.DETAILED


def test_summarize_topic(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
    ingestion_pipeline: IngestionPipeline,
) -> None:
    ingestion_pipeline.ingest_text("Transformers are used in NLP tasks.", title="Transformers")
    service = _create_service(llm_client, vector_store, embedding_model, catalog_service)
    summary = service.summarize_topic("transformers")
    assert summary.summary


def test_no_params_raises(
    llm_client: MockLLMClient,
    vector_store: VectorStore,
    embedding_model: MockEmbeddingModel,
    catalog_service: CatalogService,
) -> None:
    service = _create_service(llm_client, vector_store, embedding_model, catalog_service)
    with pytest.raises(AppError) as exc_info:
        service.summarize_sources([])
    assert exc_info.value.code == "VALIDATION_ERROR"
