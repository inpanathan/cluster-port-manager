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
