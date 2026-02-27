"""Document ingestion pipeline.

Orchestrates: parse → chunk → embed → store in vector DB → save original → catalog entry.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from src.catalog.models import SourceCreate, SourceType
from src.data.chunking import chunk_text
from src.data.folder_scanner import scan_folder
from src.data.parsers import (
    compute_content_hash,
    compute_file_hash,
    fetch_and_parse_url,
    parse_file,
)
from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.catalog.service import CatalogService
    from src.data.file_store import FileStore
    from src.models.embeddings import EmbeddingModel
    from src.utils.vector_store import VectorStore

logger = get_logger(__name__)


class IngestionResult:
    """Result of an ingestion operation."""

    def __init__(self, source_id: str, status: str, chunk_count: int = 0, error: str = "") -> None:
        self.source_id = source_id
        self.status = status
        self.chunk_count = chunk_count
        self.error = error


class FolderIngestionResult:
    """Result of a folder ingestion operation."""

    def __init__(self) -> None:
        self.folder_source_id: str = ""
        self.results: list[IngestionResult] = []
        self.total_files: int = 0
        self.succeeded: int = 0
        self.failed: int = 0
        self.skipped: int = 0


class IngestionPipeline:
    """Orchestrates document ingestion from various sources."""

    def __init__(
        self,
        catalog: CatalogService,
        file_store: FileStore,
        embedding_model: EmbeddingModel,
        vector_store: VectorStore,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        self._catalog = catalog
        self._file_store = file_store
        self._embedding = embedding_model
        self._vector_store = vector_store
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def ingest_file(
        self,
        file_data: bytes,
        filename: str,
        *,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> IngestionResult:
        """Ingest an uploaded file."""
        suffix = Path(filename).suffix.lower()
        source = self._catalog.create_source(
            SourceCreate(
                title=title or filename,
                source_type=SourceType.FILE_UPLOAD,
                origin=filename,
                file_format=suffix.lstrip("."),
                tags=tags or [],
            )
        )

        try:
            self._catalog.mark_processing(source.id)

            # Write to temp file for parsing
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_data)
                tmp_path = Path(tmp.name)

            # Check for duplicates
            file_hash = compute_file_hash(tmp_path)
            duplicate = self._catalog.find_duplicate(file_hash)
            if duplicate:
                tmp_path.unlink(missing_ok=True)
                self._catalog.mark_failed(
                    source.id,
                    f"Duplicate of source '{duplicate.title}' (ID: {duplicate.id})",
                )
                return IngestionResult(
                    source_id=source.id,
                    status="duplicate",
                    error=f"Duplicate of {duplicate.id}",
                )

            # Store original
            stored_path = self._file_store.store_bytes(source.id, file_data, filename)

            # Parse
            text = parse_file(tmp_path)
            tmp_path.unlink(missing_ok=True)

            if not text.strip():
                self._catalog.mark_failed(source.id, "No extractable text content")
                return IngestionResult(
                    source_id=source.id, status="failed", error="No extractable text"
                )

            # Chunk, embed, store
            chunk_count, total_tokens = self._process_text(source.id, text)

            self._catalog.mark_completed(
                source.id,
                chunk_count=chunk_count,
                total_tokens=total_tokens,
                content_hash=file_hash,
                original_file_path=stored_path,
            )

            return IngestionResult(source_id=source.id, status="completed", chunk_count=chunk_count)

        except AppError:
            self._catalog.mark_failed(source.id, "Ingestion failed")
            raise
        except Exception as e:
            self._catalog.mark_failed(source.id, str(e))
            raise AppError(
                code=ErrorCode.INGESTION_FAILED,
                message=f"Failed to ingest file: {filename}",
                context={"filename": filename},
                cause=e,
            ) from e

    def ingest_url(
        self,
        url: str,
        *,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> IngestionResult:
        """Ingest content from a URL."""
        source = self._catalog.create_source(
            SourceCreate(
                title=title or url,
                source_type=SourceType.URL,
                origin=url,
                file_format="html",
                tags=tags or [],
            )
        )

        try:
            self._catalog.mark_processing(source.id)

            # Single fetch: parse text + get raw HTML in one request
            text, raw_html = fetch_and_parse_url(url)
            content_hash = compute_content_hash(text)

            # Check for duplicates
            duplicate = self._catalog.find_duplicate(content_hash)
            if duplicate:
                self._catalog.mark_failed(
                    source.id,
                    f"Duplicate of source '{duplicate.title}' (ID: {duplicate.id})",
                )
                return IngestionResult(
                    source_id=source.id,
                    status="duplicate",
                    error=f"Duplicate of {duplicate.id}",
                )

            if not text.strip():
                self._catalog.mark_failed(source.id, "No extractable text from URL")
                return IngestionResult(
                    source_id=source.id, status="failed", error="No extractable text"
                )

            # Store HTML snapshot
            stored_path = self._file_store.store_url_snapshot(source.id, raw_html, url)

            # Chunk, embed, store
            chunk_count, total_tokens = self._process_text(source.id, text)

            self._catalog.mark_completed(
                source.id,
                chunk_count=chunk_count,
                total_tokens=total_tokens,
                content_hash=content_hash,
                original_file_path=stored_path,
            )

            return IngestionResult(source_id=source.id, status="completed", chunk_count=chunk_count)

        except AppError:
            self._catalog.mark_failed(source.id, "URL ingestion failed")
            raise
        except Exception as e:
            self._catalog.mark_failed(source.id, str(e))
            raise AppError(
                code=ErrorCode.INGESTION_FAILED,
                message=f"Failed to ingest URL: {url}",
                context={"url": url},
                cause=e,
            ) from e

    def ingest_text(
        self,
        content: str,
        *,
        title: str = "Pasted Text",
        tags: list[str] | None = None,
    ) -> IngestionResult:
        """Ingest raw text content."""
        source = self._catalog.create_source(
            SourceCreate(
                title=title,
                source_type=SourceType.TEXT,
                origin="pasted",
                file_format="txt",
                tags=tags or [],
            )
        )

        try:
            self._catalog.mark_processing(source.id)

            content_hash = compute_content_hash(content)

            # Check for duplicates
            duplicate = self._catalog.find_duplicate(content_hash)
            if duplicate:
                self._catalog.mark_failed(
                    source.id,
                    f"Duplicate of source '{duplicate.title}' (ID: {duplicate.id})",
                )
                return IngestionResult(
                    source_id=source.id,
                    status="duplicate",
                    error=f"Duplicate of {duplicate.id}",
                )

            # Store original text
            stored_path = self._file_store.store_text(source.id, content)

            # Chunk, embed, store
            chunk_count, total_tokens = self._process_text(source.id, content)

            self._catalog.mark_completed(
                source.id,
                chunk_count=chunk_count,
                total_tokens=total_tokens,
                content_hash=content_hash,
                original_file_path=stored_path,
            )

            return IngestionResult(source_id=source.id, status="completed", chunk_count=chunk_count)

        except Exception as e:
            self._catalog.mark_failed(source.id, str(e))
            raise AppError(
                code=ErrorCode.INGESTION_FAILED,
                message="Failed to ingest text content",
                cause=e,
            ) from e

    def ingest_folder(
        self,
        folder_path: str,
        *,
        tags: list[str] | None = None,
    ) -> FolderIngestionResult:
        """Ingest all supported files from a local folder recursively."""
        result = FolderIngestionResult()

        # Create a parent source for the folder
        folder_source = self._catalog.create_source(
            SourceCreate(
                title=Path(folder_path).name,
                source_type=SourceType.LOCAL_FOLDER,
                origin=folder_path,
                file_format="folder",
                tags=tags or [],
            )
        )
        result.folder_source_id = folder_source.id
        self._catalog.mark_processing(folder_source.id)

        # Scan for files
        discovered = scan_folder(folder_path)
        result.total_files = len(discovered)

        for file_info in discovered:
            try:
                file_data = file_info.path.read_bytes()
                file_result = self._ingest_folder_file(
                    file_data=file_data,
                    filename=file_info.filename,
                    relative_path=file_info.relative_path,
                    file_format=file_info.format,
                    parent_folder_id=folder_source.id,
                    tags=tags or [],
                )
                result.results.append(file_result)
                if file_result.status == "completed":
                    result.succeeded += 1
                elif file_result.status == "duplicate":
                    result.skipped += 1
                else:
                    result.failed += 1
            except Exception as e:
                logger.warning(
                    "folder_file_ingestion_failed",
                    file=file_info.relative_path,
                    error=str(e),
                )
                result.results.append(
                    IngestionResult(
                        source_id="",
                        status="failed",
                        error=str(e),
                    )
                )
                result.failed += 1

        # Mark folder source as completed
        self._catalog.mark_completed(
            folder_source.id,
            chunk_count=0,
            total_tokens=0,
            content_hash="",
            original_file_path=folder_path,
            description=f"Folder with {result.succeeded} files indexed",
        )

        logger.info(
            "folder_ingestion_completed",
            folder=folder_path,
            total=result.total_files,
            succeeded=result.succeeded,
            failed=result.failed,
            skipped=result.skipped,
        )

        return result

    def reindex_source(self, source_id: str) -> IngestionResult:
        """Re-index a source by deleting old chunks and re-processing."""
        source = self._catalog.get_source(source_id)

        # Delete old vectors
        self._vector_store.delete_by_source(source_id)

        # Re-parse from stored original
        file_result = self._file_store.get_file_bytes(source_id)
        if file_result is None:
            raise AppError(
                code=ErrorCode.FILE_NOT_FOUND,
                message="Original file not found for re-indexing",
                context={"source_id": source_id},
            )

        file_bytes, filename = file_result
        suffix = Path(filename).suffix.lower()

        if suffix == ".html":
            # URL snapshot — parse as HTML
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(file_bytes.decode("utf-8"), "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
        elif suffix in (".txt",):
            text = file_bytes.decode("utf-8")
        else:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = Path(tmp.name)
            text = parse_file(tmp_path)
            tmp_path.unlink(missing_ok=True)

        if not text.strip():
            self._catalog.mark_failed(source_id, "No extractable text on re-index")
            return IngestionResult(
                source_id=source_id, status="failed", error="No extractable text"
            )

        chunk_count, total_tokens = self._process_text(source_id, text)

        self._catalog.mark_completed(
            source_id,
            chunk_count=chunk_count,
            total_tokens=total_tokens,
            content_hash=source.content_hash,
            original_file_path=source.original_file_path,
        )

        return IngestionResult(source_id=source_id, status="completed", chunk_count=chunk_count)

    def _process_text(self, source_id: str, text: str) -> tuple[int, int]:
        """Chunk text, compute embeddings, and store in vector DB. Returns (chunk_count, tokens)."""
        chunks = chunk_text(
            text,
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
        )

        if not chunks:
            return 0, 0

        chunk_texts = [c.text for c in chunks]
        chunk_ids = [f"{source_id}_chunk_{c.index}" for c in chunks]
        metadatas = [
            {
                "source_id": source_id,
                "chunk_index": c.index,
                "start_char": c.start_char,
                "end_char": c.end_char,
            }
            for c in chunks
        ]

        # Compute embeddings
        embeddings = self._embedding.embed_texts(chunk_texts)

        # Store in vector DB
        self._vector_store.add(
            ids=chunk_ids,
            embeddings=embeddings,
            documents=chunk_texts,
            metadatas=metadatas,
        )

        total_tokens = sum(c.token_count for c in chunks)
        return len(chunks), total_tokens

    def _ingest_folder_file(
        self,
        file_data: bytes,
        filename: str,
        relative_path: str,
        file_format: str,
        parent_folder_id: str,
        tags: list[str],
    ) -> IngestionResult:
        """Ingest a single file discovered in a folder scan."""
        suffix = Path(filename).suffix.lower()
        source = self._catalog.create_source(
            SourceCreate(
                title=relative_path,
                source_type=SourceType.FILE_UPLOAD,
                origin=relative_path,
                file_format=file_format,
                tags=tags,
                parent_folder_id=parent_folder_id,
            )
        )

        self._catalog.mark_processing(source.id)

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_data)
            tmp_path = Path(tmp.name)

        file_hash = compute_file_hash(tmp_path)
        duplicate = self._catalog.find_duplicate(file_hash)
        if duplicate:
            tmp_path.unlink(missing_ok=True)
            self._catalog.mark_failed(
                source.id,
                f"Duplicate of source '{duplicate.title}' (ID: {duplicate.id})",
            )
            return IngestionResult(
                source_id=source.id, status="duplicate", error=f"Duplicate of {duplicate.id}"
            )

        stored_path = self._file_store.store_bytes(source.id, file_data, filename)

        text = parse_file(tmp_path)
        tmp_path.unlink(missing_ok=True)

        if not text.strip():
            self._catalog.mark_failed(source.id, "No extractable text")
            return IngestionResult(
                source_id=source.id, status="failed", error="No extractable text"
            )

        chunk_count, total_tokens = self._process_text(source.id, text)

        self._catalog.mark_completed(
            source.id,
            chunk_count=chunk_count,
            total_tokens=total_tokens,
            content_hash=file_hash,
            original_file_path=stored_path,
        )

        return IngestionResult(source_id=source.id, status="completed", chunk_count=chunk_count)
