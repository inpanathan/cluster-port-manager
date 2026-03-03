"""Process books into vector embeddings.

Usage:
    uv run python scripts/process_books.py                    # process all pending
    uv run python scripts/process_books.py --book-id <ID>     # process a single book
    uv run python scripts/process_books.py --force             # re-process completed books
    uv run python scripts/process_books.py --dry-run           # show what would be processed
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.books.models import EmbeddingStatus
from src.books.repository import BookRepository
from src.books.service import BookService
from src.catalog.repository import CatalogRepository
from src.catalog.service import CatalogService
from src.models.embeddings import create_embedding_model
from src.pipelines.book_embedding import BookEmbeddingPipeline
from src.utils.config import settings
from src.utils.vector_store import VectorStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Process books into vector embeddings")
    parser.add_argument("--book-id", help="Process a single book by ID")
    parser.add_argument("--force", action="store_true", help="Re-process completed books")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    args = parser.parse_args()

    # Initialize services
    book_repo = BookRepository(settings.books.database_path)
    book_service = BookService(book_repo)
    catalog_repo = CatalogRepository(settings.catalog.database_path)
    catalog_service = CatalogService(catalog_repo)

    embedding_model = create_embedding_model(
        backend=settings.model_backend,
        model_name=settings.embedding.model_name,
        dimension=settings.embedding.dimension,
        device=settings.embedding.device,
    )

    vector_store = VectorStore(
        url=settings.vector_store.url,
        collection_name=settings.vector_store.collection_name,
        dimension=settings.embedding.dimension,
        in_memory=(settings.model_backend == "mock"),
    )

    pipeline = BookEmbeddingPipeline(
        book_service=book_service,
        catalog_service=catalog_service,
        embedding_model=embedding_model,
        vector_store=vector_store,
        books_collection=settings.books.qdrant_collection,
        chunk_size=settings.books.chunk_size,
        chunk_overlap=settings.books.chunk_overlap,
        embedding_batch_size=settings.books.embedding_batch_size,
    )

    if args.dry_run:
        return _dry_run(book_service, args.force)

    if args.book_id:
        return _process_single(pipeline, args.book_id, args.force)

    return _process_all(pipeline, args.force)


def _dry_run(book_service: BookService, force: bool) -> int:
    response = book_service.list_books(limit=10000)
    books = response.books

    if not force:
        books = [b for b in books if b.embedding_status != EmbeddingStatus.COMPLETED]

    print(f"\n{'=' * 60}")  # noqa: T201
    print(f"  Books to process: {len(books)}")  # noqa: T201
    print(f"  Mode: {'force (re-process all)' if force else 'pending only'}")  # noqa: T201
    print(f"{'=' * 60}")  # noqa: T201

    for b in books:
        print(f"  [{b.embedding_status}] {b.title} ({b.file_format})")  # noqa: T201

    if not books:
        print("  No books to process.")  # noqa: T201
    return 0


def _process_single(pipeline: BookEmbeddingPipeline, book_id: str, force: bool) -> int:
    print(f"\nProcessing book: {book_id}")  # noqa: T201
    start = time.monotonic()
    try:
        result = pipeline.process_book(book_id, force=force)
        elapsed = time.monotonic() - start
        if result.skipped:
            print("  Skipped (already completed)")  # noqa: T201
        else:
            print(f"  Chunks: {result.chunk_count}")  # noqa: T201
            print(f"  Tokens: {result.total_tokens}")  # noqa: T201
            print(f"  Validation: {'passed' if result.validation_passed else 'failed'}")  # noqa: T201
            print(f"  Time: {elapsed:.1f}s")  # noqa: T201
        return 0
    except Exception as e:
        print(f"  FAILED: {e}")  # noqa: T201
        return 1


def _process_all(pipeline: BookEmbeddingPipeline, force: bool) -> int:
    print(f"\n{'=' * 60}")  # noqa: T201
    print("  Processing all books")  # noqa: T201
    print(f"  Mode: {'force (re-process all)' if force else 'pending only'}")  # noqa: T201
    print(f"{'=' * 60}\n")  # noqa: T201

    start = time.monotonic()
    result = pipeline.process_all_books(force=force)
    elapsed = time.monotonic() - start

    print(f"\n{'=' * 60}")  # noqa: T201
    print(f"  Total:     {result.total}")  # noqa: T201
    print(f"  Completed: {result.completed}")  # noqa: T201
    print(f"  Failed:    {result.failed}")  # noqa: T201
    print(f"  Skipped:   {result.skipped}")  # noqa: T201
    print(f"  Time:      {elapsed:.1f}s")  # noqa: T201
    print(f"{'=' * 60}")  # noqa: T201

    if result.errors:
        print("\nErrors:")  # noqa: T201
        for err in result.errors:
            print(f"  - {err}")  # noqa: T201

    return 1 if result.failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
