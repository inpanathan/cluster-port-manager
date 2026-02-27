# Project Specification — Knowledge Hub

## 1. Goal

- Build a **Knowledge Hub** — a RAG (Retrieval-Augmented Generation) application where users can ingest documents, web pages, and text content, then interact with the indexed knowledge through chat, interview preparation, Q&A generation, and summarization.
- Solve the problem of fragmented knowledge: users accumulate information across PDFs, articles, and web pages but lack a unified system to query, review, and learn from that material.

## 2. Deliverables

- A working web application (FastAPI backend, browser-based frontend) with:
  - Document ingestion pipeline (upload files, provide URLs, paste content, scan local/cloud folders).
  - RAG-powered conversational chat over indexed content.
  - Interview preparation mode with guided question flows.
  - Automatic Q&A generation on topics from the knowledge base.
  - Content summarization (short and detailed).
  - Source catalog with metadata and management UI.
  - In-browser document viewer for reading indexed content in original format.
- Backend API endpoints for all features.
- Structured logging, observability, and error handling per common requirements.
- Test suite (unit, integration, evaluation).
- Documentation: README, architecture overview, API docs, runbook.

## 3. High-Level Requirements

### v1 — Must Have

- [ ] **REQ-PRJ-001**: Users can upload documents (PDF, DOCX, TXT, Markdown) for indexing.
- [ ] **REQ-PRJ-002**: Users can provide a publicly accessible URL for the system to fetch and index.
- [ ] **REQ-PRJ-003**: Users can paste or type raw text/content directly for indexing.
- [ ] **REQ-PRJ-004**: Users can select a local folder; the system recursively indexes all supported documents in that folder and its subfolders.
- [ ] **REQ-PRJ-005**: Users can connect a cloud storage folder (Google Drive, Dropbox, OneDrive, S3) and the system recursively indexes all supported documents within it.
- [ ] **REQ-PRJ-006**: All indexed documents are stored in their original format and available for the user to read/download at any time.
- [ ] **REQ-PRJ-007**: Users can chat with the system and ask questions grounded in indexed content (RAG).
- [ ] **REQ-PRJ-008**: Users can request interview preparation on a topic; the system generates realistic interview questions and evaluates answers.
- [ ] **REQ-PRJ-009**: Users can ask the system to generate Q&A pairs on a topic from indexed content.
- [ ] **REQ-PRJ-010**: Users can produce a short or detailed summary of any indexed source or a selected topic.
- [ ] **REQ-PRJ-011**: The system maintains a searchable catalog of all indexed sources with metadata.

### v2 — Nice to Have

- [ ] **REQ-PRJ-012**: Users can provide authenticated/private URLs (behind login) with credentials or cookies for fetching.
- [ ] **REQ-PRJ-013**: Multi-user support with per-user knowledge bases and authentication.
- [ ] **REQ-PRJ-014**: Scheduled re-indexing of URL-based and folder-based sources to capture updates.
- [ ] **REQ-PRJ-015**: Export Q&A sets and summaries as PDF or Markdown files.
- [ ] **REQ-PRJ-016**: Tagging and folder organization for sources in the catalog.

## 4. Functional Requirements

### Feature 1: Content Ingestion

- [ ] **REQ-ING-001**: Accept file uploads via multipart form POST. Supported formats: PDF, DOCX, TXT, MD. Maximum file size: configurable (default 50 MB).
- [ ] **REQ-ING-002**: Accept a URL; fetch the page content using an HTTP client with configurable timeout. Extract readable text (strip nav, ads, boilerplate) using a readability parser.
- [ ] **REQ-ING-003**: Accept raw text/content pasted by the user via a text input endpoint.
- [ ] **REQ-ING-004**: Accept a local folder path; recursively discover all supported files (PDF, DOCX, TXT, MD) in the folder and its subfolders and ingest each as a separate source. Preserve the relative folder structure as metadata on each source.
- [ ] **REQ-ING-005**: Accept a cloud storage folder reference (Google Drive, Dropbox, OneDrive, or S3 bucket prefix). Authenticate via OAuth or API key, list contents recursively, download supported files, and ingest each as a separate source.
- [ ] **REQ-ING-006**: For folder ingestion (local or cloud), report per-file status (success/failure/skipped) and an overall batch summary. Skip unsupported file types with a warning rather than failing the entire batch.
- [ ] **REQ-ING-007**: Store the original file (binary) for every ingested source so it can be retrieved and read in its original format. For URL sources, store a snapshot of the fetched HTML/content. For pasted text, store the raw text.
- [ ] **REQ-ING-008**: For each ingested source, extract text and split into chunks using a configurable chunking strategy (default: recursive character splitting, chunk size 1000 tokens, overlap 200 tokens).
- [ ] **REQ-ING-009**: Compute embeddings for each chunk using a configurable embedding model (default: a sentence-transformer model).
- [ ] **REQ-ING-010**: Store chunks and their embeddings in a vector store (default: ChromaDB or FAISS with metadata persistence).
- [ ] **REQ-ING-011**: Create a catalog entry for each ingested source with metadata (see Feature 6).
- [ ] **REQ-ING-012**: Return a processing status to the user (queued, processing, completed, failed) for each ingestion job. For folder ingestion, return per-file and aggregate status.
- [ ] **REQ-ING-013**: Handle duplicate detection — warn if a URL or file with the same hash has already been indexed. For folder ingestion, skip duplicates and report them.
- [ ] **REQ-ING-014**: Support re-indexing a source (delete old chunks, re-ingest from scratch). For folder sources, support re-indexing the entire folder (detect added/removed/changed files).

**Edge cases:**
- Unsupported file formats: return clear error with list of supported formats.
- URL fetch failures (timeout, 404, paywall): return error with status code and reason.
- Empty documents or documents with only images (no extractable text): return warning.
- Very large documents: chunk progressively, report progress.
- Folder with thousands of files: process in batches, report progress, allow cancellation.
- Folder with mixed supported/unsupported files: ingest supported files, skip others with warnings.
- Symlinks and circular directory references: detect and skip with warning.
- Cloud storage auth failures: return clear error with re-auth instructions.
- Cloud folder permissions: skip files the user lacks read access to, report them.

### Feature 2: RAG Chat

- [ ] **REQ-CHT-001**: Accept a user question via chat endpoint. Retrieve top-k relevant chunks from the vector store using semantic similarity search.
- [ ] **REQ-CHT-002**: Construct a prompt with the retrieved context and the user question, then send to an LLM for answer generation.
- [ ] **REQ-CHT-003**: Return the generated answer along with source citations (source title, chunk excerpt, relevance score).
- [ ] **REQ-CHT-004**: Support multi-turn conversation with chat history (maintain session context).
- [ ] **REQ-CHT-005**: Allow the user to filter which sources to include in retrieval (e.g., by source ID, tags, or date range).
- [ ] **REQ-CHT-006**: Support configurable retrieval parameters: top-k (default 5), similarity threshold, and reranking.
- [ ] **REQ-CHT-007**: When no relevant context is found, clearly indicate that the answer is not grounded in indexed content rather than hallucinating.

**Edge cases:**
- Questions unrelated to indexed content: respond with a disclaimer.
- Ambiguous queries: ask clarifying questions or provide best-effort answer with caveats.
- Very long chat history: summarize older turns to fit context window.

### Feature 3: Interview Preparation

- [ ] **REQ-INT-001**: Accept a topic or role description from the user. Generate a set of interview questions (configurable count, default 10) grounded in indexed content relevant to that topic.
- [ ] **REQ-INT-002**: Support different interview modes: behavioral, technical, mixed.
- [ ] **REQ-INT-003**: Present questions one at a time in an interactive session. Accept the user's answer for each question.
- [ ] **REQ-INT-004**: Evaluate the user's answer against the indexed content and provide feedback: strengths, areas for improvement, and a suggested model answer.
- [ ] **REQ-INT-005**: At the end of a session, provide an overall assessment with scores and recommendations.
- [ ] **REQ-INT-006**: Allow the user to specify difficulty level (beginner, intermediate, advanced).
- [ ] **REQ-INT-007**: Allow the user to save and revisit past interview sessions.

**Edge cases:**
- Topic not covered by indexed content: inform user and suggest indexing relevant material first.
- Very short or off-topic answers: provide constructive feedback without penalizing excessively.

### Feature 4: Q&A Generation

- [ ] **REQ-QNA-001**: Accept a topic or source selection from the user. Generate question-and-answer pairs based on the indexed content.
- [ ] **REQ-QNA-002**: Support configurable output: number of Q&A pairs (default 10), difficulty level, question types (factual, conceptual, application-based).
- [ ] **REQ-QNA-003**: Each generated Q&A pair must include the source citation (which source and chunk it was derived from).
- [ ] **REQ-QNA-004**: Allow the user to review, edit, and approve generated Q&A pairs.
- [ ] **REQ-QNA-005**: Support exporting Q&A pairs as JSON or Markdown.
- [ ] **REQ-QNA-006**: Support flashcard mode — present question, let user attempt, then reveal answer.

**Edge cases:**
- Insufficient content on a topic: generate fewer Q&As and inform the user.
- Overlapping/duplicate questions: deduplicate before presenting.

### Feature 5: Content Summarization

- [ ] **REQ-SUM-001**: Accept a source ID or selection of sources. Generate a summary of the content.
- [ ] **REQ-SUM-002**: Support two summary modes: **short** (1-3 paragraphs, key takeaways) and **detailed** (comprehensive, section-by-section breakdown with key points).
- [ ] **REQ-SUM-003**: Include source metadata (title, author if available, date, URL) in the summary header.
- [ ] **REQ-SUM-004**: For multi-source summaries, organize by source with clear attribution.
- [ ] **REQ-SUM-005**: Support summarizing a specific topic across all indexed sources (cross-source topical summary).
- [ ] **REQ-SUM-006**: Allow export of summaries as Markdown or plain text.

**Edge cases:**
- Very short documents: summary may be nearly as long as the original — note this to the user.
- Conflicting information across sources: highlight discrepancies.

### Feature 6: Document Viewer

- [ ] **REQ-VWR-001**: Provide an endpoint to retrieve the original file for any indexed source. For uploaded files, serve the original binary (PDF, DOCX, etc.). For URLs, serve the stored HTML snapshot. For pasted text, serve the raw text.
- [ ] **REQ-VWR-002**: Provide an in-browser document viewer that renders the original content. PDFs render via an embedded PDF viewer, DOCX and MD render as formatted HTML, TXT renders as plain text, and URL snapshots render as readable HTML.
- [ ] **REQ-VWR-003**: The document viewer must display source metadata (title, format, ingestion date, tags) alongside the content.
- [ ] **REQ-VWR-004**: Support navigation within long documents (page numbers for PDFs, section headings for structured documents).
- [ ] **REQ-VWR-005**: Allow the user to download the original file in its native format from the viewer.
- [ ] **REQ-VWR-006**: When viewing a source referenced in a chat answer or Q&A citation, highlight or scroll to the relevant section/chunk.

**Edge cases:**
- Original file is corrupted or missing from storage: show error with option to re-upload.
- Very large files (100+ MB): stream content progressively rather than loading all at once.
- Browser cannot render the format natively (e.g., DOCX): convert to HTML for viewing, offer download for native format.

### Feature 7: Source Catalog

- [ ] **REQ-CAT-001**: Maintain a persistent catalog of all indexed sources with the following metadata per entry: unique source ID, title, source type (file upload, URL, pasted text, local folder, cloud folder), original filename or URL or folder path, file format, ingestion timestamp, last re-indexed timestamp, content hash (for dedup), chunk count, total token count, processing status, original file storage path, parent folder source ID (for folder-ingested files), user-provided tags/labels, and a brief auto-generated description.
- [ ] **REQ-CAT-002**: Provide a list/search API for the catalog with filtering by source type, tags, date range, and full-text search on title/description.
- [ ] **REQ-CAT-003**: Provide a detail API for a single catalog entry, including chunk statistics and sample content.
- [ ] **REQ-CAT-004**: Support deleting a source — removes the catalog entry and all associated chunks/embeddings from the vector store.
- [ ] **REQ-CAT-005**: Support updating metadata (title, tags, description) for a catalog entry.
- [ ] **REQ-CAT-006**: Display catalog in the UI with sortable columns, search, and bulk actions (delete, re-index, tag).

## 5. Non-Functional Requirements

- [ ] **REQ-NFR-001**: **Performance** — Chat responses should return within 10 seconds for typical queries. Ingestion of a 50-page PDF should complete within 2 minutes.
- [ ] **REQ-NFR-002**: **Scalability** — Support up to 1,000 indexed sources and 500,000 chunks in the vector store without degradation.
- [ ] **REQ-NFR-003**: **Security** — Sanitize all user inputs. Never log raw user content at INFO level. Validate uploaded file types server-side. Apply rate limiting on public endpoints.
- [ ] **REQ-NFR-004**: **Privacy** — PII in uploaded content must not leak into logs. Support content deletion (right to erasure).
- [ ] **REQ-NFR-005**: **Reliability** — Graceful error handling for LLM failures (timeouts, rate limits). Queue-based ingestion with retry on transient failures.
- [ ] **REQ-NFR-006**: **Maintainability** — Modular architecture. Embedding model, LLM, vector store, and chunking strategy must be swappable via configuration without code changes.
- [ ] **REQ-NFR-007**: **Observability** — Structured logging for all operations. Metrics for ingestion throughput, query latency, LLM token usage, and retrieval relevance scores.

## 6. Tech Stack and Constraints

- **Language**: Python 3.12+
- **Framework**: FastAPI (backend API), Jinja2 or HTMX (lightweight frontend), or a separate React/Next.js frontend (TBD).
- **LLM**: Configurable — support Claude API (primary), with mock backend for development and testing.
- **Embeddings**: Sentence-transformers (e.g., `all-MiniLM-L6-v2`) or a cloud embedding API.
- **Vector Store**: ChromaDB (default, file-based), with option to swap to FAISS, Qdrant, or pgvector.
- **Document Parsing**: `pypdf` for PDF, `python-docx` for DOCX, `beautifulsoup4` + `httpx` for web pages.
- **Chunking**: LangChain text splitters or a custom recursive splitter.
- **File Storage**: Local filesystem (`data/originals/`) for storing original uploaded files. Files organized by source ID.
- **Cloud Storage**: `google-api-python-client` for Google Drive, `boto3` for S3, `dropbox` SDK for Dropbox (installed as optional extras).
- **Database**: SQLite (catalog metadata) for v1, PostgreSQL for v2.
- **Task Queue**: In-process background tasks for v1, Celery/Redis for v2.
- **Environment**: Local development, Docker-ready. No GPU required (CPU-based embeddings).
- **Constraints**: All LLM calls must set explicit `max_tokens`. Mock backend must be available for all AI features.

## 7. Project Structure

```
├── main.py                     # FastAPI entry point
├── src/
│   ├── api/
│   │   └── routes.py           # All API endpoints (mounted at /api/v1)
│   ├── data/
│   │   ├── ingestion.py        # Document parsing, chunking, embedding pipeline
│   │   ├── parsers.py          # Format-specific parsers (PDF, DOCX, URL, text)
│   │   ├── chunking.py         # Text splitting strategies
│   │   ├── folder_scanner.py   # Local folder recursive discovery
│   │   ├── cloud_storage.py    # Cloud storage integration (GDrive, Dropbox, S3)
│   │   └── file_store.py       # Original file storage and retrieval
│   ├── models/
│   │   ├── embeddings.py       # Embedding model wrapper
│   │   └── llm.py              # LLM client wrapper (Claude, mock)
│   ├── features/
│   │   ├── chat.py             # RAG chat logic
│   │   ├── interview.py        # Interview preparation logic
│   │   ├── qna.py              # Q&A generation logic
│   │   └── summarization.py    # Summarization logic
│   ├── pipelines/
│   │   └── rag.py              # Core RAG pipeline (retrieve → augment → generate)
│   ├── evaluation/             # Retrieval and generation quality evaluation
│   ├── catalog/
│   │   ├── models.py           # Catalog Pydantic models
│   │   ├── repository.py       # Catalog CRUD operations
│   │   └── service.py          # Catalog business logic
│   └── utils/
│       ├── config.py           # Layered config (Settings singleton)
│       ├── logger.py           # Structured logging setup
│       ├── errors.py           # AppError + ErrorCode enum
│       └── vector_store.py     # Vector store abstraction
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # API/integration tests
│   ├── evaluation/             # Retrieval quality tests
│   └── fixtures/               # Test data (sample docs, expected outputs)
├── configs/                    # Per-environment YAML configs
├── scripts/                    # Setup, deployment, utility scripts
├── docs/                       # Requirements, ADRs, runbooks
├── data/                       # raw/, interim/, processed/, uploads/
└── models/                     # Saved model artifacts, embeddings cache
```

## 8. Data and Models (AI/ML-Specific)

- **Data sources**: User-uploaded files (PDF, DOCX, TXT, MD), URLs (HTML pages), pasted text, local folders (recursive), and cloud storage folders (Google Drive, Dropbox, OneDrive, S3).
- **Input schema**: Each source produces a `Source` record (metadata) and a list of `Chunk` records (text segment + embedding vector + metadata).
- **Embedding models**:
  - Default: `all-MiniLM-L6-v2` (384-dim, fast, CPU-friendly).
  - Alternative: `all-mpnet-base-v2` (768-dim, higher quality).
  - Cloud option: Claude/OpenAI embedding API.
- **LLM**:
  - Primary: Claude API (via Anthropic SDK).
  - Mock: Deterministic mock for testing.
- **Vector store**: ChromaDB with cosine similarity, persistent storage.
- **Evaluation**: Retrieval relevance (MRR, hit rate), answer quality (human eval or LLM-as-judge), summarization quality (ROUGE or LLM-as-judge).

## 9. Example Scenarios

### Scenario 1: Upload and Chat

- **Input**: User uploads a 30-page PDF titled "Machine Learning System Design."
- **Processing**: System extracts text, chunks into ~50 segments, computes embeddings, stores in vector store, creates catalog entry.
- **User asks**: "What are the key considerations for feature stores?"
- **Output**: Answer citing specific sections from the PDF with page references, plus a list of relevant chunks with scores.

### Scenario 2: Interview Preparation

- **Input**: User has indexed 5 articles on distributed systems. Requests "Prepare me for a senior backend engineer interview on distributed systems, advanced difficulty."
- **Processing**: System retrieves relevant chunks, generates 10 technical interview questions.
- **User answers** question 1. System evaluates the answer against indexed content, provides feedback.
- **Output**: Per-question feedback and an overall assessment after all questions are answered.

### Scenario 3: Q&A Generation

- **Input**: User selects a source "Kubernetes Best Practices" and requests "Generate 15 conceptual Q&A pairs."
- **Output**: 15 question-answer pairs with source citations, downloadable as JSON.

### Scenario 4: Folder Ingestion and Document Reading

- **Input**: User provides a local folder path `/home/user/study-notes/` containing 3 subfolders with 25 PDF and Markdown files.
- **Processing**: System recursively discovers all supported files, ingests each as a separate source preserving the folder hierarchy as metadata, stores original files, reports per-file status.
- **Catalog shows**: 25 sources, each tagged with their relative path (e.g., `distributed-systems/cap-theorem.pdf`).
- **User clicks** on a source in the catalog: the original PDF opens in the in-browser viewer, readable in its original format.
- **User downloads**: clicks the download button to get the original file.

### Scenario 5: Summarization

- **Input**: User selects 3 indexed articles on "React Server Components" and requests a detailed summary.
- **Output**: A structured summary organized by source, with key takeaways, organized by theme.

## 10. Interfaces and APIs

### API Endpoints (prefix: `/api/v1`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sources/upload` | Upload a file for ingestion |
| `POST` | `/sources/url` | Submit a URL for ingestion |
| `POST` | `/sources/text` | Submit raw text for ingestion |
| `POST` | `/sources/folder` | Submit a local folder path for recursive ingestion |
| `POST` | `/sources/cloud-folder` | Submit a cloud storage folder for recursive ingestion |
| `GET` | `/sources` | List all sources (with filters) |
| `GET` | `/sources/{id}` | Get source details |
| `PUT` | `/sources/{id}` | Update source metadata |
| `DELETE` | `/sources/{id}` | Delete source and its chunks |
| `POST` | `/sources/{id}/reindex` | Re-index a source |
| `GET` | `/sources/{id}/original` | Download the original file |
| `GET` | `/sources/{id}/view` | Render original content for in-browser viewing |
| `POST` | `/chat` | Send a chat message (RAG) |
| `GET` | `/chat/sessions` | List chat sessions |
| `GET` | `/chat/sessions/{id}` | Get chat session history |
| `POST` | `/interview/start` | Start an interview session |
| `POST` | `/interview/{id}/answer` | Submit an answer for evaluation |
| `GET` | `/interview/{id}/summary` | Get interview session summary |
| `POST` | `/qna/generate` | Generate Q&A pairs |
| `GET` | `/qna/{id}` | Get generated Q&A set |
| `POST` | `/qna/{id}/export` | Export Q&A set |
| `POST` | `/summarize` | Generate a summary |
| `GET` | `/health` | Health check |

## 11. Testing and Validation

- **Unit tests**: Parsers, chunking, catalog CRUD, prompt construction, response formatting.
- **Integration tests**: Full ingestion pipeline (upload → parse → chunk → embed → store → catalog), full RAG flow (question → retrieve → generate → cite).
- **Evaluation tests**: Retrieval quality on a curated test set, answer quality using LLM-as-judge.
- **Safety tests**: Prompt injection attempts, oversized uploads, malformed URLs.
- **Acceptance criteria**:
  - All supported file formats parse and index successfully.
  - Folder ingestion recursively discovers and indexes all supported files.
  - All indexed documents can be viewed in their original format in the browser.
  - All indexed documents can be downloaded in their original format.
  - Chat answers include verifiable source citations.
  - Interview questions are relevant to the requested topic.
  - Generated Q&As are factually grounded in indexed content.
  - Summaries capture key points without hallucination.

## 12. Code Style and Quality

- Follow all conventions in CLAUDE.md and `docs/requirements/common_requirements.md`.
- Python 3.12+, Ruff, mypy, structlog, Pydantic models at all boundaries.
- Docstrings on all public functions in `src/`.

## 13. Workflow and Tools Usage

- Plan each feature before implementing. Get user approval on the plan.
- Implement in this order: (1) ingestion pipeline + file storage, (2) catalog, (3) document viewer, (4) folder ingestion (local), (5) RAG chat, (6) summarization, (7) Q&A generation, (8) interview prep, (9) cloud folder ingestion.
- Use mock LLM backend for development and all tests.
- Write tests alongside implementation, not after.

## 14. Out of Scope / Boundaries

- No user authentication or multi-tenancy in v1 (single-user local app).
- No real-time collaborative editing of content.
- No image/video/audio content processing (text-only in v1).
- No fine-tuning or training of models.
- No deployment to cloud (local development only in v1).

## 15. Output Format

- Code as organized file snippets with clear paths.
- Plans before major features.
- Tests alongside implementations.
- API documentation auto-generated via FastAPI OpenAPI/Swagger.
