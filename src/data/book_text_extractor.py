"""Book-aware text extraction preserving chapter/section structure.

Extracts text from PDF, EPUB, DOCX, and TXT/MD files while detecting
chapter boundaries to enable structure-aware chunking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Patterns for detecting chapter headings
_CHAPTER_PATTERNS = [
    re.compile(r"^Chapter\s+\d+", re.IGNORECASE),
    re.compile(r"^CHAPTER\s+\d+"),
    re.compile(r"^Part\s+\d+", re.IGNORECASE),
    re.compile(r"^PART\s+\d+"),
    re.compile(r"^\d+\.\s+[A-Z]"),  # "1. Introduction"
    re.compile(r"^[IVXLC]+\.\s+"),  # Roman numeral headings
]

_FRONT_MATTER_TITLES = {
    "preface",
    "foreword",
    "introduction",
    "prologue",
    "acknowledgments",
    "acknowledgements",
    "dedication",
    "about the author",
    "about the authors",
    "copyright",
    "title page",
}

_BACK_MATTER_TITLES = {
    "appendix",
    "bibliography",
    "references",
    "glossary",
    "index",
    "afterword",
    "epilogue",
    "notes",
    "endnotes",
    "about the author",
    "colophon",
}


@dataclass
class BookChapter:
    """A single chapter extracted from a book."""

    number: int
    title: str
    text: str
    start_page: int | None = None
    end_page: int | None = None


@dataclass
class BookStructure:
    """Structured representation of a book's text content."""

    title: str
    author: str
    chapters: list[BookChapter] = field(default_factory=list)
    raw_text: str = ""
    page_count: int = 0


def extract_book_text(file_path: Path, file_format: str) -> BookStructure:
    """Extract text from a book file, preserving chapter structure.

    Args:
        file_path: Path to the book file.
        file_format: File extension (e.g., ".pdf", ".epub").

    Returns:
        BookStructure with chapters and raw text.
    """
    fmt = file_format.lower().lstrip(".")
    extractors = {
        "pdf": _extract_pdf,
        "epub": _extract_epub,
        "docx": _extract_docx,
        "txt": _extract_text,
        "md": _extract_text,
    }

    extractor = extractors.get(fmt)
    if extractor is None:
        raise AppError(
            code=ErrorCode.UNSUPPORTED_FORMAT,
            message=f"Unsupported book format: {file_format}",
            context={"path": str(file_path), "format": file_format},
        )

    try:
        structure = extractor(file_path)
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code=ErrorCode.PARSE_FAILED,
            message=f"Failed to extract text from book: {file_path.name}",
            context={"path": str(file_path), "format": file_format},
            cause=e,
        ) from e

    # Fallback: if no chapters detected, create a single chapter from raw text
    if not structure.chapters and structure.raw_text.strip():
        structure.chapters = [BookChapter(number=1, title="Full Text", text=structure.raw_text)]

    logger.info(
        "book_text_extracted",
        path=str(file_path),
        format=fmt,
        chapters=len(structure.chapters),
        pages=structure.page_count,
        chars=len(structure.raw_text),
    )
    return structure


def _extract_pdf(file_path: Path) -> BookStructure:
    """Extract text from a PDF, detecting chapter boundaries via outline or patterns."""
    from pypdf import PdfReader

    reader = PdfReader(str(file_path))
    page_texts = [page.extract_text() or "" for page in reader.pages]
    raw_text = "\n\n".join(page_texts)

    chapters: list[BookChapter] = []

    # Try outline-based chapter detection, fall back to pattern matching
    outline_chapters = _chapters_from_pdf_outline(reader, page_texts)
    chapters = outline_chapters or _chapters_from_patterns(page_texts)

    meta = dict(reader.metadata) if reader.metadata else {}
    return BookStructure(
        title=str(meta.get("/Title") or "").strip() or file_path.stem,
        author=str(meta.get("/Author") or "").strip(),
        chapters=chapters,
        raw_text=raw_text,
        page_count=len(reader.pages),
    )


def _chapters_from_pdf_outline(reader: object, page_texts: list[str]) -> list[BookChapter]:
    """Extract chapters using the PDF outline/bookmark tree."""
    from pypdf import PdfReader

    if not isinstance(reader, PdfReader):
        return []

    try:
        outline = reader.outline
        if not outline:
            return []
    except Exception:
        return []

    # Flatten outline to (title, page_number) pairs
    destinations: list[tuple[str, int]] = []
    _flatten_destinations(reader, outline, destinations)

    if len(destinations) < 2:
        return []

    chapters: list[BookChapter] = []
    for i, (title, start_page) in enumerate(destinations):
        end_page = destinations[i + 1][1] - 1 if i + 1 < len(destinations) else len(page_texts) - 1
        chapter_text = "\n\n".join(page_texts[start_page : end_page + 1])

        if not chapter_text.strip():
            continue

        chapters.append(
            BookChapter(
                number=i + 1,
                title=title,
                text=chapter_text.strip(),
                start_page=start_page + 1,  # 1-indexed for display
                end_page=end_page + 1,
            )
        )

    return chapters


def _flatten_destinations(
    reader: object, outline: list, destinations: list[tuple[str, int]]
) -> None:
    """Recursively flatten PDF outline into (title, page_index) pairs."""
    for item in outline:
        if isinstance(item, list):
            _flatten_destinations(reader, item, destinations)
        elif hasattr(item, "title"):
            try:
                page_num = reader.get_destination_page_number(item)  # type: ignore[attr-defined]
                destinations.append((item.title, page_num))
            except Exception:
                pass


def _chapters_from_patterns(page_texts: list[str]) -> list[BookChapter]:
    """Detect chapter boundaries using regex patterns on page text."""
    chapters: list[BookChapter] = []
    current_title = ""
    current_text_parts: list[str] = []
    current_start_page: int | None = None
    chapter_num = 0

    for page_idx, page_text in enumerate(page_texts):
        lines = page_text.split("\n")
        found_heading = False

        for line in lines[:5]:  # Only check first 5 lines of each page
            stripped = line.strip()
            if not stripped:
                continue
            for pattern in _CHAPTER_PATTERNS:
                if pattern.match(stripped):
                    # Save previous chapter
                    if current_text_parts:
                        chapters.append(
                            BookChapter(
                                number=chapter_num,
                                title=current_title or f"Chapter {chapter_num}",
                                text="\n\n".join(current_text_parts).strip(),
                                start_page=current_start_page,
                                end_page=page_idx,  # 0-indexed, previous page
                            )
                        )
                    chapter_num += 1
                    current_title = stripped
                    current_text_parts = [page_text]
                    current_start_page = page_idx + 1
                    found_heading = True
                    break
            if found_heading:
                break

        if not found_heading:
            current_text_parts.append(page_text)

    # Save last chapter
    if current_text_parts:
        chapters.append(
            BookChapter(
                number=chapter_num or 1,
                title=current_title or "Content",
                text="\n\n".join(current_text_parts).strip(),
                start_page=current_start_page,
                end_page=len(page_texts),
            )
        )

    return chapters


def _extract_epub(file_path: Path) -> BookStructure:
    """Extract text from an EPUB, using spine items and headings for structure."""
    try:
        from ebooklib import epub
    except ImportError as e:
        raise AppError(
            code=ErrorCode.PARSE_FAILED,
            message="ebooklib is required for EPUB processing. Install with: uv sync --extra books",
            context={"path": str(file_path)},
            cause=e,
        ) from e

    from bs4 import BeautifulSoup

    book = epub.read_epub(str(file_path), options={"ignore_ncx": True})

    # Extract metadata
    def _get_dc(field: str) -> str:
        items = book.get_metadata("DC", field)
        return str(items[0][0]).strip() if items else ""

    title = _get_dc("title") or file_path.stem
    author = _get_dc("creator")

    chapters: list[BookChapter] = []
    all_text_parts: list[str] = []
    chapter_num = 0

    for item in book.get_items_of_type(9):  # ITEM_DOCUMENT
        content = item.get_content()
        soup = BeautifulSoup(content, "html.parser")

        # Remove scripts and styles
        for tag in soup(["script", "style"]):
            tag.decompose()

        # Try to find chapter title from headings
        heading = soup.find(["h1", "h2", "h3"])
        chapter_title = heading.get_text(strip=True) if heading else ""

        body_text = soup.get_text(separator="\n", strip=True)
        if not body_text.strip():
            continue

        all_text_parts.append(body_text)

        if chapter_title:
            chapter_num += 1
            chapters.append(
                BookChapter(
                    number=chapter_num,
                    title=chapter_title,
                    text=body_text,
                )
            )
        elif chapters:
            # Append to previous chapter if no heading found
            prev = chapters[-1]
            chapters[-1] = BookChapter(
                number=prev.number,
                title=prev.title,
                text=prev.text + "\n\n" + body_text,
                start_page=prev.start_page,
                end_page=prev.end_page,
            )

    raw_text = "\n\n".join(all_text_parts)

    return BookStructure(
        title=title,
        author=author,
        chapters=chapters,
        raw_text=raw_text,
        page_count=0,  # EPUB has no fixed page count
    )


def _extract_docx(file_path: Path) -> BookStructure:
    """Extract text from a DOCX, using paragraph styles for chapter detection."""
    from docx import Document

    doc = Document(str(file_path))
    props = doc.core_properties

    chapters: list[BookChapter] = []
    all_text_parts: list[str] = []
    current_title = ""
    current_parts: list[str] = []
    chapter_num = 0

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        all_text_parts.append(text)
        style_name = (para.style.name or "").lower() if para.style else ""

        if "heading 1" in style_name or "heading 2" in style_name:
            # Save previous chapter
            if current_parts:
                chapters.append(
                    BookChapter(
                        number=chapter_num or 1,
                        title=current_title or "Content",
                        text="\n\n".join(current_parts),
                    )
                )
            chapter_num += 1
            current_title = text
            current_parts = []
        else:
            current_parts.append(text)

    # Save last chapter
    if current_parts:
        chapters.append(
            BookChapter(
                number=chapter_num or 1,
                title=current_title or "Content",
                text="\n\n".join(current_parts),
            )
        )

    raw_text = "\n\n".join(all_text_parts)

    return BookStructure(
        title=(props.title or "").strip() or file_path.stem,
        author=(props.author or "").strip(),
        chapters=chapters,
        raw_text=raw_text,
        page_count=0,
    )


def _extract_text(file_path: Path) -> BookStructure:
    """Extract text from TXT/MD files, using heading patterns for structure."""
    text = file_path.read_text(encoding="utf-8", errors="replace")

    # Try markdown heading-based splitting
    heading_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(text))

    chapters: list[BookChapter] = []
    if matches:
        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chapter_text = text[start:end].strip()
            if chapter_text:
                chapters.append(
                    BookChapter(
                        number=i + 1,
                        title=match.group(2).strip(),
                        text=chapter_text,
                    )
                )

    # Extract title from first heading or filename
    title = matches[0].group(2).strip() if matches else file_path.stem

    return BookStructure(
        title=title,
        author="",
        chapters=chapters,
        raw_text=text,
        page_count=0,
    )


def classify_chapter(title: str) -> str:
    """Classify a chapter as front_matter, back_matter, or chapter_text."""
    normalized = title.lower().strip()
    if normalized in _FRONT_MATTER_TITLES or any(
        normalized.startswith(fm) for fm in _FRONT_MATTER_TITLES
    ):
        return "front_matter"
    if normalized in _BACK_MATTER_TITLES or any(
        normalized.startswith(bm) for bm in _BACK_MATTER_TITLES
    ):
        return "back_matter"
    return "chapter_text"
