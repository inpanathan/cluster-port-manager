"""Integration tests for the Q&A generation API endpoints."""

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


def _ingest(client: TestClient) -> str:
    r = client.post(
        "/api/v1/sources/text",
        json={"content": "Machine learning algorithms learn patterns from data.", "title": "ML"},
    )
    return r.json()["source_id"]


def test_generate_returns_pairs(client: TestClient) -> None:
    _ingest(client)
    response = client.post(
        "/api/v1/qna/generate",
        json={"topic": "machine learning", "count": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"]
    assert data["topic"] == "machine learning"


def test_get_set(client: TestClient) -> None:
    _ingest(client)
    r = client.post(
        "/api/v1/qna/generate",
        json={"topic": "machine learning", "count": 3},
    )
    set_id = r.json()["id"]
    response = client.get(f"/api/v1/qna/{set_id}")
    assert response.status_code == 200
    assert response.json()["id"] == set_id


def test_export_json(client: TestClient) -> None:
    _ingest(client)
    r = client.post(
        "/api/v1/qna/generate",
        json={"topic": "machine learning", "count": 3},
    )
    set_id = r.json()["id"]
    response = client.post(f"/api/v1/qna/{set_id}/export", json={"format": "json"})
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")


def test_export_markdown(client: TestClient) -> None:
    _ingest(client)
    r = client.post(
        "/api/v1/qna/generate",
        json={"topic": "machine learning", "count": 3},
    )
    set_id = r.json()["id"]
    response = client.post(f"/api/v1/qna/{set_id}/export", json={"format": "markdown"})
    assert response.status_code == 200
    assert "text/markdown" in response.headers.get("content-type", "")


def test_nonexistent_set_404(client: TestClient) -> None:
    response = client.get("/api/v1/qna/nonexistent-id")
    assert response.status_code == 404
