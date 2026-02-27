"""Original file storage and retrieval.

Stores uploaded files, URL snapshots, and pasted text in their original format
so users can read/download them later.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)


class FileStore:
    """Stores and retrieves original source files."""

    def __init__(self, base_directory: str) -> None:
        self._base = Path(base_directory)
        self._base.mkdir(parents=True, exist_ok=True)

    def _source_dir(self, source_id: str) -> Path:
        return self._base / source_id

    def store_uploaded_file(self, source_id: str, file_path: Path, filename: str) -> str:
        """Copy an uploaded file into the store. Returns the stored path."""
        dest_dir = self._source_dir(source_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filename
        shutil.copy2(file_path, dest)
        logger.info("file_stored", source_id=source_id, filename=filename)
        return str(dest)

    def store_bytes(self, source_id: str, data: bytes, filename: str) -> str:
        """Store raw bytes as a file. Returns the stored path."""
        dest_dir = self._source_dir(source_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filename
        dest.write_bytes(data)
        logger.info("bytes_stored", source_id=source_id, filename=filename)
        return str(dest)

    def store_text(self, source_id: str, content: str, filename: str = "content.txt") -> str:
        """Store text content. Returns the stored path."""
        dest_dir = self._source_dir(source_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filename
        dest.write_text(content, encoding="utf-8")
        logger.info("text_stored", source_id=source_id, filename=filename)
        return str(dest)

    def store_url_snapshot(self, source_id: str, html_content: str, url: str) -> str:
        """Store an HTML snapshot of a fetched URL. Returns the stored path."""
        dest_dir = self._source_dir(source_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "snapshot.html"
        # Store both the URL and HTML
        header = f"<!-- Original URL: {url} -->\n"
        dest.write_text(header + html_content, encoding="utf-8")
        logger.info("url_snapshot_stored", source_id=source_id, url=url)
        return str(dest)

    def get_file_path(self, source_id: str) -> Path | None:
        """Get the path to the stored original file."""
        source_dir = self._source_dir(source_id)
        if not source_dir.exists():
            return None
        files = list(source_dir.iterdir())
        if not files:
            return None
        return files[0]

    def get_file_bytes(self, source_id: str) -> tuple[bytes, str] | None:
        """Get the file bytes and filename. Returns (bytes, filename) or None."""
        file_path = self.get_file_path(source_id)
        if file_path is None:
            return None
        return file_path.read_bytes(), file_path.name

    def delete(self, source_id: str) -> None:
        """Delete all stored files for a source."""
        source_dir = self._source_dir(source_id)
        if source_dir.exists():
            shutil.rmtree(source_dir)
            logger.info("file_deleted", source_id=source_id)

    def exists(self, source_id: str) -> bool:
        """Check if files exist for a source."""
        return self._source_dir(source_id).exists()
