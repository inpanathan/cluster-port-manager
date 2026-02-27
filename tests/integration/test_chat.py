"""Integration tests for the chat API endpoints."""

from __future__ import annotations

import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Create a lifespan-aware test client with isolated data directories."""
    from main import create_app
    from src.utils.config import settings

    with tempfile.TemporaryDirectory() as tmp:
        settings.catalog.database_path = f"{tmp}/catalog.db"
        settings.vector_store.persist_directory = f"{tmp}/vectorstore"
        settings.file_store.base_directory = f"{tmp}/originals"

        app = create_app()
        with TestClient(app) as c:
            yield c


def _ingest_content(client: TestClient) -> str:
    """Ingest a text source and return the source_id."""
    response = client.post(
        "/api/v1/sources/text",
        json={
            "content": "Python is a versatile programming language for web development.",
            "title": "Python",
        },
    )
    return response.json()["source_id"]


def test_chat_no_sources(client: TestClient) -> None:
    """Chat with no indexed sources should return a no-context response."""
    response = client.post(
        "/api/v1/chat",
        json={"message": "What is Python?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"]
    assert data["answer"]


def test_chat_after_ingestion(client: TestClient) -> None:
    _ingest_content(client)
    response = client.post(
        "/api/v1/chat",
        json={"message": "Tell me about Python."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answer"]
    assert data["session_id"]


def test_chat_multi_turn(client: TestClient) -> None:
    _ingest_content(client)
    r1 = client.post(
        "/api/v1/chat",
        json={"message": "What is Python?"},
    )
    session_id = r1.json()["session_id"]

    r2 = client.post(
        "/api/v1/chat",
        json={"message": "Tell me more.", "session_id": session_id},
    )
    assert r2.status_code == 200
    assert r2.json()["session_id"] == session_id


def test_list_sessions(client: TestClient) -> None:
    _ingest_content(client)
    client.post("/api/v1/chat", json={"message": "Hi"})
    client.post("/api/v1/chat", json={"message": "Hello"})
    response = client.get("/api/v1/chat/sessions")
    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) >= 2


def test_get_session_detail(client: TestClient) -> None:
    _ingest_content(client)
    r1 = client.post("/api/v1/chat", json={"message": "What is Python?"})
    session_id = r1.json()["session_id"]

    response = client.get(f"/api/v1/chat/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == session_id
    assert len(data["messages"]) == 2  # user + assistant


def test_session_not_found_404(client: TestClient) -> None:
    response = client.get("/api/v1/chat/sessions/nonexistent")
    assert response.status_code == 404
