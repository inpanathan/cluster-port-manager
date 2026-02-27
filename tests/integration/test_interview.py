"""Integration tests for the interview preparation API endpoints."""

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


def _ingest_and_start(client: TestClient) -> str:
    """Ingest content and start an interview session, return session_id."""
    client.post(
        "/api/v1/sources/text",
        json={
            "content": "Python is used for backend development, scripting, and data analysis.",
            "title": "Python",
        },
    )
    response = client.post(
        "/api/v1/interview/start",
        json={"topic": "Python", "question_count": 2},
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_start_interview(client: TestClient) -> None:
    session_id = _ingest_and_start(client)
    assert session_id


def test_submit_answer(client: TestClient) -> None:
    session_id = _ingest_and_start(client)
    response = client.post(
        f"/api/v1/interview/{session_id}/answer",
        json={"answer": "Python is great for web development."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["question"]["answered"]


def test_full_interview_flow(client: TestClient) -> None:
    session_id = _ingest_and_start(client)

    # Answer all questions
    for _ in range(2):
        r = client.post(
            f"/api/v1/interview/{session_id}/answer",
            json={"answer": "My answer."},
        )
        assert r.status_code == 200

    # Get summary
    response = client.get(f"/api/v1/interview/{session_id}/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["completed"]
    assert data["overall_feedback"]


def test_not_found_404(client: TestClient) -> None:
    response = client.get("/api/v1/interview/nonexistent/summary")
    assert response.status_code == 404
