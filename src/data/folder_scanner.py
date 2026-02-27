"""Local folder recursive discovery for batch ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.data.parsers import SUPPORTED_FORMATS
from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DiscoveredFile:
    """A file discovered during folder scanning."""

    path: Path
    relative_path: str
    filename: str
    format: str
    size_bytes: int


def scan_folder(folder_path: str) -> list[DiscoveredFile]:
    """Recursively scan a folder for supported documents.

    Returns a list of discovered files with metadata. Skips symlinks
    and unsupported file types with warnings.
    """
    root = Path(folder_path).resolve()

    if not root.exists():
        raise AppError(
            code=ErrorCode.FOLDER_SCAN_FAILED,
            message=f"Folder does not exist: {folder_path}",
            context={"path": folder_path},
        )

    if not root.is_dir():
        raise AppError(
            code=ErrorCode.FOLDER_SCAN_FAILED,
            message=f"Path is not a directory: {folder_path}",
            context={"path": folder_path},
        )

    discovered: list[DiscoveredFile] = []
    seen_paths: set[Path] = set()

    for item in sorted(root.rglob("*")):
        # Skip symlinks to avoid circular references
        if item.is_symlink():
            logger.warning("symlink_skipped", path=str(item))
            continue

        if not item.is_file():
            continue

        # Resolve to detect circular symlinks
        resolved = item.resolve()
        if resolved in seen_paths:
            logger.warning("circular_reference_skipped", path=str(item))
            continue
        seen_paths.add(resolved)

        suffix = item.suffix.lower()
        if suffix not in SUPPORTED_FORMATS:
            continue

        relative = str(item.relative_to(root))
        discovered.append(
            DiscoveredFile(
                path=item,
                relative_path=relative,
                filename=item.name,
                format=suffix.lstrip("."),
                size_bytes=item.stat().st_size,
            )
        )

    logger.info(
        "folder_scanned",
        folder=folder_path,
        files_found=len(discovered),
    )
    return discovered
