"""SQLite-backed repository for the source catalog."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from src.catalog.models import ProcessingStatus, Source, SourceType
from src.utils.logger import get_logger

logger = get_logger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    origin TEXT DEFAULT '',
    file_format TEXT DEFAULT '',
    ingested_at TEXT NOT NULL,
    last_indexed_at TEXT,
    content_hash TEXT DEFAULT '',
    chunk_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    status TEXT DEFAULT 'queued',
    original_file_path TEXT DEFAULT '',
    parent_folder_id TEXT,
    tags TEXT DEFAULT '[]',
    description TEXT DEFAULT '',
    error_message TEXT DEFAULT ''
);
"""


class CatalogRepository:
    """CRUD operations for the source catalog backed by SQLite."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE)
            conn.commit()
        logger.info("catalog_db_initialized", path=self._db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_source(self, row: sqlite3.Row) -> Source:
        return Source(
            id=row["id"],
            title=row["title"],
            source_type=SourceType(row["source_type"]),
            origin=row["origin"] or "",
            file_format=row["file_format"] or "",
            ingested_at=datetime.fromisoformat(row["ingested_at"]),
            last_indexed_at=(
                datetime.fromisoformat(row["last_indexed_at"]) if row["last_indexed_at"] else None
            ),
            content_hash=row["content_hash"] or "",
            chunk_count=row["chunk_count"] or 0,
            total_tokens=row["total_tokens"] or 0,
            status=ProcessingStatus(row["status"]),
            original_file_path=row["original_file_path"] or "",
            parent_folder_id=row["parent_folder_id"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            description=row["description"] or "",
            error_message=row["error_message"] or "",
        )

    def create(self, source: Source) -> Source:
        """Insert a new source."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO sources
                   (id, title, source_type, origin, file_format, ingested_at,
                    last_indexed_at, content_hash, chunk_count, total_tokens,
                    status, original_file_path, parent_folder_id, tags,
                    description, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    source.id,
                    source.title,
                    source.source_type.value,
                    source.origin,
                    source.file_format,
                    source.ingested_at.isoformat(),
                    source.last_indexed_at.isoformat() if source.last_indexed_at else None,
                    source.content_hash,
                    source.chunk_count,
                    source.total_tokens,
                    source.status.value,
                    source.original_file_path,
                    source.parent_folder_id,
                    json.dumps(source.tags),
                    source.description,
                    source.error_message,
                ),
            )
            conn.commit()
        logger.info("source_created", source_id=source.id, title=source.title)
        return source

    def get(self, source_id: str) -> Source | None:
        """Get a source by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_source(row)

    def list_sources(
        self,
        *,
        source_type: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Source], int]:
        """List sources with optional filters. Returns (sources, total_count)."""
        conditions: list[str] = []
        params: list[str | int] = []

        if source_type:
            conditions.append("source_type = ?")
            params.append(source_type)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if tag:
            conditions.append("tags LIKE ?")
            params.append(f"%{tag}%")
        if search:
            conditions.append("(title LIKE ? OR description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""

        with self._connect() as conn:
            count_row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM sources{where}",
                params,  # noqa: S608
            ).fetchone()
            total = count_row["cnt"] if count_row else 0

            rows = conn.execute(
                f"SELECT * FROM sources{where} ORDER BY ingested_at DESC LIMIT ? OFFSET ?",  # noqa: S608
                [*params, limit, offset],
            ).fetchall()

        return [self._row_to_source(r) for r in rows], total

    def update(self, source_id: str, **fields: object) -> Source | None:
        """Update specific fields on a source."""
        if not fields:
            return self.get(source_id)

        set_clauses: list[str] = []
        params: list[object] = []
        for key, value in fields.items():
            if key == "tags" and isinstance(value, list):
                set_clauses.append(f"{key} = ?")
                params.append(json.dumps(value))
            elif key in ("last_indexed_at", "ingested_at") and isinstance(value, datetime):
                set_clauses.append(f"{key} = ?")
                params.append(value.isoformat())
            else:
                set_clauses.append(f"{key} = ?")
                params.append(value)

        params.append(source_id)

        with self._connect() as conn:
            conn.execute(
                f"UPDATE sources SET {', '.join(set_clauses)} WHERE id = ?",  # noqa: S608
                params,
            )
            conn.commit()

        return self.get(source_id)

    def delete(self, source_id: str) -> bool:
        """Delete a source. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
            conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("source_deleted", source_id=source_id)
        return deleted

    def find_by_hash(self, content_hash: str) -> Source | None:
        """Find a source by its content hash for duplicate detection."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sources WHERE content_hash = ?", (content_hash,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_source(row)
