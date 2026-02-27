"""Format-specific document parsers.

Each parser extracts plain text from a specific file format.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_FORMATS = {".pdf", ".docx", ".txt", ".md"}


def compute_content_hash(content: str) -> str:
    """Compute a SHA-256 hash of text content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_file_hash(file_path: Path) -> str:
    """Compute a SHA-256 hash of file bytes."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_pdf(file_path: Path) -> str:
    """Extract text from a PDF file."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages)
        logger.info("pdf_parsed", path=str(file_path), pages=len(reader.pages))
        return text.strip()
    except Exception as e:
        raise AppError(
            code=ErrorCode.PARSE_FAILED,
            message=f"Failed to parse PDF: {file_path}",
            context={"path": str(file_path)},
            cause=e,
        ) from e


def parse_docx(file_path: Path) -> str:
    """Extract text from a DOCX file."""
    try:
        from docx import Document

        doc = Document(str(file_path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        logger.info("docx_parsed", path=str(file_path), paragraphs=len(paragraphs))
        return text.strip()
    except Exception as e:
        raise AppError(
            code=ErrorCode.PARSE_FAILED,
            message=f"Failed to parse DOCX: {file_path}",
            context={"path": str(file_path)},
            cause=e,
        ) from e


def parse_text(file_path: Path) -> str:
    """Read plain text or Markdown files."""
    try:
        text = file_path.read_text(encoding="utf-8")
        logger.info("text_parsed", path=str(file_path), chars=len(text))
        return text.strip()
    except Exception as e:
        raise AppError(
            code=ErrorCode.PARSE_FAILED,
            message=f"Failed to read text file: {file_path}",
            context={"path": str(file_path)},
            cause=e,
        ) from e


def parse_url(url: str, *, timeout: int = 30) -> str:
    """Fetch a URL and extract readable text from HTML."""
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except httpx.TimeoutException as e:
        raise AppError(
            code=ErrorCode.URL_FETCH_FAILED,
            message=f"Timeout fetching URL: {url}",
            context={"url": url},
            cause=e,
        ) from e
    except httpx.HTTPStatusError as e:
        raise AppError(
            code=ErrorCode.URL_FETCH_FAILED,
            message=f"HTTP error fetching URL: {url} (status {e.response.status_code})",
            context={"url": url, "status_code": e.response.status_code},
            cause=e,
        ) from e
    except httpx.HTTPError as e:
        raise AppError(
            code=ErrorCode.URL_FETCH_FAILED,
            message=f"Failed to fetch URL: {url}",
            context={"url": url},
            cause=e,
        ) from e

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove script, style, nav, footer, header elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    logger.info("url_parsed", url=url, chars=len(text))
    return text


def parse_file(file_path: Path) -> str:
    """Parse a file based on its extension."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(file_path)
    if suffix == ".docx":
        return parse_docx(file_path)
    if suffix in (".txt", ".md"):
        return parse_text(file_path)
    raise AppError(
        code=ErrorCode.UNSUPPORTED_FORMAT,
        message=f"Unsupported file format: {suffix}",
        context={"path": str(file_path), "format": suffix},
    )


def fetch_and_parse_url(url: str, *, timeout: int = 30) -> tuple[str, str]:
    """Fetch a URL once and return (extracted_text, raw_html).

    Eliminates the double-fetch that happened when parse_url() and
    get_raw_content_for_url() were called separately.
    """
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except httpx.TimeoutException as e:
        raise AppError(
            code=ErrorCode.URL_FETCH_FAILED,
            message=f"Timeout fetching URL: {url}",
            context={"url": url},
            cause=e,
        ) from e
    except httpx.HTTPStatusError as e:
        raise AppError(
            code=ErrorCode.URL_FETCH_FAILED,
            message=f"HTTP error fetching URL: {url} (status {e.response.status_code})",
            context={"url": url, "status_code": e.response.status_code},
            cause=e,
        ) from e
    except httpx.HTTPError as e:
        raise AppError(
            code=ErrorCode.URL_FETCH_FAILED,
            message=f"Failed to fetch URL: {url}",
            context={"url": url},
            cause=e,
        ) from e

    raw_html = response.text

    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)

    logger.info("url_fetched_and_parsed", url=url, chars=len(text))
    return text, raw_html


def get_raw_content_for_url(url: str, *, timeout: int = 30) -> str:
    """Fetch raw HTML from a URL for storage as the original content."""
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        return response.text
    except httpx.HTTPError as e:
        raise AppError(
            code=ErrorCode.URL_FETCH_FAILED,
            message=f"Failed to fetch URL: {url}",
            context={"url": url},
            cause=e,
        ) from e
