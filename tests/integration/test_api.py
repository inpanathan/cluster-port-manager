"""Integration tests for the API."""

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


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "env" in data
    assert "version" in data


def test_app_starts_with_services_initialized(client: TestClient) -> None:
    """Verify the service container is populated after lifespan startup."""
    from src.api.dependencies import get_container

    container = get_container()
    assert container.catalog is not None
    assert container.ingestion is not None
    assert container.chat is not None
    assert container.interview is not None
    assert container.qna is not None
    assert container.summarization is not None
