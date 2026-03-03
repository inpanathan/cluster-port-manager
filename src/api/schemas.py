"""Pydantic request/response models for the API layer.

Separate from internal models to avoid leaking implementation details.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ---------- Ingestion ----------


class IngestionResponse(BaseModel):
    """Response after ingesting a single source."""

    source_id: str
    status: str
    chunk_count: int = 0
    error: str = ""


class FolderIngestionResponse(BaseModel):
    """Response after ingesting a folder."""

    folder_source_id: str
    total_files: int
    succeeded: int
    failed: int
    skipped: int
    results: list[IngestionResponse]


class UrlIngestionRequest(BaseModel):
    """Request to ingest a URL."""

    url: str
    title: str | None = None
    tags: list[str] = Field(default_factory=list)


class TextIngestionRequest(BaseModel):
    """Request to ingest raw text."""

    content: str
    title: str = "Pasted Text"
    tags: list[str] = Field(default_factory=list)


class FolderIngestionRequest(BaseModel):
    """Request to ingest files from a local folder."""

    folder_path: str
    tags: list[str] = Field(default_factory=list)


# ---------- Source / Catalog ----------


class SourceUpdateRequest(BaseModel):
    """Request to update source metadata."""

    title: str | None = None
    tags: list[str] | None = None
    description: str | None = None


class SourceDetail(BaseModel):
    """Full source detail response."""

    id: str
    title: str
    source_type: str
    origin: str
    file_format: str
    ingested_at: datetime
    last_indexed_at: datetime | None
    content_hash: str
    chunk_count: int
    total_tokens: int
    status: str
    tags: list[str]
    description: str
    error_message: str


class SourceSummaryResponse(BaseModel):
    """Lightweight source info for list views."""

    id: str
    title: str
    source_type: str
    file_format: str
    ingested_at: datetime
    status: str
    chunk_count: int
    tags: list[str]


class SourceListResponse(BaseModel):
    """Paginated source list response."""

    sources: list[SourceSummaryResponse]
    total: int


# ---------- Chat ----------


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    message: str
    session_id: str | None = None
    source_ids: list[str] | None = None
    include_books: bool = True


class CitationResponse(BaseModel):
    """A source citation in a chat response."""

    source_id: str
    source_title: str
    chunk_text: str
    relevance_score: float


class ChatMessageResponse(BaseModel):
    """A single chat message."""

    role: str
    content: str
    timestamp: datetime
    citations: list[dict] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""

    session_id: str
    answer: str
    citations: list[dict] = Field(default_factory=list)


class ChatSessionResponse(BaseModel):
    """Full chat session with message history."""

    id: str
    messages: list[ChatMessageResponse]
    created_at: datetime
    source_filter: list[str] | None = None


class ChatSessionSummary(BaseModel):
    """Lightweight chat session for list views."""

    id: str
    created_at: datetime
    message_count: int


# ---------- Summarization ----------


class SummarizeRequest(BaseModel):
    """Request to summarize content."""

    source_ids: list[str] | None = None
    topic: str | None = None
    mode: str = "short"


class SummarizeResponse(BaseModel):
    """Summarization response."""

    summary: str
    mode: str
    source_ids: list[str]
    source_titles: list[str]


# ---------- Q&A ----------


class QnAGenerateRequest(BaseModel):
    """Request to generate Q&A pairs."""

    topic: str | None = None
    source_ids: list[str] | None = None
    count: int = 10
    difficulty: str = "intermediate"


class QAPairResponse(BaseModel):
    """A single Q&A pair."""

    question: str
    answer: str
    source_title: str = ""
    difficulty: str = ""


class QASetResponse(BaseModel):
    """A set of generated Q&A pairs."""

    id: str
    topic: str
    pairs: list[QAPairResponse]
    created_at: datetime
    difficulty: str


class QnAExportRequest(BaseModel):
    """Request to export a Q&A set."""

    format: str = "json"


# ---------- Interview ----------


class InterviewStartRequest(BaseModel):
    """Request to start an interview session."""

    topic: str
    mode: str = "mixed"
    difficulty: str = "intermediate"
    question_count: int = 10
    source_ids: list[str] | None = None


class InterviewQuestionResponse(BaseModel):
    """A single interview question with optional feedback."""

    index: int
    question: str
    user_answer: str = ""
    feedback: str = ""
    score: float = 0.0
    model_answer: str = ""
    answered: bool = False


class InterviewSessionResponse(BaseModel):
    """Interview session response."""

    id: str
    topic: str
    mode: str
    difficulty: str
    current_index: int
    total_questions: int
    completed: bool
    current_question: InterviewQuestionResponse | None = None


class InterviewAnswerRequest(BaseModel):
    """Request to submit an interview answer."""

    answer: str


class InterviewAnswerResponse(BaseModel):
    """Response after submitting an interview answer."""

    question: InterviewQuestionResponse
    next_question: InterviewQuestionResponse | None = None
    completed: bool


class InterviewSummaryResponse(BaseModel):
    """Interview session summary with scores."""

    id: str
    topic: str
    completed: bool
    overall_score: float
    overall_feedback: str
    questions: list[InterviewQuestionResponse]


# ---------- Books ----------


class BookSummaryResponse(BaseModel):
    """Lightweight book info for list views."""

    id: str
    title: str
    author: str
    file_format: str
    publication_year: int | None
    cover_image_path: str
    tags: list[str]
    embedding_status: str


class BookDetailResponse(BaseModel):
    """Full book detail."""

    id: str
    title: str
    author: str
    isbn: str
    publisher: str
    publication_year: int | None
    language: str
    page_count: int | None
    file_format: str
    file_size_bytes: int
    cover_image_path: str
    description: str
    table_of_contents: list[str]
    tags: list[str]
    drive_folder_path: str
    drive_file_id: str
    created_at: datetime
    processed_at: datetime | None
    embedding_status: str
    graph_status: str
    source_id: str | None


class BookListApiResponse(BaseModel):
    """Paginated book list."""

    books: list[BookSummaryResponse]
    total: int


class BookUpdateRequest(BaseModel):
    """Editable book fields."""

    title: str | None = None
    author: str | None = None
    tags: list[str] | None = None
    description: str | None = None


class BookEmbedRequest(BaseModel):
    """Request to trigger embedding for a book."""

    force: bool = False


class BookEmbedResponse(BaseModel):
    """Response from the book embedding endpoint."""

    book_id: str
    chunk_count: int = 0
    total_tokens: int = 0
    duration_ms: int = 0
    validation_passed: bool = False
    skipped: bool = False
    error: str = ""


class BookProcessingStatusResponse(BaseModel):
    """Processing status of a book."""

    embedding_status: str
    graph_status: str
    chunk_count: int | None = None
    source_id: str | None = None


# ---------- Knowledge Graph ----------


class GraphNodeResponse(BaseModel):
    """A node in the knowledge graph."""

    id: str
    label: str
    name: str
    type: str = ""
    properties: dict = Field(default_factory=dict)
    connections_count: int = 0


class GraphEdgeResponse(BaseModel):
    """An edge in the knowledge graph."""

    source: str
    target: str
    relationship: str
    properties: dict = Field(default_factory=dict)


class GraphSearchResponse(BaseModel):
    """Search results from the knowledge graph."""

    results: list[dict] = Field(default_factory=list)
    total: int = 0


class GraphNeighborhoodResponse(BaseModel):
    """Entity with its neighborhood."""

    center_node: GraphNodeResponse
    nodes: list[GraphNodeResponse] = Field(default_factory=list)
    edges: list[GraphEdgeResponse] = Field(default_factory=list)


class GraphPathResponse(BaseModel):
    """Path between two entities."""

    nodes: list[GraphNodeResponse] = Field(default_factory=list)
    edges: list[GraphEdgeResponse] = Field(default_factory=list)
    length: int = 0
    found: bool = True


class BookEntitiesResponse(BaseModel):
    """Entities from a specific book."""

    book_id: str
    entities: list[GraphNodeResponse] = Field(default_factory=list)
    total: int = 0


class RelatedBooksResponse(BaseModel):
    """Books related to a given book."""

    book_id: str
    related: list[dict] = Field(default_factory=list)


class TopicTaxonomyResponse(BaseModel):
    """Hierarchical topic structure."""

    topics: list[dict] = Field(default_factory=list)


class GraphStatsResponse(BaseModel):
    """Knowledge graph statistics."""

    node_counts: dict[str, int] = Field(default_factory=dict)
    relationship_counts: dict[str, int] = Field(default_factory=dict)
    total_nodes: int = 0
    total_relationships: int = 0


class GraphBuildRequest(BaseModel):
    """Request to build a knowledge graph for a book."""

    force: bool = False


class GraphBuildResponse(BaseModel):
    """Response from graph build."""

    book_id: str
    entity_count: int = 0
    relationship_count: int = 0
    topic_count: int = 0
    duration_ms: int = 0
    error: str = ""
