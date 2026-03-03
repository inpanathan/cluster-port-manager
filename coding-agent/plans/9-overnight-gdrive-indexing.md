# Plan 9: Overnight Google Drive Indexing

## Context

The user wants to run the full book pipeline overnight: download from Google Drive → embed into Qdrant → build knowledge graph in Neo4j. Infrastructure is mostly ready (Qdrant, Neo4j running), but two blockers exist:

1. **Port conflict**: vLLM defaults to port 8000 which is occupied by the FastAPI app. Need to move vLLM to port 8001.
2. **OAuth token**: Google Drive requires first-time browser authentication. No token exists yet — the pipeline will hang overnight waiting for browser input.

## Steps

### Step 1: Move vLLM default port to 8001 `[x]`

Update all references from port 8000 to 8001 for vLLM:

| File | Change |
|------|--------|
| `scripts/start_vllm.sh` (line 28) | Default `8000` → `8001` |
| `src/utils/config.py` (line 66) | `LLMSettings.vllm_base_url` default → `localhost:8001/v1` |
| `configs/local.yaml` (line 13) | `vllm_base_url` → `localhost:8001/v1` |
| `.env` (line 23) | Comment → `localhost:8001/v1` |
| `.env.example` (line 23) | Comment → `localhost:8001/v1` |
| `tests/unit/test_llm.py` (lines 25, 50) | Test URLs → `localhost:8001/v1` |

All downstream code (`dependencies.py`, `build_knowledge_graph.py`, `llm.py`) reads from `settings.llm.vllm_base_url` — no changes needed there.

### Step 2: Create standalone GDrive auth script `[x]`

Create `scripts/authenticate_gdrive.py` that:
- Initializes `GoogleDriveClient` and triggers the OAuth browser flow
- Saves the token to `data/gdrive_token.json`
- Lists files in the configured folder as a verification
- Exits cleanly so the overnight pipeline can run non-interactively

### Step 3: Add pre-flight check to seed_books.sh `[x]`

Add a check at the top of `seed_books.sh` that verifies `data/gdrive_token.json` exists before proceeding. Fail fast with a clear message pointing to `scripts/authenticate_gdrive.py` instead of hanging.

### Step 4: Update docs `[x]`

- Update `docs/app_cheatsheet.md` — add vLLM port 8001, document the auth script
- Update VLLM_PORT references in cheatsheet configuration table

### Step 5: Run tests `[x]`

Run `uv run pytest tests/ -x -q` to verify nothing is broken.

### Step 6: Authenticate & launch overnight `[ ]`

1. Run `uv run python scripts/authenticate_gdrive.py` (interactive — browser auth)
2. Start vLLM on port 8001: `bash scripts/start_vllm.sh`
3. Kick off pipeline in background: `nohup bash scripts/seed_books.sh run > data/seed_books.log 2>&1 &`

## Files to create/modify

- **Modify**: `scripts/start_vllm.sh`, `src/utils/config.py`, `configs/local.yaml`, `.env`, `.env.example`, `tests/unit/test_llm.py`, `scripts/seed_books.sh`, `docs/app_cheatsheet.md`
- **Create**: `scripts/authenticate_gdrive.py`

## Verification

1. `uv run pytest tests/ -x -q` — all tests pass
2. `uv run python scripts/authenticate_gdrive.py` — token saved, files listed
3. `bash scripts/start_vllm.sh` — starts on port 8001
4. `curl http://localhost:8001/v1/models` — vLLM responds
5. Pipeline runs unattended via `seed_books.sh`
