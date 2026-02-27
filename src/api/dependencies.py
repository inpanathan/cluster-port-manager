"""Dependency injection container for FastAPI.

Initializes all service instances at startup using settings and factories.
Provides FastAPI Depends() accessor functions for route handlers.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.catalog.repository import CatalogRepository
from src.catalog.service import CatalogService
from src.data.file_store import FileStore
from src.data.ingestion import IngestionPipeline
from src.features.chat import ChatService
from src.features.interview import InterviewService
from src.features.qna import QnAService
from src.features.summarization import SummarizationService
from src.models.embeddings import create_embedding_model
from src.models.llm import create_llm_client
from src.pipelines.rag import RAGPipeline
from src.utils.cache import CacheStore, create_cache_store
from src.utils.config import settings
from src.utils.logger import get_logger
from src.utils.vector_store import VectorStore

logger = get_logger(__name__)


@dataclass
class ServiceContainer:
    """Holds all initialized service instances."""

    catalog: CatalogService
    file_store: FileStore
    vector_store: VectorStore
    ingestion: IngestionPipeline
    rag: RAGPipeline
    chat: ChatService
    interview: InterviewService
    qna: QnAService
    summarization: SummarizationService
    cache: CacheStore


_container: ServiceContainer | None = None


def init_services() -> ServiceContainer:
    """Create and wire all services from settings."""
    global _container  # noqa: PLW0603

    # Core infrastructure
    catalog_repo = CatalogRepository(settings.catalog.database_path)
    catalog = CatalogService(catalog_repo)
    file_store = FileStore(settings.file_store.base_directory)
    vector_store = VectorStore(
        persist_directory=settings.vector_store.persist_directory,
        collection_name=settings.vector_store.collection_name,
    )

    # Models
    embedding_model = create_embedding_model(
        backend=settings.model_backend,
        model_name=settings.embedding.model_name,
        dimension=settings.embedding.dimension,
    )
    llm_client = create_llm_client(
        backend=settings.model_backend,
        api_key=settings.llm.api_key,
        model_id=settings.llm.model_id,
        temperature=settings.llm.temperature,
        timeout=settings.llm.timeout_seconds,
    )

    # Cache
    cache = create_cache_store(
        backend=settings.model_backend,
        redis_url=settings.redis.connection_url,
        default_ttl_days=settings.redis.default_ttl_days,
    )

    # Pipelines
    ingestion = IngestionPipeline(
        catalog=catalog,
        file_store=file_store,
        embedding_model=embedding_model,
        vector_store=vector_store,
        chunk_size=settings.chunking.chunk_size,
        chunk_overlap=settings.chunking.chunk_overlap,
    )
    rag = RAGPipeline(
        embedding_model=embedding_model,
        vector_store=vector_store,
        llm_client=llm_client,
        catalog=catalog,
        top_k=settings.rag.top_k,
        similarity_threshold=settings.rag.similarity_threshold,
    )

    # Features
    chat = ChatService(rag_pipeline=rag, cache=cache)
    interview = InterviewService(
        llm_client=llm_client,
        vector_store=vector_store,
        embedding_model=embedding_model,
        catalog=catalog,
        cache=cache,
    )
    qna = QnAService(
        llm_client=llm_client,
        vector_store=vector_store,
        embedding_model=embedding_model,
        catalog=catalog,
        cache=cache,
    )
    summarization = SummarizationService(
        llm_client=llm_client,
        vector_store=vector_store,
        embedding_model=embedding_model,
        catalog=catalog,
    )

    _container = ServiceContainer(
        catalog=catalog,
        file_store=file_store,
        vector_store=vector_store,
        ingestion=ingestion,
        rag=rag,
        chat=chat,
        interview=interview,
        qna=qna,
        summarization=summarization,
        cache=cache,
    )

    logger.info("services_initialized", backend=settings.model_backend)
    return _container


def shutdown_services() -> None:
    """Cleanup on shutdown."""
    global _container  # noqa: PLW0603
    _container = None
    logger.info("services_shutdown")


def get_container() -> ServiceContainer:
    """Get the service container. Raises if not initialized."""
    if _container is None:
        msg = "Services not initialized — call init_services() first"
        raise RuntimeError(msg)
    return _container


def get_ingestion() -> IngestionPipeline:
    return get_container().ingestion


def get_catalog() -> CatalogService:
    return get_container().catalog


def get_file_store() -> FileStore:
    return get_container().file_store


def get_chat() -> ChatService:
    return get_container().chat


def get_interview() -> InterviewService:
    return get_container().interview


def get_qna() -> QnAService:
    return get_container().qna


def get_summarization() -> SummarizationService:
    return get_container().summarization


def get_vector_store() -> VectorStore:
    return get_container().vector_store
