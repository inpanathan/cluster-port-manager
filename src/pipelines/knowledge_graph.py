"""Knowledge graph construction pipeline.

Orchestrates: extract entities → resolve → build graph → track progress.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from src.features.knowledge_graph.entity_resolution import EntityResolver
from src.features.knowledge_graph.models import (
    CrossRefResult,
    GraphBuildResult,
    RelationshipType,
)
from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.books.models import Book
    from src.books.service import BookService
    from src.models.graph_extractor import GraphExtractor
    from src.utils.graph_store import GraphStore

logger = get_logger(__name__)


class KnowledgeGraphPipeline:
    """Build knowledge graphs from book content."""

    def __init__(
        self,
        graph_extractor: GraphExtractor,
        entity_resolver: EntityResolver,
        graph_store: GraphStore,
        book_service: BookService,
    ) -> None:
        self._extractor = graph_extractor
        self._resolver = entity_resolver
        self._graph_store = graph_store
        self._book_service = book_service

    def build_book_graph(
        self, book_id: str, chunks: list[dict], *, force: bool = False
    ) -> GraphBuildResult:
        """Build a knowledge graph for a single book.

        Args:
            book_id: ID of the book to process.
            chunks: List of dicts with keys: text, chapter_title, chapter_number.
            force: If True, rebuild even if already completed.
        """
        start = time.perf_counter()
        book = self._book_service.get_book(book_id)

        # Skip if already completed (unless force)
        if book.graph_status == "completed" and not force:
            return GraphBuildResult(book_id=book_id)

        # Must have completed embeddings first
        if book.embedding_status != "completed":
            return GraphBuildResult(
                book_id=book_id,
                error="Book embeddings must be completed before graph construction",
            )

        self._book_service.mark_graph_started(book_id)

        try:
            # 1. Extract entities and relationships from chunks
            extraction_results = self._extractor.extract_from_book(chunks, book.title)

            # 2. Flatten extracted entities
            all_entities = []
            all_relationships = []
            all_topics = []
            for result in extraction_results:
                all_entities.extend(result.entities)
                all_relationships.extend(result.relationships)
                all_topics.extend(result.topics)

            # 3. Resolve entities within the book
            resolved = self._resolver.resolve(all_entities, book_id=book_id)

            # 4. Delete existing graph for this book (idempotent)
            self._graph_store.delete_book_graph(book_id)

            # 5. Create nodes
            entity_count, relationship_count, topic_count = self._build_graph_nodes(
                book, resolved, all_relationships, all_topics, chunks
            )

            # 6. Mark completed
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            self._book_service.mark_graph_completed(book_id, entity_count=entity_count)

            logger.info(
                "book_graph_built",
                book_id=book_id,
                entities=entity_count,
                relationships=relationship_count,
                topics=topic_count,
                duration_ms=elapsed_ms,
            )

            return GraphBuildResult(
                book_id=book_id,
                entity_count=entity_count,
                relationship_count=relationship_count,
                topic_count=topic_count,
                duration_ms=elapsed_ms,
            )

        except AppError:
            self._book_service.mark_graph_failed(book_id, error="Graph construction failed")
            raise
        except Exception as e:
            error_msg = str(e)
            self._book_service.mark_graph_failed(book_id, error=error_msg)
            raise AppError(
                code=ErrorCode.GRAPH_CONSTRUCTION_FAILED,
                message=f"Failed to build knowledge graph for book {book_id}: {error_msg}",
                context={"book_id": book_id},
                cause=e,
            ) from e

    def _build_graph_nodes(
        self,
        book: Book,
        resolved_entities: list,
        relationships: list,
        topics: list,
        chunks: list[dict],
    ) -> tuple[int, int, int]:
        """Create all graph nodes and relationships for a book.

        Returns (entity_count, relationship_count, topic_count).
        """
        book_id = book.id

        # Book node
        book_node_id = self._graph_store.merge_node(
            "Book",
            match_keys={"id": book_id},
            properties={
                "title": book.title,
                "author": book.author,
                "isbn": book.isbn,
                "book_id": book_id,
                "file_format": book.file_format,
            },
        )

        # Author node
        if book.author:
            author_node_id = self._graph_store.merge_node(
                "Author",
                match_keys={"name": book.author},
                properties={"id": f"author_{book.author}", "book_id": book_id},
            )
            self._graph_store.create_relationship(
                book_node_id,
                author_node_id,
                RelationshipType.AUTHORED_BY.value,
            )

        # Chapter nodes
        chapter_ids: dict[int, str] = {}
        seen_chapters: set[int] = set()
        for chunk in chunks:
            ch_num = chunk.get("chapter_number", 0)
            if ch_num in seen_chapters:
                continue
            seen_chapters.add(ch_num)
            ch_title = chunk.get("chapter_title", f"Chapter {ch_num}")
            ch_id = self._graph_store.create_node(
                "Chapter",
                {
                    "id": f"{book_id}_ch{ch_num}",
                    "book_id": book_id,
                    "number": ch_num,
                    "title": ch_title,
                },
            )
            chapter_ids[ch_num] = ch_id
            self._graph_store.create_relationship(
                book_node_id, ch_id, RelationshipType.HAS_CHAPTER.value
            )

        # Entity nodes
        entity_node_ids: dict[str, str] = {}
        for entity in resolved_entities:
            node_id = self._graph_store.merge_node(
                "Entity",
                match_keys={"name": entity.name.lower()},
                properties={
                    "id": entity.id,
                    "name": entity.name,
                    "type": entity.type,
                    "description": entity.description,
                    "mention_count": entity.mention_count,
                    "book_id": book_id,
                },
            )
            entity_node_ids[entity.name.lower()] = node_id

        # Topic nodes
        topic_node_ids: dict[str, str] = {}
        topic_count = 0
        seen_topics: set[str] = set()
        for topic in topics:
            norm = topic.name.lower()
            if norm in seen_topics:
                continue
            seen_topics.add(norm)
            topic_count += 1
            tid = self._graph_store.merge_node(
                "Topic",
                match_keys={"name": norm},
                properties={
                    "id": f"topic_{norm}",
                    "name": topic.name,
                    "description": topic.description,
                    "book_id": book_id,
                },
            )
            topic_node_ids[norm] = tid
            if topic.parent_topic:
                parent_norm = topic.parent_topic.lower()
                if parent_norm in topic_node_ids:
                    self._graph_store.create_relationship(
                        tid,
                        topic_node_ids[parent_norm],
                        RelationshipType.SUBTOPIC_OF.value,
                    )

        # Relationships between entities
        rel_count = 0
        for rel in relationships:
            src_key = rel.source_entity.lower()
            tgt_key = rel.target_entity.lower()
            src_id = entity_node_ids.get(src_key)
            tgt_id = entity_node_ids.get(tgt_key)
            if src_id and tgt_id:
                rel_type = rel.relationship_type.upper()
                if not hasattr(RelationshipType, rel_type):
                    rel_type = RelationshipType.RELATED_TO.value
                self._graph_store.create_relationship(
                    src_id, tgt_id, rel_type, {"context": rel.context[:200]}
                )
                rel_count += 1

        return len(resolved_entities), rel_count, topic_count

    def build_cross_references(self) -> CrossRefResult:
        """Build cross-reference edges between books sharing entities/topics."""
        # Query all books that have completed graphs
        books_result = self._book_service.list_books(limit=1000)
        completed_books = [b for b in books_result.books]

        if len(completed_books) < 2:
            return CrossRefResult(books_processed=len(completed_books))

        # For each pair of books, count shared entities via the graph store
        cross_ref_count = 0
        for i, book_a in enumerate(completed_books):
            for book_b in completed_books[i + 1 :]:
                shared = self._graph_store.query(
                    "MATCH (e:Entity) "
                    "WHERE e.book_id = $a_id "
                    "WITH collect(e.name) AS a_entities "
                    "MATCH (e2:Entity) "
                    "WHERE e2.book_id = $b_id AND e2.name IN a_entities "
                    "RETURN count(e2) AS shared_count",
                    {"a_id": book_a.id, "b_id": book_b.id},
                )
                shared_count = shared[0]["shared_count"] if shared else 0
                if shared_count >= 3:
                    self._graph_store.create_relationship(
                        book_a.id,
                        book_b.id,
                        RelationshipType.CROSS_REFERENCED.value,
                        {"shared_entity_count": shared_count},
                    )
                    cross_ref_count += 1

        logger.info(
            "cross_references_built",
            books_processed=len(completed_books),
            cross_ref_edges=cross_ref_count,
        )
        return CrossRefResult(
            cross_ref_edges=cross_ref_count,
            books_processed=len(completed_books),
        )

    def build_all(self, *, force: bool = False) -> list[GraphBuildResult]:
        """Build knowledge graphs for all books with completed embeddings."""
        from src.data.book_chunking import chunk_book
        from src.data.book_text_extractor import extract_book_text

        books_result = self._book_service.list_books(limit=1000)
        results: list[GraphBuildResult] = []

        for book_summary in books_result.books:
            book = self._book_service.get_book(book_summary.id)

            if book.embedding_status != "completed":
                continue
            if book.graph_status == "completed" and not force:
                continue

            # Extract and chunk the book text
            try:
                from pathlib import Path

                structure = extract_book_text(Path(book.file_path), book.file_format)
                book_chunks = chunk_book(structure)
                chunk_dicts = [
                    {
                        "text": c.text,
                        "chapter_title": c.chapter_title,
                        "chapter_number": c.chapter_number,
                    }
                    for c in book_chunks
                ]

                result = self.build_book_graph(book.id, chunk_dicts, force=force)
                results.append(result)
            except Exception as e:
                logger.warning(
                    "graph_build_skipped",
                    book_id=book.id,
                    error=str(e),
                )
                results.append(GraphBuildResult(book_id=book.id, error=str(e)))

        # Build cross-references after all books are done
        if results:
            self.build_cross_references()

        return results
