# Plan: Knowledge Hub — API Wiring, Redis Caching, and Full Test Suite

## Context

All backend service modules are implemented (ingestion, catalog, RAG, chat, interview, Q&A, summarization) but are entirely disconnected from the API layer. `src/api/routes.py` is empty — zero endpoints. `main.py` has no service initialization. Chat, interview, and Q&A sessions use in-memory Python dicts and are lost on restart. There is only 1 test (health check). Two bugs exist in the ingestion pipeline.

**This plan wires everything together:** fixes bugs, adds Redis caching with configurable TTL, creates the DI container, implements all 21 API endpoints, and writes comprehensive tests — across 8 phases, each producing a working, testable increment.

---

## Status

- [x] Phase 0: Foundation — Bug Fixes, Redis, Cache Layer, Test Infrastructure
- [x] Phase 1: App Lifespan + Dependency Injection
- [x] Phase 2: Source Ingestion + Catalog API Endpoints
- [x] Phase 3: RAG Chat API + Redis-backed Sessions
- [x] Phase 4: Summarization API
- [x] Phase 5: Q&A Generation API + Redis-backed Sets
- [x] Phase 6: Interview Preparation API + Redis-backed Sessions
- [x] Phase 7: Full Integration Verification + Cleanup

---

## Changes Summary

| Phase | New Files | Modified Files | Tests |
|-------|-----------|----------------|-------|
| 0 | `src/utils/cache.py`, `tests/conftest.py`, `tests/unit/test_cache.py` | `src/data/ingestion.py`, `src/data/parsers.py`, `pyproject.toml`, `src/utils/config.py`, `src/features/chat.py`, `src/features/interview.py`, `src/features/qna.py`, `.env.example` | 6 |
| 1 | `src/api/dependencies.py` | `main.py` | 2 |
| 2 | `src/api/schemas.py`, `tests/unit/test_ingestion.py`, `tests/integration/test_sources.py` | `src/api/routes.py` | ~18 |
| 3 | `tests/unit/test_chat.py`, `tests/integration/test_chat.py` | `src/api/routes.py`, `src/features/chat.py` | ~12 |
| 4 | `tests/unit/test_summarization.py`, `tests/integration/test_summarization.py` | `src/api/routes.py` | ~8 |
| 5 | `tests/unit/test_qna.py`, `tests/integration/test_qna.py` | `src/api/routes.py` | ~11 |
| 6 | `tests/unit/test_interview.py`, `tests/integration/test_interview.py` | `src/api/routes.py` | ~11 |
| 7 | `tests/integration/test_e2e_flow.py` | `docs/app_cheatsheet.md`, `.env.example` | 1 |

**Totals: ~15 new files, ~13 modified files, ~69 tests**

---

## Phase 0: Foundation — Bug Fixes, Redis, Cache Layer, Test Infrastructure

Everything subsequent depends on this phase.

### 0.1 Fix bug: `ingest_text()` missing duplicate check
**File:** `src/data/ingestion.py` (line ~250)

After `content_hash = compute_content_hash(content)`, add duplicate detection matching the pattern in `ingest_file()` and `ingest_url()`:
```python
duplicate = self._catalog.find_duplicate(content_hash)
if duplicate:
    self._catalog.mark_failed(source.id, f"Duplicate of '{duplicate.title}' ({duplicate.id})")
    return IngestionResult(source_id=source.id, status="duplicate", error=f"Duplicate of {duplicate.id}")
```

### 0.2 Fix bug: `ingest_url()` double HTTP fetch
**Files:** `src/data/parsers.py`, `src/data/ingestion.py`

Currently `parse_url()` and `get_raw_content_for_url()` each make a separate HTTP request. Create `fetch_and_parse_url(url, *, timeout) -> tuple[str, str]` that fetches once, returns `(extracted_text, raw_html)`. Update `ingest_url()` to use it. Keep original functions for backward compatibility.

### 0.3 Add Redis dependency
**File:** `pyproject.toml`

Add `"redis[hiredis]>=5.0.0"` to dependencies. Run `uv sync --extra dev`.

### 0.4 Add `RedisSettings` to config
**File:** `src/utils/config.py`

```python
class RedisSettings(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    default_ttl_days: int = 7
    url: str = ""

    @property
    def connection_url(self) -> str:
        if self.url:
            return self.url
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"
```

Add `redis: RedisSettings = Field(default_factory=RedisSettings)` to `Settings`.

### 0.5 Create cache abstraction
**New file:** `src/utils/cache.py`

- `CacheStore` Protocol: `get(key) -> dict | None`, `set(key, value, *, ttl_seconds)`, `delete(key)`, `keys(pattern)`
- `RedisCacheStore`: Redis-backed with JSON serialization, `setex` for TTL, `scan_iter` for keys listing, `default=str` in `json.dumps` for datetime handling
- `InMemoryCacheStore`: Dict-backed fallback for testing (no real TTL enforcement)
- `create_cache_store(backend, redis_url, default_ttl_days)` factory: returns `InMemoryCacheStore` when `backend == "mock"`, `RedisCacheStore` otherwise
- TTL stored as seconds internally; config exposes `default_ttl_days` for readability

### 0.6 Modify feature services to use CacheStore
**Files:** `src/features/chat.py`, `src/features/interview.py`, `src/features/qna.py`

Replace `self._sessions: dict[str, X] = {}` with `self._cache: CacheStore` injected via constructor. Add `to_dict()` / `from_dict()` serialization methods to dataclasses. Key namespaces: `chat:{id}`, `interview:{id}`, `qna:{id}`.

Constructor changes:
- `ChatService.__init__(self, rag_pipeline, cache: CacheStore)`
- `InterviewService.__init__(self, llm_client, vector_store, embedding_model, catalog, cache: CacheStore)`
- `QnAService.__init__(self, llm_client, vector_store, embedding_model, catalog, cache: CacheStore)`

### 0.7 Create root test conftest
**New file:** `tests/conftest.py`

Override env vars before app imports (REQ-TST-051): `APP_ENV=test`, `MODEL_BACKEND=mock`. Shared fixtures: `tmp_dir`, `cache_store` (InMemoryCacheStore), `embedding_model` (Mock), `llm_client` (Mock), `catalog_repo`, `catalog_service`, `file_store`, `vector_store`, `ingestion_pipeline`, `rag_pipeline`.

### 0.8 Unit tests for cache
**New file:** `tests/unit/test_cache.py`

Tests: `test_set_and_get`, `test_get_missing_returns_none`, `test_delete`, `test_keys_all`, `test_keys_prefix_pattern`, `test_datetime_serialization`.

### 0.9 Update `.env.example`
Add Redis variables: `REDIS__HOST`, `REDIS__PORT`, `REDIS__DB`, `REDIS__PASSWORD`, `REDIS__DEFAULT_TTL_DAYS`.

**Acceptance:** `uv run pytest tests/unit/test_cache.py -x -q` passes. Feature service constructors accept `cache: CacheStore`.

---

## Phase 1: App Lifespan + Dependency Injection

### 1.1 Create service container
**New file:** `src/api/dependencies.py`

- `ServiceContainer` dataclass holding all initialized service instances
- `init_services()` creates everything using `settings` and factories (`create_embedding_model`, `create_llm_client`, `create_cache_store`)
- Module-level singleton `_container`
- FastAPI `Depends()` accessor functions: `get_ingestion()`, `get_catalog()`, `get_file_store()`, `get_chat()`, `get_interview()`, `get_qna()`, `get_summarization()`, `get_vector_store()`
- `shutdown_services()` for cleanup

### 1.2 Wire main.py lifespan
**File:** `main.py`

- Replace TODO comments in `lifespan()` with `init_services()` / `shutdown_services()`
- Update app title to "Knowledge Hub"
- Expand `_error_code_to_status()` to map all `ErrorCode` values: `SOURCE_NOT_FOUND` → 404, `FILE_NOT_FOUND` → 404, `SESSION_NOT_FOUND` → 404, `UNSUPPORTED_FORMAT` → 415, `FILE_TOO_LARGE` → 413, `DUPLICATE_SOURCE` → 409

### 1.3 Integration test
**File:** `tests/integration/test_api.py` (add to existing)

`test_app_starts_with_services_initialized` — verify `get_container()` returns populated container.

**Acceptance:** App starts with mock backend. Health check passes. `get_container()` returns all services.

---

## Phase 2: Source Ingestion + Catalog API Endpoints

Covers REQ-PRJ-001 through REQ-PRJ-004, REQ-PRJ-006, REQ-PRJ-011, REQ-ING-001 through REQ-ING-014, REQ-CAT-001 through REQ-CAT-006.

### 2.1 Define API schemas
**New file:** `src/api/schemas.py`

All Pydantic request/response models, separate from internal models. Includes: `IngestionResponse`, `FolderIngestionResponse`, `UrlIngestionRequest`, `TextIngestionRequest`, `FolderIngestionRequest`, `SourceUpdateRequest`, plus schemas for chat, interview, Q&A, and summarization (defined here, used in later phases).

### 2.2 Implement source ingestion endpoints
**File:** `src/api/routes.py`

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/sources/upload` | POST | Multipart: `UploadFile` + `Form` fields |
| `/sources/url` | POST | JSON body `UrlIngestionRequest` |
| `/sources/text` | POST | JSON body `TextIngestionRequest` |
| `/sources/folder` | POST | JSON body `FolderIngestionRequest` |

### 2.3 Implement catalog CRUD endpoints
**File:** `src/api/routes.py`

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/sources` | GET | Query params for filters (type, status, tag, search, limit, offset) |
| `/sources/{id}` | GET | Returns full source detail |
| `/sources/{id}` | PUT | JSON body `SourceUpdateRequest` |
| `/sources/{id}` | DELETE | Cascades: vectors → file store → catalog |
| `/sources/{id}/reindex` | POST | Re-ingest from stored original |

### 2.4 Implement document viewer endpoints
**File:** `src/api/routes.py`

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/sources/{id}/original` | GET | `Response` with correct `Content-Type`, `Content-Disposition: attachment` |
| `/sources/{id}/view` | GET | Inline rendering (PDF: inline, text: text/html) |

### 2.5 Tests
**New files:** `tests/unit/test_ingestion.py`, `tests/integration/test_sources.py`

Unit (~8): `test_ingest_text_happy_path`, `test_ingest_text_duplicate_detection`, `test_ingest_file_happy_path`, `test_ingest_url_single_fetch`, `test_ingest_folder_happy_path`, `test_reindex_source`, `test_ingest_file_empty_content`, `test_ingest_file_unsupported_format`.

Integration (~10): `test_upload_file`, `test_ingest_text`, `test_ingest_url`, `test_list_sources`, `test_get_source`, `test_get_source_not_found_404`, `test_update_source`, `test_delete_source_204`, `test_reindex_source`, `test_download_original`.

**Acceptance:** All 11 source endpoints respond correctly. Upload TXT → `status=completed`. Catalog CRUD works E2E.

---

## Phase 3: RAG Chat API + Redis-backed Sessions

Covers REQ-PRJ-007, REQ-CHT-001 through REQ-CHT-007.

### 3.1 Adjust ChatService return type
**File:** `src/features/chat.py`

`send_message()` currently returns only the assistant `ChatMessage`. Change to return `(session_id, ChatMessage)` so the route handler knows which session was used when a new one is auto-created.

### 3.2 Implement chat endpoints
**File:** `src/api/routes.py`

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/chat` | POST | Creates or continues session, returns answer + citations |
| `/chat/sessions` | GET | List all sessions |
| `/chat/sessions/{id}` | GET | Full session with message history |

### 3.3 Tests
**New files:** `tests/unit/test_chat.py`, `tests/integration/test_chat.py`

Unit (~6): `test_create_session`, `test_send_message`, `test_session_from_cache`, `test_list_sessions`, `test_session_not_found`, `test_multi_turn`.

Integration (~6): `test_chat_no_sources`, `test_chat_after_ingestion`, `test_chat_multi_turn`, `test_list_sessions`, `test_get_session_detail`, `test_session_not_found_404`.

**Acceptance:** `POST /chat` returns answer with citations. Sessions persist in cache across requests.

---

## Phase 4: Summarization API

Covers REQ-PRJ-010, REQ-SUM-001 through REQ-SUM-006.

### 4.1 Implement summarization endpoint
**File:** `src/api/routes.py`

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/summarize` | POST | Accepts `source_ids` or `topic`, mode `short`/`detailed` |

### 4.2 Tests
**New files:** `tests/unit/test_summarization.py`, `tests/integration/test_summarization.py`

Unit (~5): `test_summarize_sources_short`, `test_summarize_sources_detailed`, `test_summarize_topic`, `test_no_params_raises`, `test_no_content_raises`.

Integration (~3): `test_summarize_source`, `test_summarize_topic`, `test_summarize_no_params_400`.

**Acceptance:** Both `source_ids` and `topic` modes work. Short vs detailed produce different output.

---

## Phase 5: Q&A Generation API + Redis-backed Sets

Covers REQ-PRJ-009, REQ-QNA-001 through REQ-QNA-006.

### 5.1 Implement Q&A endpoints
**File:** `src/api/routes.py`

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/qna/generate` | POST | Generate Q&A pairs from topic or sources |
| `/qna/{id}` | GET | Retrieve a generated Q&A set |
| `/qna/{id}/export` | POST | Export as JSON or Markdown `Response` |

### 5.2 Tests
**New files:** `tests/unit/test_qna.py`, `tests/integration/test_qna.py`

Unit (~6): `test_generate_with_topic`, `test_generate_with_sources`, `test_requires_topic_or_sources`, `test_get_from_cache`, `test_export_json`, `test_export_markdown`.

Integration (~5): `test_generate_returns_pairs`, `test_get_set`, `test_export_json`, `test_export_markdown`, `test_nonexistent_set_404`.

**Acceptance:** Q&A sets persist in cache. Export works for both formats.

---

## Phase 6: Interview Preparation API + Redis-backed Sessions

Covers REQ-PRJ-008, REQ-INT-001 through REQ-INT-007.

### 6.1 Implement interview endpoints
**File:** `src/api/routes.py`

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/interview/start` | POST | Start session, generate questions, return first question |
| `/interview/{id}/answer` | POST | Submit answer, return feedback + next question |
| `/interview/{id}/summary` | GET | Overall score after session completion |

### 6.2 Tests
**New files:** `tests/unit/test_interview.py`, `tests/integration/test_interview.py`

Unit (~7): `test_start_generates_questions`, `test_submit_answer_returns_feedback`, `test_answer_advances_index`, `test_session_completes`, `test_submit_to_completed_raises`, `test_get_summary`, `test_session_not_found`.

Integration (~4): `test_start_interview`, `test_submit_answer`, `test_full_interview_flow`, `test_not_found_404`.

**Acceptance:** Full interview flow works: start → answer all → get summary with scores.

---

## Phase 7: Full Integration Verification + Cleanup

### 7.1 End-to-end flow test
**New file:** `tests/integration/test_e2e_flow.py`

Single test exercising the full happy path:
1. `POST /sources/upload` a text file
2. `GET /sources` — verify it appears
3. `GET /sources/{id}` — verify detail
4. `GET /sources/{id}/original` — download
5. `POST /chat` — ask about content, verify citations
6. `POST /summarize` — summarize it
7. `POST /qna/generate` — generate Q&A pairs
8. `GET /qna/{id}` — retrieve the set
9. `POST /interview/start` — start interview
10. `DELETE /sources/{id}` — delete it
11. `GET /sources` — verify gone

### 7.2 Update app cheatsheet
**File:** `docs/app_cheatsheet.md` — fill in API Endpoints table with all 21 endpoints.

### 7.3 Run full quality checks
```bash
bash scripts/check_all.sh
```

### 7.4 Update `.env.example`
Ensure all Redis and LLM variables are documented.

**Acceptance:** E2E test passes. `bash scripts/check_all.sh` passes. All 21 endpoints documented.

---

## Key Architectural Decisions

1. **DI pattern**: Module-level `ServiceContainer` singleton initialized in lifespan, accessed via `Depends(get_X)`. Simple, testable (`app.dependency_overrides`), no DI framework.

2. **Cache key namespacing**: `chat:{id}`, `interview:{id}`, `qna:{id}` — avoids collisions, enables `keys("chat:*")` for listing.

3. **Schema separation**: API schemas in `src/api/schemas.py`, internal models in `src/catalog/models.py`. No internal fields leak.

4. **Thin routes**: Each endpoint validates input → calls service → converts result. No business logic in routes.

5. **Cache fallback**: `InMemoryCacheStore` for `model_backend=mock` and all tests. `RedisCacheStore` for local/cloud. Same interface via factory.

6. **Configurable TTL**: `settings.redis.default_ttl_days` (default 7 days). Stored as seconds internally. Overridable per set/session if needed.

7. **Single HTTP fetch**: `fetch_and_parse_url()` replaces the two-call URL ingestion pattern.

8. **Test isolation**: Root conftest overrides `APP_ENV=test`, `MODEL_BACKEND=mock` before imports (REQ-TST-051). Temp dirs for all data stores.

---

## Critical Files

| File | Role |
|------|------|
| `src/api/routes.py` | Currently empty — will contain all 21 endpoints |
| `src/api/dependencies.py` | New — DI container, service initialization |
| `src/api/schemas.py` | New — all Pydantic request/response models |
| `src/utils/cache.py` | New — Redis/in-memory cache abstraction |
| `src/utils/config.py` | Add `RedisSettings` nested class |
| `src/data/ingestion.py` | Fix 2 bugs, core pipeline wired to endpoints |
| `src/data/parsers.py` | Add `fetch_and_parse_url()` |
| `src/features/chat.py` | Replace in-memory dict → CacheStore |
| `src/features/interview.py` | Replace in-memory dict → CacheStore |
| `src/features/qna.py` | Replace in-memory dict → CacheStore |
| `main.py` | Wire lifespan, expand error mapping |
| `tests/conftest.py` | Root test config with shared fixtures |

---

## Verification

After all phases:
1. `bash scripts/check_all.sh` — lint, format, typecheck, all tests pass
2. `uv run pytest tests/ -x -q` — ~69 tests pass
3. `uv run pytest tests/integration/test_e2e_flow.py -v` — full flow test passes
4. Start server: `MODEL_BACKEND=mock uv run python main.py` — verify `/docs` shows all endpoints
5. `curl http://localhost:8000/health` — returns `{"status": "ok"}`
6. All 21 endpoints listed in `docs/app_cheatsheet.md`
