"""Authenticate with Google Drive interactively.

Run this BEFORE any unattended pipeline (e.g. seed_books.sh) so the
OAuth token is cached at data/gdrive_token.json and the pipeline can
proceed non-interactively.

Usage:
    uv run python scripts/authenticate_gdrive.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Resolve project root so imports work when invoked from any directory
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.gdrive_client import GoogleDriveClient  # noqa: E402
from src.utils.config import settings  # noqa: E402


def main() -> None:
    folder_id = settings.google_drive.folder_id
    if not folder_id:
        print("ERROR: GOOGLE_DRIVE__FOLDER_ID is not set in .env or config.")  # noqa: T201
        print("Set it and try again.")  # noqa: T201
        sys.exit(1)

    creds_file = settings.google_drive.credentials_file
    if not Path(creds_file).exists():
        print(f"ERROR: Credentials file not found: {creds_file}")  # noqa: T201
        print("Download OAuth credentials from Google Cloud Console")  # noqa: T201
        print("and save to configs/gdrive_credentials.json")  # noqa: T201
        sys.exit(1)

    print("Authenticating with Google Drive...")  # noqa: T201
    print("A browser window will open for OAuth consent.")  # noqa: T201
    print()  # noqa: T201

    client = GoogleDriveClient(
        credentials_file=settings.google_drive.credentials_file,
        token_file=settings.google_drive.token_file,
        scopes=settings.google_drive.scopes,
    )

    # Trigger auth flow by listing files
    files = client.list_files(folder_id, recursive=False)

    token_path = Path(settings.google_drive.token_file)
    if token_path.exists():
        print(f"Token saved to {token_path}")  # noqa: T201
    else:
        print("WARNING: Token file was not created. Auth may have failed.")  # noqa: T201
        sys.exit(1)

    print(f"Found {len(files)} files in configured Drive folder:")  # noqa: T201
    for f in files[:10]:
        size = int(f.get("size", 0))
        size_mb = size / (1024 * 1024) if size else 0
        print(f"  {f['name']} ({size_mb:.1f} MB)")  # noqa: T201
    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more")  # noqa: T201

    print()  # noqa: T201
    print("Authentication complete. Overnight pipeline can now run non-interactively.")  # noqa: T201


if __name__ == "__main__":
    main()
