"""Business logic for the book catalog."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.books.models import (
    Book,
    BookCreate,
    BookListResponse,
    BookSummary,
    BookUpdate,
    EmbeddingStatus,
)
from src.books.repository import BookRepository
from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BookService:
    """Book catalog business logic."""

    def __init__(self, repository: BookRepository) -> None:
        self._repo = repository

    def create_book(self, data: BookCreate) -> Book:
        """Create a new book entry in the catalog."""
        book = Book(
            id=str(uuid.uuid4()),
            title=data.title,
            author=data.author,
            isbn=data.isbn,
            publisher=data.publisher,
            publication_year=data.publication_year,
            language=data.language,
            page_count=data.page_count,
            file_format=data.file_format,
            file_size_bytes=data.file_size_bytes,
            file_hash=data.file_hash,
            file_path=data.file_path,
            cover_image_path=data.cover_image_path,
            description=data.description,
            table_of_contents=data.table_of_contents,
            tags=data.tags,
            drive_folder_path=data.drive_folder_path,
            drive_file_id=data.drive_file_id,
            created_at=datetime.now(tz=UTC),
        )
        return self._repo.create(book)

    def get_book(self, book_id: str) -> Book:
        """Get a book by ID, raising if not found."""
        book = self._repo.get(book_id)
        if book is None:
            raise AppError(
                code=ErrorCode.BOOK_NOT_FOUND,
                message=f"Book not found: {book_id}",
                context={"book_id": book_id},
            )
        return book

    def list_books(
        self,
        *,
        author: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        embedding_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> BookListResponse:
        """List books with filtering."""
        books, total = self._repo.list_books(
            author=author,
            tag=tag,
            search=search,
            embedding_status=embedding_status,
            limit=limit,
            offset=offset,
        )
        summaries = [
            BookSummary(
                id=b.id,
                title=b.title,
                author=b.author,
                file_format=b.file_format,
                publication_year=b.publication_year,
                cover_image_path=b.cover_image_path,
                tags=b.tags,
                embedding_status=b.embedding_status,
            )
            for b in books
        ]
        return BookListResponse(books=summaries, total=total)

    def update_book(self, book_id: str, data: BookUpdate) -> Book:
        """Update book metadata."""
        self.get_book(book_id)
        fields: dict[str, object] = {}
        if data.title is not None:
            fields["title"] = data.title
        if data.author is not None:
            fields["author"] = data.author
        if data.tags is not None:
            fields["tags"] = data.tags
        if data.description is not None:
            fields["description"] = data.description

        updated = self._repo.update(book_id, **fields)
        if updated is None:
            raise AppError(
                code=ErrorCode.BOOK_NOT_FOUND,
                message=f"Book not found: {book_id}",
            )
        return updated

    def delete_book(self, book_id: str) -> None:
        """Delete a book from the catalog."""
        if not self._repo.delete(book_id):
            raise AppError(
                code=ErrorCode.BOOK_NOT_FOUND,
                message=f"Book not found: {book_id}",
            )

    def find_duplicate(self, file_hash: str) -> Book | None:
        """Check if a book with the same hash already exists."""
        return self._repo.find_by_hash(file_hash)

    def find_by_drive_file_id(self, drive_file_id: str) -> Book | None:
        """Check if a book from this Drive file was already downloaded."""
        return self._repo.find_by_drive_file_id(drive_file_id)

    def mark_processed(self, book_id: str, *, processed_at: datetime | None = None) -> None:
        """Mark a book as metadata-processed."""
        self._repo.update(
            book_id,
            processed_at=processed_at or datetime.now(tz=UTC),
        )

    def mark_embedding_completed(self, book_id: str, *, source_id: str) -> None:
        """Mark a book's embeddings as completed and link to source."""
        self._repo.update(
            book_id,
            embedding_status=EmbeddingStatus.COMPLETED.value,
            source_id=source_id,
        )

    def mark_embedding_failed(self, book_id: str, *, error: str) -> None:
        """Mark a book's embedding as failed."""
        self._repo.update(
            book_id,
            embedding_status=EmbeddingStatus.FAILED.value,
        )
        logger.warning("book_embedding_failed", book_id=book_id, error=error)

    def mark_graph_started(self, book_id: str) -> None:
        """Mark a book's graph construction as in progress."""
        from src.books.models import GraphStatus

        self._repo.update(book_id, graph_status=GraphStatus.PROCESSING.value)

    def mark_graph_completed(self, book_id: str, *, entity_count: int) -> None:
        """Mark a book's knowledge graph as completed."""
        from src.books.models import GraphStatus

        self._repo.update(book_id, graph_status=GraphStatus.COMPLETED.value)
        logger.info("book_graph_completed", book_id=book_id, entity_count=entity_count)

    def mark_graph_failed(self, book_id: str, *, error: str) -> None:
        """Mark a book's graph construction as failed."""
        from src.books.models import GraphStatus

        self._repo.update(book_id, graph_status=GraphStatus.FAILED.value)
        logger.warning("book_graph_failed", book_id=book_id, error=error)
