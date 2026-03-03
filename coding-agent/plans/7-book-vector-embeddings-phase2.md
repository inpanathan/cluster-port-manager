# Plan 7 — Phase 2: Book Vector Embeddings

## Context

Phase 1 delivered the book download pipeline, catalog (SQLite), REST API, and Library UI. Phase 2 processes each cataloged book into vector embeddings stored in Qdrant, enabling RAG chat over the entire book collection.

**Infrastructure already in place:**
- Book models with `embedding_status` and `source_id` fields (`src/books/models.py`)
- `BookService` with `mark_embedding_completed(book_id, source_id)` and `mark_embedding_failed(book_id, error)`
- Embedding model (`src/models/embeddings.py`) — `SentenceTransformerEmbeddingModel` with BGE-large-en-v1.5
- Vector store wrapper (`src/utils/vector_store.py`) — Qdrant client with add/search/delete
- Text parsers (`src/data/parsers.py`) — PDF, DOCX, TXT, MD
- Chunking (`src/data/chunking.py`) — recursive character splitting
- Ingestion pipeline (`src/data/ingestion.py`) — chunk → embed → store flow for general sources
- Config: `BooksSettings.qdrant_collection = "books"`, `chunk_size=1000`, `chunk_overlap=200`, `embedding_batch_size=32`

**What Phase 2 adds:**
- Book-specific text extraction preserving chapter/section structure
- Structure-aware chunking that tags chunks with chapter, section, page info
- Dedicated embedding pipeline for books (separate from general ingestion)
- Qdrant `books` collection with rich metadata and payload indexing
- Source registration so books are queryable via existing RAG chat
- Processing script with progress tracking, incremental support, and validation

**Requirements:** REQ-LIB-006 through REQ-LIB-010, REQ-VEP-001 through REQ-VEP-008

---

## Step 1 — Book Text Extraction `[x]`

Build a book-aware text extractor that preserves document structure (chapters, sections, pages).

### 1.1 Create `src/data/book_text_extractor.py` `[x]`
- Define `BookChapter` model: `number: int`, `title: str`, `text: str`, `start_page: int | None`, `end_page: int | None`
- Define `BookStructure` model: `title: str`, `author: str`, `chapters: list[BookChapter]`, `raw_text: str`, `page_count: int`
- Implement `extract_book_text(file_path: Path, file_format: str) -> BookStructure`
  - Dispatch by format: PDF, EPUB, DOCX, TXT/MD
- **PDF extraction** (`_extract_pdf`):
  - Use `pypdf.PdfReader`, extract text page by page
  - Detect chapter boundaries using heading patterns (e.g., `^Chapter \d+`, `^\d+\.\s`, all-caps headings)
  - Map pages to chapters using the PDF outline (if available) or pattern matching
  - Preserve page numbers for each chapter
- **EPUB extraction** (`_extract_epub`):
  - Use `ebooklib` to iterate spine items
  - Parse each HTML item with BeautifulSoup, extract text preserving heading hierarchy
  - Map `<h1>`/`<h2>` tags to chapter/section boundaries
  - EPUB has no page numbers — use approximate character offsets
- **DOCX extraction** (`_extract_docx`):
  - Use `python-docx`, iterate paragraphs
  - Detect headings via `paragraph.style.name` (Heading 1, Heading 2, etc.)
  - Group paragraphs under their heading hierarchy
- **TXT/MD extraction** (`_extract_text`):
  - Split on markdown heading patterns (`^#+\s`) or blank-line-separated sections
  - Treat each heading group as a chapter
- **Fallback**: If no structure is detected, return a single chapter containing the full text

### 1.2 Write tests `[x]`
- **File:** `tests/unit/test_book_text_extractor.py`
- Test each format with small fixture files
- Test chapter detection with various heading styles
- Test fallback when no structure detected
- Test edge cases: empty file, single-page PDF, EPUB with no headings

---

## Step 2 — Structure-Aware Chunking `[x]`

Extend chunking to produce chunks tagged with structural metadata.

### 2.1 Create `src/data/book_chunking.py` `[x]`
- Define `BookChunk` model extending the base `Chunk`:
  - Inherits: `text`, `index`, `start_char`, `end_char`, `token_count`
  - Adds: `chapter_number: int | None`, `chapter_title: str | None`, `content_type: str` (chapter_text, front_matter, back_matter, etc.)
- Implement `chunk_book(book_structure: BookStructure, chunk_size: int, chunk_overlap: int) -> list[BookChunk]`
  - Chunk each chapter independently (chunks don't cross chapter boundaries)
  - Tag each chunk with its chapter number/title
  - Use the existing `chunk_text()` function internally for the actual splitting
  - Assign sequential `index` across all chapters (global chunk index)
  - Set `content_type` based on chapter position (front_matter for intro/preface, back_matter for appendix/index)

### 2.2 Write tests `[x]`
- **File:** `tests/unit/test_book_chunking.py`
- Test that chunks don't cross chapter boundaries
- Test chunk metadata is correctly assigned
- Test with single-chapter books
- Test with very short chapters (shorter than chunk_size)

---

## Step 3 — Qdrant Books Collection Setup `[x]`

Configure the dedicated `books` collection in Qdrant with appropriate indexing.

### 3.1 Modify `src/utils/vector_store.py` `[x]`
- Add method `create_books_collection(dimension: int)` that creates the `books` collection with:
  - Distance metric: cosine
  - Payload indexes on: `book_id`, `author`, `chapter_number`, `content_type`, `tags` (keyword indexes for filtered search)
  - HNSW parameters: `m=16`, `ef_construct=200` (good defaults for ~5M vectors)
- Add method `add_book_chunks(book_id: str, chunks: list, embeddings: list, metadatas: list)` — store with book-specific payload structure
- Add method `delete_book_vectors(book_id: str)` — delete all vectors for a specific book
- Add method `search_books(query_embedding, top_k, book_ids: list | None, author: str | None, chapter: int | None)` — filtered search within books collection
- Add method `validate_book_embedding(book_id: str, title: str, query_embedding)` — search for title, verify top result belongs to the book (REQ-VEP-008)

### 3.2 Write tests `[x]`
- **File:** `tests/unit/test_vector_store_books.py`
- Test collection creation with correct config
- Test add/search/delete for book vectors
- Test filtered search by book_id, author, chapter
- Test validation query

---

## Step 4 — Book Embedding Pipeline `[x]`

Orchestrate: extract → chunk → embed → store → register source.

### 4.1 Create `src/pipelines/book_embedding.py` `[x]`
- Define `BookEmbeddingPipeline` class:
  - Dependencies: `EmbeddingModel`, `VectorStore`, `BookService`, `CatalogService`, logger
  - Constructor takes these via DI (same pattern as `IngestionPipeline`)
- Implement `process_book(book_id: str, *, force: bool = False) -> BookProcessingResult`:
  1. Fetch book from `BookService` — raise if not found
  2. Check `embedding_status` — skip if COMPLETED unless `force=True` (REQ-VEP-005)
  3. If `force`, check content hash — skip if unchanged
  4. Mark `embedding_status = PROCESSING`
  5. Extract text via `extract_book_text()`
  6. Chunk via `chunk_book()`
  7. Embed in batches (batch_size from `settings.books.embedding_batch_size`) (REQ-VEP-003)
  8. Delete any existing vectors for this book (idempotent re-processing)
  9. Store in Qdrant `books` collection with metadata:
     - `book_id`, `title`, `author`, `chapter_number`, `chapter_title`, `content_type`, `chunk_index`, `start_char`, `end_char`, `tags`, `isbn`, `publication_year`, `language` (REQ-VEP-002)
  10. Create/update Source in catalog via `CatalogService` (REQ-VEP-006, REQ-LIB-010):
      - `source_type = "book"`, `title = book.title`, `origin = book.file_path`
      - Set `chunk_count`, `total_tokens`, `status = COMPLETED`
  11. Validate embedding quality (REQ-VEP-008):
      - Embed the book title as a query
      - Search top-5 results in books collection filtered to this book_id
      - Log whether the top result belongs to this book
  12. Mark `embedding_status = COMPLETED`, set `source_id`
  13. Return `BookProcessingResult` with stats (chunk_count, tokens, duration, validation_passed)
- Implement error handling:
  - On failure, mark `embedding_status = FAILED`, log error with context
  - Don't leave partial vectors — delete on failure
- Define `BookProcessingResult` model: `book_id`, `chunk_count`, `total_tokens`, `duration_ms`, `validation_passed`, `skipped`

### 4.2 Implement `process_all_books(*, force: bool = False) -> BatchResult` `[x]`
- Query all books with `embedding_status != COMPLETED` (or all if `force`)
- Process each book sequentially (GPU memory constraint)
- Log progress: `"book_embedding_progress"`, `completed=N`, `total=M`, `current_book=title`
- Return `BatchResult`: `total`, `completed`, `failed`, `skipped`, `errors: list`

### 4.3 Write tests `[x]`
- **File:** `tests/unit/test_book_embedding_pipeline.py`
- Test happy path: book → extracted → chunked → embedded → stored → source created
- Test skip when already completed
- Test force re-processing
- Test failure handling (cleanup on error)
- Test batch processing with mixed statuses

---

## Step 5 — Processing Script `[x]`

CLI script for running the embedding pipeline.

### 5.1 Create `scripts/process_books.py` `[x]`
- Parse args: `--book-id <ID>` (single book), `--force` (re-process completed), `--dry-run` (show what would be processed)
- Initialize dependencies (embedding model, vector store, services)
- Ensure Qdrant `books` collection exists (create if not)
- Call `process_book()` or `process_all_books()`
- Print summary: books processed, chunks created, time elapsed, any failures
- Exit with non-zero code if any books failed

### 5.2 Update `scripts/seed_books.sh` `[x]`
- Add embedding step after download+catalog:
  ```bash
  echo "Step 3: Embedding books..."
  uv run python scripts/process_books.py
  ```
- Add `--skip-embed` flag to skip embedding step

### 5.3 Write test `[x]`
- **File:** `tests/unit/test_process_books_script.py`
- Test argument parsing
- Test dry-run mode

---

## Step 6 — API Enhancements `[x]`

Add embedding-related endpoints and update existing ones.

### 6.1 Modify `src/api/routes.py` `[x]`
- Add `POST /books/{book_id}/embed` — trigger embedding for a single book
  - Request body: `{ "force": false }`
  - Returns: `BookProcessingResult`
  - Runs synchronously (books are processed one at a time)
- Add `GET /books/{book_id}/status` — return processing status
  - Response: `{ "embedding_status": "completed", "chunk_count": 142, "source_id": "..." }`
- Update `GET /books` — include `chunk_count` in list response
- Update `DELETE /books/{book_id}` — also delete vectors from Qdrant books collection

### 6.2 Update `src/api/schemas.py` `[x]`
- Add `BookEmbedRequest` model
- Add `BookProcessingStatusResponse` model
- Update `BookSummaryResponse` to include `chunk_count`

### 6.3 Register pipeline in `src/api/dependencies.py` `[x]`
- Add `BookEmbeddingPipeline` to `ServiceContainer`
- Wire dependencies (embedding model, vector store, book service, catalog service)

### 6.4 Write tests `[x]`
- **File:** `tests/integration/test_book_embedding_api.py`
- Test embed endpoint triggers processing
- Test status endpoint returns correct state
- Test delete cleans up vectors

---

## Step 7 — Frontend Updates `[x]`

Show embedding progress and chunk count in the Library UI.

### 7.1 Update `frontend/src/features/library/BookCard.tsx` `[x]`
- Add chunk count badge when `embedding_status === "completed"`
- Show "Processing..." spinner when `embedding_status === "processing"`

### 7.2 Update `frontend/src/features/library/BookDetail.tsx` `[x]`
- Add "Embed" button that calls `POST /books/{id}/embed`
- Show chunk count and source_id when embedding is complete
- Show error message when embedding has failed

### 7.3 Update `frontend/src/features/library/LibraryPage.tsx` `[x]`
- Add library stats bar: total books, embedded count, total chunks
- Add "Embed All" button (calls embed for each pending book)

### 7.4 Update `frontend/src/api/types.ts` and `frontend/src/api/books.ts` `[x]`
- Add `embedBook(bookId, force)` API function
- Add `getBookStatus(bookId)` API function
- Update `BookSummary` type with `chunk_count`

---

## Step 8 — RAG Integration `[x]`

Ensure embedded books are queryable through existing chat/Q&A/summarization features.

### 8.1 Modify `src/pipelines/rag.py` `[x]`
- Update `query()` to optionally search the `books` collection alongside `knowledge_hub`
- Add `include_books: bool = True` parameter
- Merge and re-rank results from both collections by score
- Include book-specific metadata in citations (chapter, page)

### 8.2 Update chat/Q&A/summarize endpoints `[x]`
- Pass `include_books` flag through to RAG pipeline
- Update citation format to show book title + chapter when source is a book

### 8.3 Write tests `[x]`
- **File:** `tests/integration/test_book_rag.py`
- Test RAG query returns results from books collection
- Test citation includes book metadata
- Test filtering with and without books

---

## Step 9 — Documentation & Cleanup `[x]`

### 9.1 Update `docs/app_cheatsheet.md` `[x]`
- Add `POST /books/{id}/embed` and `GET /books/{id}/status` endpoints
- Add `scripts/process_books.py` commands
- Update seed_books.sh documentation

### 9.2 Update `docs/troubleshooting.md` `[x]`
- Add section on embedding failures (OOM, Qdrant connection, empty text)

### 9.3 Run full quality checks `[x]`
- `bash scripts/check_all.sh` — lint, format, typecheck, tests all pass

---

## Acceptance Criteria

1. Running `uv run python scripts/process_books.py` processes all pending books end-to-end
2. Each processed book has embeddings in the Qdrant `books` collection with chapter/section metadata
3. Each processed book is registered as a Source in the catalog with `source_id` linked
4. RAG chat can answer questions using book content with correct citations (title + chapter)
5. `embedding_status` correctly tracks progress (pending → processing → completed/failed)
6. Incremental processing: re-running skips already-completed books unless `--force`
7. Library UI shows embedding status, chunk count, and offers an embed action
8. All existing tests continue to pass; new tests cover the pipeline
