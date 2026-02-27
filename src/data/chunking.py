"""Text chunking strategies for document processing."""

from __future__ import annotations

from dataclasses import dataclass

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Chunk:
    """A single text chunk with metadata."""

    text: str
    index: int
    start_char: int
    end_char: int
    token_count: int


def estimate_tokens(text: str) -> int:
    """Rough token count estimation (words * 1.3)."""
    return int(len(text.split()) * 1.3)


def chunk_text(
    text: str,
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    min_chunk_size: int = 50,
) -> list[Chunk]:
    """Split text into overlapping chunks using recursive character splitting.

    Tries to split on paragraph boundaries first, then sentences, then words.
    """
    if not text.strip():
        return []

    separators = ["\n\n", "\n", ". ", " "]
    raw_chunks = _recursive_split(text, separators, chunk_size)

    # Merge small chunks and apply overlap
    chunks: list[Chunk] = []
    current_pos = 0

    for i, raw in enumerate(raw_chunks):
        if len(raw.split()) < min_chunk_size // 4 and chunks:
            # Merge tiny trailing fragments into previous chunk
            prev = chunks[-1]
            chunks[-1] = Chunk(
                text=prev.text + "\n" + raw,
                index=prev.index,
                start_char=prev.start_char,
                end_char=current_pos + len(raw),
                token_count=estimate_tokens(prev.text + "\n" + raw),
            )
        else:
            chunks.append(
                Chunk(
                    text=raw,
                    index=i,
                    start_char=current_pos,
                    end_char=current_pos + len(raw),
                    token_count=estimate_tokens(raw),
                )
            )
        current_pos += len(raw)

    # Re-index
    for i, c in enumerate(chunks):
        c.index = i

    logger.info("text_chunked", chunk_count=len(chunks), total_chars=len(text))
    return chunks


def _recursive_split(text: str, separators: list[str], max_size: int) -> list[str]:
    """Recursively split text trying each separator in order."""
    if estimate_tokens(text) <= max_size:
        return [text.strip()] if text.strip() else []

    # Find the best separator
    separator = separators[-1]  # fallback to space
    for sep in separators:
        if sep in text:
            separator = sep
            break

    parts = text.split(separator)
    results: list[str] = []
    current = ""

    for part in parts:
        candidate = f"{current}{separator}{part}" if current else part
        if estimate_tokens(candidate) <= max_size:
            current = candidate
        else:
            if current.strip():
                results.append(current.strip())
            if estimate_tokens(part) > max_size and len(separators) > 1:
                # Recurse with next separator
                results.extend(_recursive_split(part, separators[1:], max_size))
                current = ""
            else:
                current = part

    if current.strip():
        results.append(current.strip())

    return results
