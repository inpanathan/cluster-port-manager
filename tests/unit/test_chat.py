"""Unit tests for the chat service."""

from __future__ import annotations

from src.features.chat import ChatService
from src.pipelines.rag import RAGPipeline
from src.utils.cache import InMemoryCacheStore


def test_create_session(
    rag_pipeline: RAGPipeline,
    cache_store: InMemoryCacheStore,
) -> None:
    chat = ChatService(rag_pipeline=rag_pipeline, cache=cache_store)
    session = chat.create_session()
    assert session.id
    assert session.messages == []


def test_send_message(
    rag_pipeline: RAGPipeline,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,  # noqa: F821
) -> None:
    # Ingest some content first so RAG has context

    ingestion_pipeline.ingest_text("Python is a programming language.", title="Python Intro")

    chat = ChatService(rag_pipeline=rag_pipeline, cache=cache_store)
    session_id, msg = chat.send_message(None, "What is Python?")
    assert session_id
    assert msg.role == "assistant"
    assert msg.content


def test_session_from_cache(
    rag_pipeline: RAGPipeline,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,  # noqa: F821
) -> None:

    ingestion_pipeline.ingest_text("Test content for session caching.", title="Cache Test")

    chat = ChatService(rag_pipeline=rag_pipeline, cache=cache_store)
    session = chat.create_session()
    session_id = session.id

    # Retrieve from cache
    loaded = chat.get_session(session_id)
    assert loaded is not None
    assert loaded.id == session_id


def test_list_sessions(
    rag_pipeline: RAGPipeline,
    cache_store: InMemoryCacheStore,
) -> None:
    chat = ChatService(rag_pipeline=rag_pipeline, cache=cache_store)
    chat.create_session()
    chat.create_session()
    sessions = chat.list_sessions()
    assert len(sessions) == 2


def test_session_not_found(
    rag_pipeline: RAGPipeline,
    cache_store: InMemoryCacheStore,
) -> None:
    chat = ChatService(rag_pipeline=rag_pipeline, cache=cache_store)
    assert chat.get_session("nonexistent") is None


def test_multi_turn(
    rag_pipeline: RAGPipeline,
    cache_store: InMemoryCacheStore,
    ingestion_pipeline: IngestionPipeline,  # noqa: F821
) -> None:

    ingestion_pipeline.ingest_text("FastAPI is a modern web framework.", title="FastAPI")

    chat = ChatService(rag_pipeline=rag_pipeline, cache=cache_store)
    sid, msg1 = chat.send_message(None, "What is FastAPI?")
    assert msg1.content

    _, msg2 = chat.send_message(sid, "Tell me more about it.")
    assert msg2.content

    session = chat.get_session(sid)
    assert session is not None
    assert len(session.messages) == 4  # 2 user + 2 assistant
