#!/usr/bin/env bash
# Seed the book library from Google Drive.
#
# Usage:
#   bash scripts/seed_books.sh             # run full download
#   bash scripts/seed_books.sh --dry-run   # list without downloading
#   bash scripts/seed_books.sh status      # show catalog stats
#
# Requires: uv sync --extra dev --extra books

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Load .env if present
if [[ -f ".env" ]]; then
    set -a
    # shellcheck source=/dev/null
    source .env
    set +a
fi

# Pre-flight: verify Google Drive token exists (avoid hanging on OAuth browser flow)
TOKEN_FILE="${GOOGLE_DRIVE__TOKEN_FILE:-data/gdrive_token.json}"
if [[ ! -f "$TOKEN_FILE" ]]; then
    echo "ERROR: Google Drive token not found at $TOKEN_FILE"
    echo "Run the interactive auth first:"
    echo "  uv run python scripts/authenticate_gdrive.py"
    exit 1
fi

SKIP_EMBED=false
SKIP_GRAPH=false

# Parse flags
POSITIONAL=()
for arg in "$@"; do
    case "$arg" in
        --skip-embed)
            SKIP_EMBED=true
            ;;
        --skip-graph)
            SKIP_GRAPH=true
            ;;
        *)
            POSITIONAL+=("$arg")
            ;;
    esac
done
set -- "${POSITIONAL[@]}"

case "${1:-run}" in
    status)
        echo "=== Book Library Status ==="
        uv run python -c "
import sys; sys.path.insert(0, '.')
from src.books.repository import BookRepository
from src.utils.config import settings
repo = BookRepository(settings.books.database_path)
books, total = repo.list_books(limit=0)
_, pending = repo.list_books(embedding_status='pending', limit=0)
_, completed = repo.list_books(embedding_status='completed', limit=0)
print(f'  Total books:        {total}')
print(f'  Embeddings pending: {pending}')
print(f'  Embeddings done:    {completed}')
"
        ;;
    --dry-run)
        echo "=== Dry Run: Listing Drive files ==="
        uv run python scripts/download_books.py --dry-run
        ;;
    run)
        echo "=== Step 1: Downloading books from Google Drive ==="
        uv run python scripts/download_books.py "${@:2}"
        echo ""

        if [[ "$SKIP_EMBED" == "false" ]]; then
            echo "=== Step 2: Embedding books ==="
            uv run python scripts/process_books.py
            echo ""
        else
            echo "=== Skipping embedding (--skip-embed) ==="
        fi

        if [[ "$SKIP_GRAPH" == "false" && "$SKIP_EMBED" == "false" ]]; then
            echo "=== Step 3: Building knowledge graph ==="
            uv run python scripts/build_knowledge_graph.py
            echo ""
        else
            echo "=== Skipping graph (--skip-graph or --skip-embed) ==="
        fi

        echo "=== Seeding complete. Run 'bash scripts/seed_books.sh status' to verify. ==="
        ;;
    *)
        echo "Usage: $0 {run|--dry-run|status} [--skip-embed] [--skip-graph]"
        exit 1
        ;;
esac
