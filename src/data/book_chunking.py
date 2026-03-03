"""Structure-aware chunking for books.

Chunks each chapter independently and tags chunks with structural metadata
(chapter number, chapter title, content type).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.data.book_text_extractor import BookStructure, classify_chapter
from src.data.chunking import chunk_text
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BookChunk:
    """A text chunk from a book with structural metadata."""

    text: str
    index: int
    start_char: int
    end_char: int
    token_count: int
    chapter_number: int | None = None
    chapter_title: str | None = None
    content_type: str = "chapter_text"


def chunk_book(
    book_structure: BookStructure,
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[BookChunk]:
    """Chunk a book structure into BookChunks, one chapter at a time.

    Chunks never cross chapter boundaries. Each chunk is tagged with
    chapter number, title, and content type.

    Args:
        book_structure: The extracted book structure with chapters.
        chunk_size: Max tokens per chunk (passed to chunk_text).
        chunk_overlap: Token overlap between chunks.

    Returns:
        List of BookChunks with sequential global indices.
    """
    if not book_structure.chapters:
        return []

    all_chunks: list[BookChunk] = []
    global_index = 0
    global_char_offset = 0

    for chapter in book_structure.chapters:
        if not chapter.text.strip():
            continue

        content_type = classify_chapter(chapter.title)

        # Chunk this chapter using the existing chunking logic
        raw_chunks = chunk_text(
            chapter.text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        for raw_chunk in raw_chunks:
            all_chunks.append(
                BookChunk(
                    text=raw_chunk.text,
                    index=global_index,
                    start_char=global_char_offset + raw_chunk.start_char,
                    end_char=global_char_offset + raw_chunk.end_char,
                    token_count=raw_chunk.token_count,
                    chapter_number=chapter.number,
                    chapter_title=chapter.title,
                    content_type=content_type,
                )
            )
            global_index += 1

        global_char_offset += len(chapter.text)

    logger.info(
        "book_chunked",
        chapters=len(book_structure.chapters),
        total_chunks=len(all_chunks),
        total_tokens=sum(c.token_count for c in all_chunks),
    )
    return all_chunks
