"""Build knowledge graph from embedded books.

Usage:
    uv run python scripts/build_knowledge_graph.py            # process all pending
    uv run python scripts/build_knowledge_graph.py --book-id <ID>  # single book
    uv run python scripts/build_knowledge_graph.py --force    # rebuild all
    uv run python scripts/build_knowledge_graph.py --dry-run  # preview
    uv run python scripts/build_knowledge_graph.py --skip-cross-refs  # skip cross-refs
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.books.repository import BookRepository
from src.books.service import BookService
from src.data.book_chunking import chunk_book
from src.data.book_text_extractor import extract_book_text
from src.features.knowledge_graph.entity_resolution import EntityResolver
from src.models.graph_extractor import create_graph_extractor
from src.models.llm import create_llm_client
from src.pipelines.knowledge_graph import KnowledgeGraphPipeline
from src.utils.config import settings
from src.utils.graph_store import create_graph_store
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build knowledge graph from books")
    parser.add_argument("--book-id", help="Process a single book by ID")
    parser.add_argument("--force", action="store_true", help="Rebuild even if completed")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be processed")
    parser.add_argument(
        "--skip-cross-refs", action="store_true", help="Skip cross-reference building"
    )
    return parser.parse_args()


def _create_pipeline() -> tuple[KnowledgeGraphPipeline, BookService]:
    """Initialize all dependencies for the pipeline."""
    book_repo = BookRepository(settings.books.database_path)
    book_service = BookService(book_repo)

    llm_client = create_llm_client(
        backend=settings.model_backend,
        api_key=settings.llm.api_key,
        model_id=settings.llm.model_id,
        temperature=settings.llm.temperature,
        timeout=settings.llm.timeout_seconds,
        vllm_base_url=settings.llm.vllm_base_url,
        vllm_model=settings.llm.vllm_model,
    )

    graph_extractor = create_graph_extractor(settings.model_backend, llm_client)
    entity_resolver = EntityResolver()
    graph_store = create_graph_store(settings.model_backend)

    pipeline = KnowledgeGraphPipeline(
        graph_extractor=graph_extractor,
        entity_resolver=entity_resolver,
        graph_store=graph_store,
        book_service=book_service,
    )
    return pipeline, book_service


def _dry_run(book_service: BookService, book_id: str | None) -> None:
    """Show what would be processed without doing anything."""
    if book_id:
        book = book_service.get_book(book_id)
        logger.info(
            "dry_run_single",
            book_id=book.id,
            title=book.title,
            embedding_status=book.embedding_status,
            graph_status=book.graph_status,
        )
        return

    result = book_service.list_books(limit=1000)
    pending = [b for b in result.books if b.embedding_status == "completed"]
    logger.info("dry_run_summary", eligible_books=len(pending), total_books=result.total)
    for b in pending:
        logger.info("dry_run_book", book_id=b.id, title=b.title)


def _process_single(
    pipeline: KnowledgeGraphPipeline, book_service: BookService, book_id: str, *, force: bool
) -> None:
    """Process a single book."""
    book = book_service.get_book(book_id)
    structure = extract_book_text(Path(book.file_path), book.file_format)
    book_chunks = chunk_book(structure)
    chunk_dicts = [
        {"text": c.text, "chapter_title": c.chapter_title, "chapter_number": c.chapter_number}
        for c in book_chunks
    ]
    result = pipeline.build_book_graph(book_id, chunk_dicts, force=force)
    logger.info(
        "graph_build_result",
        book_id=result.book_id,
        entities=result.entity_count,
        relationships=result.relationship_count,
        topics=result.topic_count,
        duration_ms=result.duration_ms,
        error=result.error,
    )


def _process_all(pipeline: KnowledgeGraphPipeline, *, force: bool, skip_cross_refs: bool) -> None:
    """Process all eligible books."""
    results = pipeline.build_all(force=force)
    completed = sum(1 for r in results if not r.error)
    failed = sum(1 for r in results if r.error)
    logger.info(
        "graph_build_all_complete",
        total=len(results),
        completed=completed,
        failed=failed,
    )

    if not skip_cross_refs and completed > 0:
        cross_ref = pipeline.build_cross_references()
        logger.info(
            "cross_references_result",
            edges=cross_ref.cross_ref_edges,
            books=cross_ref.books_processed,
        )


def main() -> None:
    args = _parse_args()
    pipeline, book_service = _create_pipeline()

    if args.dry_run:
        _dry_run(book_service, args.book_id)
        return

    if args.book_id:
        _process_single(pipeline, book_service, args.book_id, force=args.force)
    else:
        _process_all(pipeline, force=args.force, skip_cross_refs=args.skip_cross_refs)


if __name__ == "__main__":
    main()
