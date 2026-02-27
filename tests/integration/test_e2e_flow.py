"""End-to-end integration test exercising the full Knowledge Hub flow."""

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


def test_full_happy_path(client: TestClient) -> None:
    """Exercise the complete flow: ingest → browse → chat → summarize → Q&A → interview → delete."""

    # 1. Upload a text file
    content = (
        "Python is a high-level programming language known for its simplicity and readability."
    )
    r = client.post(
        "/api/v1/sources/upload",
        files={"file": ("python.txt", content.encode(), "text/plain")},
        data={"title": "Python Overview"},
    )
    assert r.status_code == 200
    source_id = r.json()["source_id"]
    assert r.json()["status"] == "completed"

    # 2. List sources — verify it appears
    r = client.get("/api/v1/sources")
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    ids = [s["id"] for s in r.json()["sources"]]
    assert source_id in ids

    # 3. Get source detail
    r = client.get(f"/api/v1/sources/{source_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "Python Overview"

    # 4. Download original
    r = client.get(f"/api/v1/sources/{source_id}/original")
    assert r.status_code == 200
    assert content.encode() in r.content

    # 5. Chat — ask about the content
    r = client.post(
        "/api/v1/chat",
        json={"message": "What is Python?", "source_ids": [source_id]},
    )
    assert r.status_code == 200
    chat_data = r.json()
    assert chat_data["answer"]
    assert chat_data["session_id"]

    # 6. Summarize
    r = client.post(
        "/api/v1/summarize",
        json={"source_ids": [source_id], "mode": "short"},
    )
    assert r.status_code == 200
    assert r.json()["summary"]

    # 7. Generate Q&A pairs
    r = client.post(
        "/api/v1/qna/generate",
        json={"topic": "Python", "count": 3},
    )
    assert r.status_code == 200
    qna_id = r.json()["id"]

    # 8. Retrieve the Q&A set
    r = client.get(f"/api/v1/qna/{qna_id}")
    assert r.status_code == 200
    assert r.json()["id"] == qna_id

    # 9. Start interview
    r = client.post(
        "/api/v1/interview/start",
        json={"topic": "Python", "question_count": 2},
    )
    assert r.status_code == 200
    assert r.json()["id"]
    assert r.json()["total_questions"] > 0

    # 10. Delete source
    r = client.delete(f"/api/v1/sources/{source_id}")
    assert r.status_code == 204

    # 11. Verify it's gone
    r = client.get("/api/v1/sources")
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()["sources"]]
    assert source_id not in ids
