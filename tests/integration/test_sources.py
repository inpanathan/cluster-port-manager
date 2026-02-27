"""Integration tests for source ingestion and catalog endpoints."""

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
        # Isolate data dirs for this test session
        settings.catalog.database_path = f"{tmp}/catalog.db"
        settings.vector_store.persist_directory = f"{tmp}/vectorstore"
        settings.file_store.base_directory = f"{tmp}/originals"

        app = create_app()
        with TestClient(app) as c:
            yield c


def _upload_text_file(
    client: TestClient, content: str = "Test content.", title: str = "Test"
) -> dict:
    """Helper to upload a text file and return the response JSON."""
    response = client.post(
        "/api/v1/sources/upload",
        files={"file": ("test.txt", content.encode(), "text/plain")},
        data={"title": title},
    )
    assert response.status_code == 200
    return response.json()


def test_upload_file(client: TestClient) -> None:
    data = _upload_text_file(client)
    assert data["status"] == "completed"
    assert data["source_id"]
    assert data["chunk_count"] >= 1


def test_ingest_text(client: TestClient) -> None:
    response = client.post(
        "/api/v1/sources/text",
        json={"content": "Some text content for ingestion.", "title": "Text Source"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


def test_list_sources(client: TestClient) -> None:
    _upload_text_file(client, "File A content.", "File A")
    _upload_text_file(client, "File B content.", "File B")
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert len(data["sources"]) >= 2


def test_get_source(client: TestClient) -> None:
    upload = _upload_text_file(client)
    source_id = upload["source_id"]
    response = client.get(f"/api/v1/sources/{source_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == source_id
    assert data["status"] == "completed"


def test_get_source_not_found_404(client: TestClient) -> None:
    response = client.get("/api/v1/sources/nonexistent-id")
    assert response.status_code == 404


def test_update_source(client: TestClient) -> None:
    upload = _upload_text_file(client)
    source_id = upload["source_id"]
    response = client.put(
        f"/api/v1/sources/{source_id}",
        json={"title": "Updated Title", "tags": ["updated"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert "updated" in data["tags"]


def test_delete_source_204(client: TestClient) -> None:
    upload = _upload_text_file(client)
    source_id = upload["source_id"]
    response = client.delete(f"/api/v1/sources/{source_id}")
    assert response.status_code == 204

    # Verify it's gone
    response = client.get(f"/api/v1/sources/{source_id}")
    assert response.status_code == 404


def test_reindex_source(client: TestClient) -> None:
    upload = _upload_text_file(client, "Content for reindex test.")
    source_id = upload["source_id"]
    response = client.post(f"/api/v1/sources/{source_id}/reindex")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


def test_download_original(client: TestClient) -> None:
    content = "Downloadable content."
    upload = _upload_text_file(client, content, "Download Test")
    source_id = upload["source_id"]
    response = client.get(f"/api/v1/sources/{source_id}/original")
    assert response.status_code == 200
    assert content.encode() in response.content
