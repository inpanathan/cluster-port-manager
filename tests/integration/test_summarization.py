"""Integration tests for the summarization API endpoint."""

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


def _ingest(client: TestClient, content: str, title: str) -> str:
    r = client.post("/api/v1/sources/text", json={"content": content, "title": title})
    return r.json()["source_id"]


def test_summarize_source(client: TestClient) -> None:
    sid = _ingest(client, "Python is a popular programming language for data science.", "Python DS")
    response = client.post(
        "/api/v1/summarize",
        json={"source_ids": [sid], "mode": "short"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]
    assert data["mode"] == "short"


def test_summarize_topic(client: TestClient) -> None:
    _ingest(client, "FastAPI is a modern web framework for building APIs.", "FastAPI")
    response = client.post(
        "/api/v1/summarize",
        json={"topic": "FastAPI", "mode": "detailed"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]
    assert data["mode"] == "detailed"


def test_summarize_no_params_400(client: TestClient) -> None:
    response = client.post("/api/v1/summarize", json={})
    assert response.status_code == 400
