"""Business logic for the source catalog."""

from __future__ import annotations

import uuid
from datetime import datetime

from src.catalog.models import (
    ProcessingStatus,
    Source,
    SourceCreate,
    SourceListResponse,
    SourceSummary,
    SourceUpdate,
)
from src.catalog.repository import CatalogRepository
from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CatalogService:
    """Source catalog business logic."""

    def __init__(self, repository: CatalogRepository) -> None:
        self._repo = repository

    def create_source(self, data: SourceCreate) -> Source:
        """Create a new source entry in the catalog."""
        source = Source(
            id=str(uuid.uuid4()),
            title=data.title,
            source_type=data.source_type,
            origin=data.origin,
            file_format=data.file_format,
            tags=data.tags,
            description=data.description,
            parent_folder_id=data.parent_folder_id,
            ingested_at=datetime.utcnow(),
            status=ProcessingStatus.QUEUED,
        )
        return self._repo.create(source)

    def get_source(self, source_id: str) -> Source:
        """Get a source by ID, raising if not found."""
        source = self._repo.get(source_id)
        if source is None:
            raise AppError(
                code=ErrorCode.SOURCE_NOT_FOUND,
                message=f"Source not found: {source_id}",
                context={"source_id": source_id},
            )
        return source

    def list_sources(
        self,
        *,
        source_type: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> SourceListResponse:
        """List sources with filtering."""
        sources, total = self._repo.list_sources(
            source_type=source_type,
            status=status,
            tag=tag,
            search=search,
            limit=limit,
            offset=offset,
        )
        summaries = [
            SourceSummary(
                id=s.id,
                title=s.title,
                source_type=s.source_type,
                file_format=s.file_format,
                ingested_at=s.ingested_at,
                status=s.status,
                chunk_count=s.chunk_count,
                tags=s.tags,
            )
            for s in sources
        ]
        return SourceListResponse(sources=summaries, total=total)

    def update_source(self, source_id: str, data: SourceUpdate) -> Source:
        """Update source metadata."""
        self.get_source(source_id)  # ensure exists
        fields: dict[str, object] = {}
        if data.title is not None:
            fields["title"] = data.title
        if data.tags is not None:
            fields["tags"] = data.tags
        if data.description is not None:
            fields["description"] = data.description

        updated = self._repo.update(source_id, **fields)
        if updated is None:
            raise AppError(
                code=ErrorCode.SOURCE_NOT_FOUND,
                message=f"Source not found: {source_id}",
            )
        return updated

    def delete_source(self, source_id: str) -> None:
        """Delete a source from the catalog."""
        if not self._repo.delete(source_id):
            raise AppError(
                code=ErrorCode.SOURCE_NOT_FOUND,
                message=f"Source not found: {source_id}",
            )

    def mark_processing(self, source_id: str) -> None:
        """Mark a source as currently processing."""
        self._repo.update(source_id, status=ProcessingStatus.PROCESSING.value)

    def mark_completed(
        self,
        source_id: str,
        *,
        chunk_count: int,
        total_tokens: int,
        content_hash: str,
        original_file_path: str,
        description: str = "",
    ) -> None:
        """Mark a source as successfully processed."""
        self._repo.update(
            source_id,
            status=ProcessingStatus.COMPLETED.value,
            chunk_count=chunk_count,
            total_tokens=total_tokens,
            content_hash=content_hash,
            original_file_path=original_file_path,
            description=description,
            last_indexed_at=datetime.utcnow(),
        )

    def mark_failed(self, source_id: str, error: str) -> None:
        """Mark a source as failed with an error message."""
        self._repo.update(
            source_id,
            status=ProcessingStatus.FAILED.value,
            error_message=error,
        )

    def find_duplicate(self, content_hash: str) -> Source | None:
        """Check if a source with the same hash already exists."""
        return self._repo.find_by_hash(content_hash)
