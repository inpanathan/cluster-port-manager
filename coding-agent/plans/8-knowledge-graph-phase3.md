# Plan 8 — Phase 3: Knowledge Graph (Neo4j)

## Context

Phase 1 delivered the book catalog, download pipeline, API, and Library UI. Phase 2 (Plan 7) adds vector embeddings in Qdrant so books are searchable via RAG. Phase 3 builds a knowledge graph in Neo4j from extracted entities and relationships, enabling cross-book discovery, graph-augmented RAG, and interactive visualization.

**Depends on:** Phase 2 (books must have extracted text/chunks before entity extraction)

**Infrastructure already in place:**
- Book models with `graph_status` field (pending/processing/completed/failed/skipped) (`src/books/models.py`)
- LLM client (`src/models/llm.py`) — Mock, Claude, and vLLM backends via `LLMClient` protocol
- Embedding model (`src/models/embeddings.py`) — for entity similarity during resolution
- Book text extraction and chunking (from Phase 2)
- ServiceContainer DI pattern (`src/api/dependencies.py`)
- Config with `BooksSettings`, `LLMSettings` (`src/utils/config.py`)

**What Phase 3 adds:**
- Neo4j connection wrapper and schema management
- LLM-based entity and relationship extraction from book chunks
- Cross-book entity resolution (deduplication, merging)
- Knowledge graph construction pipeline with progress tracking
- 7 graph API endpoints (search, entity detail, paths, related books, topics, stats)
- Interactive force-directed graph visualization in the frontend
- Graph-augmented RAG integration
- Neo4j start/stop script (Docker)

**Requirements:** REQ-KGC-001 through REQ-KGC-008, REQ-KGV-001 through REQ-KGV-005

---

## Step 1 — Dependencies & Configuration `[x]`

### 1.1 Update `pyproject.toml` `[x]`
- Add `neo4j>=5.18.0` to a new `graph` optional extra:
  ```toml
  graph = [
      "neo4j>=5.18.0",
  ]
  ```
- Run `uv sync --extra dev --extra graph`

### 1.2 Add `Neo4jSettings` to `src/utils/config.py` `[x]`
- Define `Neo4jSettings(BaseSettings)`:
  - `url: str = "bolt://localhost:7687"`
  - `user: str = "neo4j"`
  - `password: str = ""`
  - `database: str = "knowledgehub"`
- Add `neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)` to root `Settings`
- Env vars: `NEO4J__URL`, `NEO4J__USER`, `NEO4J__PASSWORD`, `NEO4J__DATABASE`

### 1.3 Add error codes to `src/utils/errors.py` `[x]`
- `NEO4J_CONNECTION_FAILED` — cannot connect to Neo4j
- `GRAPH_CONSTRUCTION_FAILED` — general graph build error
- `ENTITY_EXTRACTION_FAILED` — LLM extraction returned invalid JSON
- `GRAPH_QUERY_FAILED` — Cypher query error
- `ENTITY_RESOLUTION_FAILED` — entity merging/dedup error

### 1.4 Update `.env.example` `[x]`
- Add Neo4j variables with comments

### 1.5 Update `configs/local.yaml` `[x]`
- Add `neo4j` section with defaults

### 1.6 Write tests `[x]`
- **File:** `tests/unit/test_config_neo4j.py`
- Test Neo4jSettings loads from env vars
- Test defaults are correct

---

## Step 2 — Neo4j Connection Wrapper `[x]`

### 2.1 Create `src/utils/graph_store.py` `[x]`
- Define `GraphStore` protocol:
  - `create_node(label: str, properties: dict) -> str` — returns node ID
  - `create_relationship(from_id: str, to_id: str, rel_type: str, properties: dict) -> None`
  - `find_node(label: str, properties: dict) -> dict | None`
  - `merge_node(label: str, match_keys: dict, properties: dict) -> str` — upsert
  - `query(cypher: str, params: dict) -> list[dict]` — raw Cypher query
  - `delete_book_graph(book_id: str) -> int` — delete all nodes/edges for a book
  - `get_stats() -> GraphStats` — node/edge counts by type
  - `close() -> None`
- Define `GraphStats` model: `node_counts: dict[str, int]`, `relationship_counts: dict[str, int]`, `total_nodes: int`, `total_relationships: int`

### 2.2 Implement `Neo4jGraphStore` `[x]`
- Use `neo4j` Python driver with async support
- Connection pool management (single driver instance)
- Auto-create constraints and indexes on first use:
  - Unique constraint on `Entity.id`, `Book.id`, `Author.name`, `Topic.name`
  - Index on `Entity.name`, `Entity.type`, `Chapter.book_id`
- Implement all protocol methods with Cypher queries
- `merge_node` uses `MERGE` for idempotent upserts
- `delete_book_graph` uses `MATCH (n) WHERE n.book_id = $book_id DETACH DELETE n`
- Error handling: wrap driver errors in `AppError(NEO4J_CONNECTION_FAILED | GRAPH_QUERY_FAILED)`
- Structured logging for all operations

### 2.3 Implement `MockGraphStore` `[x]`
- In-memory dict-based implementation for testing
- Stores nodes as `dict[str, dict]`, relationships as `list[tuple]`
- Supports all protocol methods

### 2.4 Factory function `[x]`
- `create_graph_store(backend: str) -> GraphStore`
  - `"mock"` → `MockGraphStore`
  - `"local"` / `"cloud"` → `Neo4jGraphStore(settings.neo4j)`

### 2.5 Write tests `[x]`
- **File:** `tests/unit/test_graph_store.py`
- Test MockGraphStore CRUD operations
- Test merge_node idempotency
- Test delete_book_graph removes all related nodes/edges
- Test stats calculation

---

## Step 3 — Graph Schema Definition `[x]`

Define the knowledge graph schema as documented Pydantic models.

### 3.1 Create `src/features/knowledge_graph/models.py` `[x]`
- **Node types** (REQ-KGC-002):
  - `BookNode`: id, title, author, isbn, publisher, year, language, page_count, file_format
  - `AuthorNode`: name, aliases (list), description
  - `ChapterNode`: book_id, number, title, start_page, end_page
  - `EntityNode`: id, name, type (person/org/place/concept/technology/event/theory), description, aliases (list), mention_count
  - `TopicNode`: name, description, parent_topic (for hierarchy)
- **Relationship types** (REQ-KGC-003):
  - `AUTHORED_BY` (Book → Author)
  - `HAS_CHAPTER` (Book → Chapter)
  - `MENTIONS` (Chapter → Entity, properties: context, page, confidence)
  - `DISCUSSES` (Chapter → Topic, properties: depth: primary/secondary)
  - `RELATED_TO` (Entity → Entity, properties: relationship_type, confidence)
  - `PART_OF` (Entity → Entity, for hierarchical relationships)
  - `PRECEDES` (Entity/Event → Entity/Event, temporal ordering)
  - `SUPPORTS` / `CONTRADICTS` (Entity/Concept → Entity/Concept)
  - `CROSS_REFERENCED` (Book → Book, properties: shared_entity_count, shared_topic_count)
  - `SUBTOPIC_OF` (Topic → Topic)
- **Response models** for API:
  - `GraphNode`: id, label, name, type, properties, connections_count
  - `GraphEdge`: source, target, relationship, properties
  - `GraphNeighborhood`: center_node, nodes, edges
  - `GraphPath`: nodes, edges, length
  - `GraphSearchResult`: nodes with relevance scores

### 3.2 Write tests `[x]`
- **File:** `tests/unit/test_graph_models.py`
- Test model validation
- Test serialization/deserialization

---

## Step 4 — LLM Entity Extraction `[x]`

Use the LLM to extract entities and relationships from book chunks.

### 4.1 Create `src/models/graph_extractor.py` `[x]`
- Define `ExtractionResult` model:
  - `entities: list[ExtractedEntity]` — name, type, description, aliases
  - `relationships: list[ExtractedRelationship]` — source_entity, target_entity, relationship_type, context, confidence
  - `topics: list[ExtractedTopic]` — name, description, parent_topic
- Implement `GraphExtractor` class:
  - Dependencies: `LLMClient`, logger
  - `extract_from_chunk(chunk_text: str, chapter_title: str, book_title: str) -> ExtractionResult`
    - Build a structured extraction prompt asking for JSON output:
      ```
      Extract entities, relationships, and topics from this book passage.
      Book: {book_title}, Chapter: {chapter_title}

      Return JSON with:
      - entities: [{name, type, description, aliases}]
      - relationships: [{source, target, type, context}]
      - topics: [{name, description, parent}]

      Entity types: person, organization, place, concept, technology, event, theory
      Relationship types: mentions, related_to, part_of, precedes, supports, contradicts
      ```
    - Set `max_tokens` appropriately (e.g., 2048) (REQ-ERR-007)
    - Parse JSON from LLM response with error handling
    - Validate against `ExtractionResult` model
    - On parse failure, retry once with a simpler prompt; if still fails, return empty result and log warning
  - `extract_from_book(chunks: list[BookChunk], book_title: str) -> list[ExtractionResult]`
    - Process chunks sequentially (LLM calls are expensive)
    - Log progress: `"entity_extraction_progress"`, chunk N/M
    - Aggregate results across chunks

### 4.2 Implement `MockGraphExtractor` `[x]`
- Returns deterministic entities/relationships based on chunk content hash
- For testing without LLM calls

### 4.3 Write tests `[x]`
- **File:** `tests/unit/test_graph_extractor.py`
- Test prompt construction
- Test JSON parsing from LLM response (valid, malformed, empty)
- Test retry on parse failure
- Test mock extractor determinism
- Test extraction with various chunk content types

---

## Step 5 — Entity Resolution `[x]`

Deduplicate and merge entities across chunks and books.

### 5.1 Create `src/features/knowledge_graph/entity_resolution.py` `[x]`
- Implement `EntityResolver` class:
  - Dependencies: `EmbeddingModel`, logger
  - `resolve(entities: list[ExtractedEntity]) -> list[ResolvedEntity]`
    1. **Exact match**: Group entities with identical normalized names (lowercase, strip whitespace)
    2. **Alias match**: Check if any entity name matches another's aliases
    3. **Embedding similarity**: For remaining entities of the same type, compute pairwise cosine similarity; merge if > 0.92 threshold
    4. Merge properties: combine descriptions, union aliases, sum mention counts
    5. Pick the most frequent name form as the canonical name
  - `resolve_across_books(book_entities: dict[str, list[ResolvedEntity]]) -> list[ResolvedEntity]`
    - Same logic applied across books
    - Track which books mention each entity for cross-references (REQ-KGC-006)

### 5.2 Write tests `[x]`
- **File:** `tests/unit/test_entity_resolution.py`
- Test exact name matching ("Barack Obama" == "barack obama")
- Test alias matching ("USA" in aliases of "United States")
- Test embedding similarity merging
- Test cross-book resolution
- Test no false merges (different entities with similar names)

---

## Step 6 — Knowledge Graph Construction Pipeline `[x]`

Orchestrate: extract → resolve → build graph → track progress.

### 6.1 Create `src/pipelines/knowledge_graph.py` `[x]`
- Define `KnowledgeGraphPipeline` class:
  - Dependencies: `GraphExtractor`, `EntityResolver`, `GraphStore`, `BookService`, logger
- Implement `build_book_graph(book_id: str, chunks: list[BookChunk], *, force: bool = False) -> GraphBuildResult`:
  1. Fetch book from `BookService` — raise if not found
  2. Check `graph_status` — skip if COMPLETED unless `force`
  3. Mark `graph_status = PROCESSING`
  4. Extract entities/relationships from all chunks via `GraphExtractor`
  5. Resolve entities within the book via `EntityResolver`
  6. Delete existing graph for this book (idempotent) via `GraphStore.delete_book_graph()`
  7. Create/merge nodes in Neo4j:
     - `BookNode` for the book
     - `AuthorNode` for the author (merge if exists)
     - `ChapterNode` for each chapter
     - `EntityNode` for each resolved entity (merge across books)
     - `TopicNode` for each topic (merge)
  8. Create relationships:
     - `AUTHORED_BY`, `HAS_CHAPTER`
     - `MENTIONS` (Chapter → Entity)
     - `DISCUSSES` (Chapter → Topic)
     - `RELATED_TO`, `PART_OF`, `SUPPORTS`, `CONTRADICTS` (Entity ↔ Entity)
     - `SUBTOPIC_OF` (Topic → Topic)
  9. Mark `graph_status = COMPLETED`
  10. Return `GraphBuildResult`: entity_count, relationship_count, topic_count, duration_ms
- Error handling:
  - On failure, mark `graph_status = FAILED`, log error
  - Partial graph is acceptable (unlike embeddings) — don't delete on failure

### 6.2 Implement `build_cross_references() -> CrossRefResult` `[x]`
- Run after all books are processed (REQ-KGC-006)
- For each pair of books, count shared entities and shared topics
- Create `CROSS_REFERENCED` edges between books that share significant overlap (>= 3 shared entities or >= 2 shared topics)
- Compute topic overlap scores
- Return stats: cross-ref edges created, most connected books

### 6.3 Implement `build_all(*, force: bool = False) -> BatchResult` `[x]`
- Process all books with `graph_status != COMPLETED` (or all if `force`)
- Requires `embedding_status == COMPLETED` (need chunks from Phase 2)
- Process sequentially
- After all books, run `build_cross_references()`
- Log progress and return summary

### 6.4 Add `BookService` methods `[x]`
- `mark_graph_started(book_id: str)` — set `graph_status = PROCESSING`
- `mark_graph_completed(book_id: str, entity_count: int)` — set `graph_status = COMPLETED`
- `mark_graph_failed(book_id: str, error: str)` — set `graph_status = FAILED`

### 6.5 Write tests `[x]`
- **File:** `tests/unit/test_knowledge_graph_pipeline.py`
- Test full pipeline: extract → resolve → build
- Test skip when already completed
- Test force re-processing (deletes old graph)
- Test cross-reference building
- Test failure handling (status set correctly)
- Test requires embedding completed

---

## Step 7 — Graph Construction Script `[x]`

### 7.1 Create `scripts/build_knowledge_graph.py` `[x]`
- Parse args:
  - `--book-id <ID>` — build graph for a single book
  - `--force` — rebuild even if already completed
  - `--skip-cross-refs` — skip cross-reference building
  - `--dry-run` — show what would be processed
- Initialize dependencies (LLM client, graph store, embedding model, services)
- Verify Neo4j connection before starting
- Call `build_book_graph()` or `build_all()`
- Print summary: books processed, entities created, relationships created, cross-references
- Exit with non-zero code on failure

### 7.2 Create `scripts/start_neo4j.sh` `[x]`
- Docker-based Neo4j management (similar to `scripts/start_qdrant.sh`)
- Commands: `start` (default), `stop`, `status`
- Container name: `knowledge-hub-neo4j`
- Ports: `7474` (HTTP), `7687` (Bolt)
- Volume: `knowledge-hub-neo4j-data` for persistence
- Set default password from env var `NEO4J__PASSWORD` (or default for dev)
- Wait for Neo4j ready before returning (health check on 7474)

### 7.3 Update `scripts/seed_books.sh` `[x]`
- Add graph building step after embedding:
  ```bash
  echo "Step 4: Building knowledge graph..."
  uv run python scripts/build_knowledge_graph.py
  ```
- Add `--skip-graph` flag

### 7.4 Write test `[x]`
- **File:** `tests/unit/test_build_graph_script.py`
- Test argument parsing
- Test dry-run mode

---

## Step 8 — Graph API Endpoints `[x]`

### 8.1 Create `src/features/knowledge_graph/service.py` `[x]`
- Define `KnowledgeGraphService` class:
  - Dependencies: `GraphStore`, logger
- Methods:
  - `search_entities(query: str, entity_type: str | None, limit: int) -> list[GraphSearchResult]`
    - Full-text search on entity names (fuzzy match via Cypher `CONTAINS` or `apoc.text.fuzzyMatch`)
    - Filter by entity type if specified
  - `get_entity(entity_id: str, depth: int = 1) -> GraphNeighborhood`
    - Return entity with N-hop neighborhood
    - Include connected entities, topics, books, chapters
  - `find_path(from_id: str, to_id: str, max_depth: int = 5) -> GraphPath | None`
    - Shortest path between two entities using Cypher `shortestPath()`
  - `get_book_entities(book_id: str) -> list[GraphNode]`
    - All entities and topics from a specific book
  - `get_related_books(book_id: str) -> list[RelatedBook]`
    - Books connected via `CROSS_REFERENCED` edges, sorted by shared entity count
  - `get_topic_taxonomy() -> list[TopicTree]`
    - Hierarchical topic structure via `SUBTOPIC_OF` relationships
  - `get_stats() -> GraphStats`
    - Node counts by type, relationship counts by type, top entities, most cross-referenced books

### 8.2 Add endpoints to `src/api/routes.py` `[x]`
- `GET /graph/search?q={query}&type={entity_type}&limit=20` → search entities
- `GET /graph/entity/{entity_id}?depth=1` → entity with neighborhood
- `GET /graph/entity/{entity_id}/path/{target_id}?max_depth=5` → shortest path
- `GET /graph/book/{book_id}/entities` → entities from a book
- `GET /graph/book/{book_id}/related` → related books
- `GET /graph/topics` → topic taxonomy
- `GET /graph/stats` → graph statistics (REQ-KGC-008)

### 8.3 Add schemas to `src/api/schemas.py` `[x]`
- `GraphSearchResponse`, `GraphNeighborhoodResponse`, `GraphPathResponse`
- `BookEntitiesResponse`, `RelatedBooksResponse`, `TopicTaxonomyResponse`
- `GraphStatsResponse`

### 8.4 Register in `src/api/dependencies.py` `[x]`
- Add `GraphStore` and `KnowledgeGraphService` to `ServiceContainer`

### 8.5 Write tests `[x]`
- **File:** `tests/integration/test_graph_api.py`
- Test each endpoint with mock graph store
- Test search with and without type filter
- Test entity neighborhood at different depths
- Test path finding (exists, no path)
- Test stats endpoint

---

## Step 9 — Frontend: Knowledge Graph Page `[x]`

### 9.1 Install frontend dependencies `[x]`
- Add `react-force-graph-2d` (or `@react-sigma/core` with graphology) to `frontend/package.json`
- Evaluate: `react-force-graph-2d` is simpler; `sigma.js` handles larger graphs better
- Decision: use `react-force-graph-2d` for v1, swap if performance becomes an issue

### 9.2 Create `frontend/src/api/graph.ts` `[x]`
- API client functions for all 7 graph endpoints
- TypeScript types matching the API schemas

### 9.3 Create `frontend/src/features/graph/GraphViewer.tsx` `[x]`
- Force-directed graph component using `react-force-graph-2d`
- Node coloring by type (Book=blue, Author=green, Entity=orange, Topic=purple, Chapter=gray)
- Node sizing by connection count
- Labeled edges
- Click-to-expand: clicking a node loads its neighborhood and adds to the graph
- Hover tooltip: show node name, type, description
- Zoom, pan, drag support
- Props: `nodes: GraphNode[]`, `edges: GraphEdge[]`, `onNodeClick`, `onExpand`

### 9.4 Create `frontend/src/features/graph/KnowledgeGraphPage.tsx` `[x]`
- Search bar at top — calls `GET /graph/search`
- Filter controls: entity type dropdown, book filter
- Main area: `GraphViewer` component
- Side panel: shows selected node details, connected nodes list
- Stats summary bar: total nodes, edges, books, entities
- Initial state: show top entities or recent books as starting nodes

### 9.5 Create `frontend/src/features/graph/EntityDetail.tsx` `[x]`
- Side panel component for selected entity
- Shows: name, type, description, aliases, mention count
- Lists: connected entities, books mentioning this entity, topics
- "Find path to..." button to trigger path finding

### 9.6 Add route and navigation `[x]`
- Add `/graph` route to the router
- Add "Knowledge Graph" link in the sidebar/nav

### 9.7 Write tests `[x]`
- Component tests for KnowledgeGraphPage (renders, search triggers API call)
- Test GraphViewer renders nodes and edges

---

## Step 10 — Mini Graph on Book Detail `[x]`

### 10.1 Update `frontend/src/features/library/BookDetail.tsx` `[x]`
- Add a "Knowledge Graph" tab/section
- When `graph_status === "completed"`, fetch `GET /graph/book/{id}/entities` and render a mini `GraphViewer`
- Show entity count and key topics
- Link to full graph page filtered to this book

### 10.2 Update book card status indicator `[x]`
- Show graph_status alongside embedding_status in `BookCard.tsx`
- Status badges: Pending, Processing, Completed, Failed, Skipped

---

## Step 11 — Graph-Augmented RAG `[x]`

### 11.1 Modify `src/pipelines/rag.py` `[x]`
- Add `use_graph: bool = False` parameter to `query()`
- When enabled:
  1. Extract key entities from the user's question (simple NER or keyword extraction)
  2. Query knowledge graph for those entities and their 1-hop neighbors
  3. Build a "graph context" string with entity descriptions and relationships
  4. Prepend graph context to the LLM prompt alongside vector search results
  5. This gives the LLM cross-book connections and entity context it wouldn't have from chunks alone
- Add `graph_context` field to `RAGResponse` for transparency

### 11.2 Update chat endpoint `[x]`
- Add `use_graph: bool = False` to chat request body
- Pass through to RAG pipeline

### 11.3 Write tests `[x]`
- **File:** `tests/integration/test_graph_augmented_rag.py`
- Test RAG with graph context includes entity information
- Test RAG without graph context works normally (backward compatible)
- Test entity extraction from questions

---

## Step 12 — Documentation & Cleanup `[x]`

### 12.1 Update `docs/app_cheatsheet.md` `[x]`
- Add all 7 graph API endpoints
- Add `scripts/build_knowledge_graph.py` commands
- Add `scripts/start_neo4j.sh` commands
- Add Neo4j env vars to config table

### 12.2 Update `docs/troubleshooting.md` `[x]`
- Add section on Neo4j connection issues
- Add section on entity extraction failures (malformed LLM output)
- Add section on graph performance (large graphs, slow queries)

### 12.3 Create `docs/runbook/knowledge_graph.md` `[x]`
- Neo4j operations: backup, restore, clear graph
- Monitoring: node/edge counts, query latency
- Common issues and remediation

### 12.4 Run full quality checks `[x]`
- `bash scripts/check_all.sh` — lint, format, typecheck, tests all pass

---

## Acceptance Criteria

1. `bash scripts/start_neo4j.sh` starts Neo4j in Docker with persistent storage
2. `uv run python scripts/build_knowledge_graph.py` processes all embedded books into the knowledge graph
3. Entity extraction via LLM produces structured entities, relationships, and topics from book content
4. Entity resolution deduplicates entities within and across books
5. Cross-book references are created between books sharing significant entity/topic overlap
6. All 7 graph API endpoints return correct data
7. Frontend Knowledge Graph page renders an interactive force-directed graph with search, filter, and click-to-expand
8. Book detail page shows a mini knowledge graph for completed books
9. Graph-augmented RAG uses entity context to improve chat answers
10. `graph_status` correctly tracks progress for each book
11. All existing tests pass; new tests cover graph pipeline, API, and entity resolution
12. Documentation is updated (cheatsheet, troubleshooting, runbook)
