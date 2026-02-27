"""Unit tests for the ingestion pipeline."""

from __future__ import annotations

import pytest

from src.data.ingestion import IngestionPipeline
from src.utils.errors import AppError


def test_ingest_text_happy_path(ingestion_pipeline: IngestionPipeline) -> None:
    result = ingestion_pipeline.ingest_text("Hello world, this is a test document.")
    assert result.status == "completed"
    assert result.source_id
    assert result.chunk_count >= 1


def test_ingest_text_duplicate_detection(ingestion_pipeline: IngestionPipeline) -> None:
    content = "Duplicate detection test content."
    first = ingestion_pipeline.ingest_text(content, title="First")
    assert first.status == "completed"

    second = ingestion_pipeline.ingest_text(content, title="Second")
    assert second.status == "duplicate"
    assert first.source_id != second.source_id


def test_ingest_file_happy_path(
    ingestion_pipeline: IngestionPipeline,
) -> None:
    content = "This is a sample text file for ingestion testing."
    result = ingestion_pipeline.ingest_file(
        content.encode("utf-8"),
        "sample.txt",
        title="Sample TXT",
    )
    assert result.status == "completed"
    assert result.chunk_count >= 1


def test_ingest_file_empty_content(
    ingestion_pipeline: IngestionPipeline,
) -> None:
    result = ingestion_pipeline.ingest_file(
        b"   ",
        "empty.txt",
        title="Empty File",
    )
    assert result.status == "failed"
    assert "No extractable text" in result.error


def test_ingest_file_unsupported_format(
    ingestion_pipeline: IngestionPipeline,
) -> None:
    with pytest.raises(AppError) as exc_info:
        ingestion_pipeline.ingest_file(
            b"binary data",
            "file.xyz",
            title="Unknown Format",
        )
    assert exc_info.value.code == "UNSUPPORTED_FORMAT"


def test_reindex_source(
    ingestion_pipeline: IngestionPipeline,
) -> None:
    result = ingestion_pipeline.ingest_text(
        "Content for re-indexing test.",
        title="Reindex Me",
    )
    assert result.status == "completed"

    reindexed = ingestion_pipeline.reindex_source(result.source_id)
    assert reindexed.status == "completed"
    assert reindexed.source_id == result.source_id
