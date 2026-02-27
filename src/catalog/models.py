"""Pydantic models for the source catalog."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    """Type of ingested source."""

    FILE_UPLOAD = "file_upload"
    URL = "url"
    TEXT = "text"
    LOCAL_FOLDER = "local_folder"


class ProcessingStatus(StrEnum):
    """Processing status of a source."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Source(BaseModel):
    """A single indexed source in the catalog."""

    id: str
    title: str
    source_type: SourceType
    origin: str = ""
    file_format: str = ""
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    last_indexed_at: datetime | None = None
    content_hash: str = ""
    chunk_count: int = 0
    total_tokens: int = 0
    status: ProcessingStatus = ProcessingStatus.QUEUED
    original_file_path: str = ""
    parent_folder_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    error_message: str = ""


class SourceCreate(BaseModel):
    """Request model for creating a source."""

    title: str
    source_type: SourceType
    origin: str = ""
    file_format: str = ""
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    parent_folder_id: str | None = None


class SourceUpdate(BaseModel):
    """Request model for updating source metadata."""

    title: str | None = None
    tags: list[str] | None = None
    description: str | None = None


class SourceSummary(BaseModel):
    """Lightweight source info for list views."""

    id: str
    title: str
    source_type: SourceType
    file_format: str
    ingested_at: datetime
    status: ProcessingStatus
    chunk_count: int
    tags: list[str]


class SourceListResponse(BaseModel):
    """Paginated source list response."""

    sources: list[SourceSummary]
    total: int
