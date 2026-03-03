"""Book embedding pipeline.

Orchestrates: extract text → chunk → embed → store in Qdrant → register source.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from src.books.models import EmbeddingStatus
from src.catalog.models import SourceCreate, SourceType
from src.data.book_chunking import BookChunk, chunk_book
from src.data.book_text_extractor import extract_book_text
from src.data.parsers import compute_file_hash
from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.books.service import BookService
    from src.catalog.service import CatalogService
    from src.models.embeddings import EmbeddingModel
    from src.utils.vector_store import VectorStore

logger = get_logger(__name__)


@dataclass
class BookProcessingResult:
    """Result of processing a single book."""

    book_id: str
    chunk_count: int = 0
    total_tokens: int = 0
    duration_ms: int = 0
    validation_passed: bool = False
    skipped: bool = False
    error: str = ""


@dataclass
class BatchResult:
    """Result of processing multiple books."""

    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class BookEmbeddingPipeline:
    """Processes books into vector embeddings stored in Qdrant."""

    def __init__(
        self,
        book_service: BookService,
        catalog_service: CatalogService,
        embedding_model: EmbeddingModel,
        vector_store: VectorStore,
        *,
        books_collection: str = "books",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        embedding_batch_size: int = 32,
    ) -> None:
        self._books = book_service
        self._catalog = catalog_service
        self._embedding = embedding_model
        self._vector_store = vector_store
        self._collection = books_collection
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._batch_size = embedding_batch_size

    def process_book(self, book_id: str, *, force: bool = False) -> BookProcessingResult:
        """Process a single book: extract, chunk, embed, store, register.

        Args:
            book_id: ID of the book to process.
            force: If True, re-process even if already completed.

        Returns:
            BookProcessingResult with stats.
        """
        start = time.monotonic()
        book = self._books.get_book(book_id)

        # Skip if already completed (unless force)
        if book.embedding_status == EmbeddingStatus.COMPLETED and not force:
            logger.info("book_embedding_skipped", book_id=book_id, reason="already_completed")
            return BookProcessingResult(book_id=book_id, skipped=True)

        # If force, check content hash — skip if unchanged
        if force and book.embedding_status == EmbeddingStatus.COMPLETED:
            file_path = Path(book.file_path)
            if file_path.exists():
                current_hash = compute_file_hash(file_path)
                if current_hash == book.file_hash:
                    logger.info(
                        "book_embedding_skipped",
                        book_id=book_id,
                        reason="content_unchanged",
                    )
                    return BookProcessingResult(book_id=book_id, skipped=True)

        # Mark as processing
        self._books._repo.update(book_id, embedding_status=EmbeddingStatus.PROCESSING.value)

        try:
            # Extract text
            file_path = Path(book.file_path)
            if not file_path.exists():
                raise AppError(
                    code=ErrorCode.FILE_NOT_FOUND,
                    message=f"Book file not found: {book.file_path}",
                    context={"book_id": book_id, "path": book.file_path},
                )

            structure = extract_book_text(file_path, book.file_format)

            # Chunk
            chunks = chunk_book(
                structure,
                chunk_size=self._chunk_size,
                chunk_overlap=self._chunk_overlap,
            )

            if not chunks:
                raise AppError(
                    code=ErrorCode.PARSE_FAILED,
                    message="No chunks produced from book text",
                    context={"book_id": book_id},
                )

            # Embed in batches
            all_embeddings: list[list[float]] = []
            for batch_start in range(0, len(chunks), self._batch_size):
                batch = chunks[batch_start : batch_start + self._batch_size]
                batch_texts = [c.text for c in batch]
                batch_embeddings = self._embedding.embed_texts(batch_texts)
                all_embeddings.extend(batch_embeddings)

            # Delete existing vectors for idempotent re-processing
            self._vector_store.delete_book_vectors(self._collection, book_id)

            # Ensure collection exists
            self._vector_store.ensure_books_collection(self._collection, self._embedding.dimension)

            # Store in Qdrant
            chunk_ids = [f"{book_id}_chunk_{c.index}" for c in chunks]
            chunk_texts = [c.text for c in chunks]
            metadatas = _build_chunk_metadatas(chunks, book)

            self._vector_store.add_book_chunks(
                collection_name=self._collection,
                book_id=book_id,
                chunk_ids=chunk_ids,
                embeddings=all_embeddings,
                documents=chunk_texts,
                metadatas=metadatas,
            )

            # Register as source in catalog
            source = self._catalog.create_source(
                SourceCreate(
                    title=book.title,
                    source_type=SourceType.FILE_UPLOAD,
                    origin=book.file_path,
                    file_format=book.file_format.lstrip("."),
                    tags=book.tags,
                    description=f"Book: {book.title} by {book.author}",
                )
            )
            total_tokens = sum(c.token_count for c in chunks)
            self._catalog.mark_completed(
                source.id,
                chunk_count=len(chunks),
                total_tokens=total_tokens,
                content_hash=book.file_hash,
                original_file_path=book.file_path,
            )

            # Validate embedding quality
            validation_passed = self._validate_embedding(book_id, book.title)

            # Mark completed and link source
            self._books.mark_embedding_completed(book_id, source_id=source.id)

            duration_ms = int((time.monotonic() - start) * 1000)

            logger.info(
                "book_embedding_completed",
                book_id=book_id,
                title=book.title,
                chunks=len(chunks),
                tokens=total_tokens,
                duration_ms=duration_ms,
                validation_passed=validation_passed,
            )

            return BookProcessingResult(
                book_id=book_id,
                chunk_count=len(chunks),
                total_tokens=total_tokens,
                duration_ms=duration_ms,
                validation_passed=validation_passed,
            )

        except Exception as e:
            # Clean up partial vectors on failure
            self._vector_store.delete_book_vectors(self._collection, book_id)
            error_msg = str(e)
            self._books.mark_embedding_failed(book_id, error=error_msg)

            if isinstance(e, AppError):
                raise
            raise AppError(
                code=ErrorCode.EMBEDDING_FAILED,
                message=f"Book embedding failed: {book.title}",
                context={"book_id": book_id},
                cause=e,
            ) from e

    def process_all_books(self, *, force: bool = False) -> BatchResult:
        """Process all pending books.

        Args:
            force: If True, re-process all books including completed ones.

        Returns:
            BatchResult with aggregate stats.
        """
        response = self._books.list_books(limit=10000)
        books = response.books

        if not force:
            books = [b for b in books if b.embedding_status != EmbeddingStatus.COMPLETED]

        result = BatchResult(total=len(books))

        for i, book_summary in enumerate(books):
            logger.info(
                "book_embedding_progress",
                completed=i,
                total=len(books),
                current_book=book_summary.title,
            )
            try:
                proc_result = self.process_book(book_summary.id, force=force)
                if proc_result.skipped:
                    result.skipped += 1
                else:
                    result.completed += 1
            except Exception as e:
                result.failed += 1
                result.errors.append(f"{book_summary.title}: {e}")
                logger.error(
                    "book_embedding_batch_error",
                    book_id=book_summary.id,
                    title=book_summary.title,
                    error=str(e),
                )

        logger.info(
            "book_embedding_batch_completed",
            total=result.total,
            completed=result.completed,
            failed=result.failed,
            skipped=result.skipped,
        )
        return result

    def _validate_embedding(self, book_id: str, title: str) -> bool:
        """Validate embedding quality by searching for the book title."""
        try:
            query_embedding = self._embedding.embed_query(title)
            results = self._vector_store.search_books(
                self._collection,
                query_embedding,
                top_k=5,
                book_id=book_id,
            )
            if results and results[0].metadata.get("book_id") == book_id:
                logger.info("book_embedding_validation_passed", book_id=book_id)
                return True
            logger.warning("book_embedding_validation_failed", book_id=book_id)
            return False
        except Exception as e:
            logger.warning("book_embedding_validation_error", book_id=book_id, error=str(e))
            return False


def _build_chunk_metadatas(chunks: list[BookChunk], book: object) -> list[dict]:
    """Build metadata dicts for each chunk to store in Qdrant."""
    metadatas = []
    for chunk in chunks:
        meta: dict = {
            "chunk_index": chunk.index,
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "content_type": chunk.content_type,
            "author": getattr(book, "author", ""),
            "title": getattr(book, "title", ""),
        }
        if chunk.chapter_number is not None:
            meta["chapter_number"] = chunk.chapter_number
        if chunk.chapter_title:
            meta["chapter_title"] = chunk.chapter_title
        # Include book-level metadata for search filtering
        isbn = getattr(book, "isbn", "")
        if isbn:
            meta["isbn"] = isbn
        pub_year = getattr(book, "publication_year", None)
        if pub_year:
            meta["publication_year"] = pub_year
        language = getattr(book, "language", "")
        if language:
            meta["language"] = language
        tags = getattr(book, "tags", [])
        if tags:
            meta["tags"] = tags
        metadatas.append(meta)
    return metadatas
