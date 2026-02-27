"""API routes for the Knowledge Hub application.

This router is mounted at /api/v1 in main.py.
"""

from __future__ import annotations

import mimetypes
from typing import Annotated

from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.responses import Response

from src.api.dependencies import (
    get_catalog,
    get_chat,
    get_file_store,
    get_ingestion,
    get_interview,
    get_qna,
    get_summarization,
    get_vector_store,
)
from src.api.schemas import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionResponse,
    ChatSessionSummary,
    FolderIngestionRequest,
    FolderIngestionResponse,
    IngestionResponse,
    InterviewAnswerRequest,
    InterviewAnswerResponse,
    InterviewQuestionResponse,
    InterviewSessionResponse,
    InterviewStartRequest,
    InterviewSummaryResponse,
    QAPairResponse,
    QASetResponse,
    QnAExportRequest,
    QnAGenerateRequest,
    SourceDetail,
    SourceListResponse,
    SourceSummaryResponse,
    SourceUpdateRequest,
    SummarizeRequest,
    SummarizeResponse,
    TextIngestionRequest,
    UrlIngestionRequest,
)
from src.catalog.models import SourceUpdate
from src.catalog.service import CatalogService
from src.data.file_store import FileStore
from src.data.ingestion import IngestionPipeline
from src.features.chat import ChatService
from src.features.interview import DifficultyLevel as InterviewDifficulty
from src.features.interview import InterviewMode, InterviewService
from src.features.qna import DifficultyLevel as QnADifficulty
from src.features.qna import QnAService
from src.features.summarization import SummarizationService, SummaryMode
from src.utils.errors import AppError, ErrorCode
from src.utils.vector_store import VectorStore

router = APIRouter()


# ── Source Ingestion ──────────────────────────────────────────────────────


@router.post("/sources/upload", response_model=IngestionResponse)
async def upload_file(
    file: UploadFile,
    ingestion: Annotated[IngestionPipeline, Depends(get_ingestion)],
    title: str = Form(default=""),
    tags: str = Form(default=""),
) -> IngestionResponse:
    """Upload and ingest a file (PDF, DOCX, TXT, MD)."""
    file_data = await file.read()
    filename = file.filename or "upload"
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    result = ingestion.ingest_file(
        file_data,
        filename,
        title=title or None,
        tags=tag_list,
    )
    return IngestionResponse(
        source_id=result.source_id,
        status=result.status,
        chunk_count=result.chunk_count,
        error=result.error,
    )


@router.post("/sources/url", response_model=IngestionResponse)
async def ingest_url(
    body: UrlIngestionRequest,
    ingestion: Annotated[IngestionPipeline, Depends(get_ingestion)],
) -> IngestionResponse:
    """Ingest content from a URL."""
    result = ingestion.ingest_url(body.url, title=body.title, tags=body.tags)
    return IngestionResponse(
        source_id=result.source_id,
        status=result.status,
        chunk_count=result.chunk_count,
        error=result.error,
    )


@router.post("/sources/text", response_model=IngestionResponse)
async def ingest_text(
    body: TextIngestionRequest,
    ingestion: Annotated[IngestionPipeline, Depends(get_ingestion)],
) -> IngestionResponse:
    """Ingest raw text content."""
    result = ingestion.ingest_text(body.content, title=body.title, tags=body.tags)
    return IngestionResponse(
        source_id=result.source_id,
        status=result.status,
        chunk_count=result.chunk_count,
        error=result.error,
    )


@router.post("/sources/folder", response_model=FolderIngestionResponse)
async def ingest_folder(
    body: FolderIngestionRequest,
    ingestion: Annotated[IngestionPipeline, Depends(get_ingestion)],
) -> FolderIngestionResponse:
    """Ingest all supported files from a local folder."""
    result = ingestion.ingest_folder(body.folder_path, tags=body.tags)
    return FolderIngestionResponse(
        folder_source_id=result.folder_source_id,
        total_files=result.total_files,
        succeeded=result.succeeded,
        failed=result.failed,
        skipped=result.skipped,
        results=[
            IngestionResponse(
                source_id=r.source_id,
                status=r.status,
                chunk_count=r.chunk_count,
                error=r.error,
            )
            for r in result.results
        ],
    )


# ── Catalog CRUD ──────────────────────────────────────────────────────────


@router.get("/sources", response_model=SourceListResponse)
async def list_sources(
    catalog: Annotated[CatalogService, Depends(get_catalog)],
    source_type: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> SourceListResponse:
    """List sources with optional filters."""
    result = catalog.list_sources(
        source_type=source_type,
        status=status,
        tag=tag,
        search=search,
        limit=limit,
        offset=offset,
    )
    return SourceListResponse(
        sources=[
            SourceSummaryResponse(
                id=s.id,
                title=s.title,
                source_type=s.source_type,
                file_format=s.file_format,
                ingested_at=s.ingested_at,
                status=s.status,
                chunk_count=s.chunk_count,
                tags=s.tags,
            )
            for s in result.sources
        ],
        total=result.total,
    )


@router.get("/sources/{source_id}", response_model=SourceDetail)
async def get_source(
    source_id: str,
    catalog: Annotated[CatalogService, Depends(get_catalog)],
) -> SourceDetail:
    """Get full source detail."""
    source = catalog.get_source(source_id)
    return SourceDetail(
        id=source.id,
        title=source.title,
        source_type=source.source_type,
        origin=source.origin,
        file_format=source.file_format,
        ingested_at=source.ingested_at,
        last_indexed_at=source.last_indexed_at,
        content_hash=source.content_hash,
        chunk_count=source.chunk_count,
        total_tokens=source.total_tokens,
        status=source.status,
        tags=source.tags,
        description=source.description,
        error_message=source.error_message,
    )


@router.put("/sources/{source_id}", response_model=SourceDetail)
async def update_source(
    source_id: str,
    body: SourceUpdateRequest,
    catalog: Annotated[CatalogService, Depends(get_catalog)],
) -> SourceDetail:
    """Update source metadata (title, tags, description)."""
    updated = catalog.update_source(
        source_id,
        SourceUpdate(title=body.title, tags=body.tags, description=body.description),
    )
    return SourceDetail(
        id=updated.id,
        title=updated.title,
        source_type=updated.source_type,
        origin=updated.origin,
        file_format=updated.file_format,
        ingested_at=updated.ingested_at,
        last_indexed_at=updated.last_indexed_at,
        content_hash=updated.content_hash,
        chunk_count=updated.chunk_count,
        total_tokens=updated.total_tokens,
        status=updated.status,
        tags=updated.tags,
        description=updated.description,
        error_message=updated.error_message,
    )


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: str,
    catalog: Annotated[CatalogService, Depends(get_catalog)],
    file_store: Annotated[FileStore, Depends(get_file_store)],
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
) -> None:
    """Delete a source and its vectors and stored files."""
    catalog.get_source(source_id)  # ensure exists, raises SOURCE_NOT_FOUND
    vector_store.delete_by_source(source_id)
    file_store.delete(source_id)
    catalog.delete_source(source_id)


@router.post("/sources/{source_id}/reindex", response_model=IngestionResponse)
async def reindex_source(
    source_id: str,
    ingestion: Annotated[IngestionPipeline, Depends(get_ingestion)],
) -> IngestionResponse:
    """Re-index a source from its stored original."""
    result = ingestion.reindex_source(source_id)
    return IngestionResponse(
        source_id=result.source_id,
        status=result.status,
        chunk_count=result.chunk_count,
        error=result.error,
    )


# ── Document viewer ───────────────────────────────────────────────────────


@router.get("/sources/{source_id}/original")
async def download_original(
    source_id: str,
    catalog: Annotated[CatalogService, Depends(get_catalog)],
    file_store: Annotated[FileStore, Depends(get_file_store)],
) -> Response:
    """Download the original source file."""
    catalog.get_source(source_id)  # ensure exists
    file_result = file_store.get_file_bytes(source_id)
    if file_result is None:
        raise AppError(
            code=ErrorCode.FILE_NOT_FOUND,
            message="Original file not found",
            context={"source_id": source_id},
        )
    file_bytes, filename = file_result
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/sources/{source_id}/view")
async def view_source(
    source_id: str,
    catalog: Annotated[CatalogService, Depends(get_catalog)],
    file_store: Annotated[FileStore, Depends(get_file_store)],
) -> Response:
    """View the source inline (text rendered as HTML, others as attachment)."""
    source = catalog.get_source(source_id)
    file_result = file_store.get_file_bytes(source_id)
    if file_result is None:
        raise AppError(
            code=ErrorCode.FILE_NOT_FOUND,
            message="Original file not found",
            context={"source_id": source_id},
        )
    file_bytes, filename = file_result
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    # Render text-based files inline
    if source.file_format in ("txt", "md"):
        text = file_bytes.decode("utf-8")
        html = f"<html><body><pre>{text}</pre></body></html>"
        return Response(content=html, media_type="text/html")

    if source.file_format == "html":
        return Response(content=file_bytes, media_type="text/html")

    # PDF and others: inline disposition
    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ── Chat ──────────────────────────────────────────────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    chat_service: Annotated[ChatService, Depends(get_chat)],
) -> ChatResponse:
    """Send a chat message and get a RAG-powered response."""
    session_id, assistant_msg = chat_service.send_message(
        body.session_id,
        body.message,
        source_ids=body.source_ids,
    )
    return ChatResponse(
        session_id=session_id,
        answer=assistant_msg.content,
        citations=assistant_msg.citations,
    )


@router.get("/chat/sessions")
async def list_chat_sessions(
    chat_service: Annotated[ChatService, Depends(get_chat)],
) -> list[ChatSessionSummary]:
    """List all chat sessions."""
    sessions = chat_service.list_sessions()
    return [
        ChatSessionSummary(
            id=s.id,
            created_at=s.created_at,
            message_count=len(s.messages),
        )
        for s in sessions
    ]


@router.get("/chat/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(
    session_id: str,
    chat_service: Annotated[ChatService, Depends(get_chat)],
) -> ChatSessionResponse:
    """Get a chat session with its full message history."""
    session = chat_service.get_session(session_id)
    if session is None:
        raise AppError(
            code=ErrorCode.SESSION_NOT_FOUND,
            message=f"Chat session not found: {session_id}",
        )
    return ChatSessionResponse(
        id=session.id,
        messages=[
            ChatMessageResponse(
                role=m.role,
                content=m.content,
                timestamp=m.timestamp,
                citations=m.citations,
            )
            for m in session.messages
        ],
        created_at=session.created_at,
        source_filter=session.source_filter,
    )


# ── Summarization ────────────────────────────────────────────────────────


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(
    body: SummarizeRequest,
    summarization: Annotated[SummarizationService, Depends(get_summarization)],
) -> SummarizeResponse:
    """Summarize sources by IDs or by topic."""
    mode = SummaryMode(body.mode) if body.mode in ("short", "detailed") else SummaryMode.SHORT

    if body.source_ids:
        result = summarization.summarize_sources(body.source_ids, mode=mode)
    elif body.topic:
        result = summarization.summarize_topic(body.topic, mode=mode)
    else:
        raise AppError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Either source_ids or topic is required",
        )

    return SummarizeResponse(
        summary=result.summary,
        mode=result.mode.value,
        source_ids=result.source_ids,
        source_titles=result.source_titles,
    )


# ── Q&A Generation ───────────────────────────────────────────────────────


@router.post("/qna/generate", response_model=QASetResponse)
async def generate_qna(
    body: QnAGenerateRequest,
    qna: Annotated[QnAService, Depends(get_qna)],
) -> QASetResponse:
    """Generate Q&A pairs from topic or sources."""
    difficulty = (
        QnADifficulty(body.difficulty)
        if body.difficulty in ("beginner", "intermediate", "advanced")
        else QnADifficulty.INTERMEDIATE
    )

    qa_set = qna.generate(
        topic=body.topic,
        source_ids=body.source_ids,
        count=body.count,
        difficulty=difficulty,
    )
    return QASetResponse(
        id=qa_set.id,
        topic=qa_set.topic,
        pairs=[
            QAPairResponse(
                question=p.question,
                answer=p.answer,
                source_title=p.source_title,
                difficulty=p.difficulty,
            )
            for p in qa_set.pairs
        ],
        created_at=qa_set.created_at,
        difficulty=qa_set.difficulty,
    )


@router.get("/qna/{set_id}", response_model=QASetResponse)
async def get_qna_set(
    set_id: str,
    qna: Annotated[QnAService, Depends(get_qna)],
) -> QASetResponse:
    """Retrieve a generated Q&A set."""
    qa_set = qna.get_set(set_id)
    if qa_set is None:
        raise AppError(
            code=ErrorCode.NOT_FOUND,
            message=f"Q&A set not found: {set_id}",
        )
    return QASetResponse(
        id=qa_set.id,
        topic=qa_set.topic,
        pairs=[
            QAPairResponse(
                question=p.question,
                answer=p.answer,
                source_title=p.source_title,
                difficulty=p.difficulty,
            )
            for p in qa_set.pairs
        ],
        created_at=qa_set.created_at,
        difficulty=qa_set.difficulty,
    )


@router.post("/qna/{set_id}/export")
async def export_qna_set(
    set_id: str,
    body: QnAExportRequest,
    qna: Annotated[QnAService, Depends(get_qna)],
) -> Response:
    """Export a Q&A set as JSON or Markdown."""
    fmt = body.format if body.format in ("json", "markdown") else "json"
    content = qna.export_set(set_id, fmt=fmt)

    if fmt == "markdown":
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="qna_{set_id}.md"'},
        )
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="qna_{set_id}.json"'},
    )


# ── Interview Preparation ────────────────────────────────────────────────


@router.post("/interview/start", response_model=InterviewSessionResponse)
async def start_interview(
    body: InterviewStartRequest,
    interview: Annotated[InterviewService, Depends(get_interview)],
) -> InterviewSessionResponse:
    """Start a new interview preparation session."""
    mode = (
        InterviewMode(body.mode)
        if body.mode in ("behavioral", "technical", "mixed")
        else InterviewMode.MIXED
    )
    difficulty = (
        InterviewDifficulty(body.difficulty)
        if body.difficulty in ("beginner", "intermediate", "advanced")
        else InterviewDifficulty.INTERMEDIATE
    )

    session = interview.start_session(
        topic=body.topic,
        mode=mode,
        difficulty=difficulty,
        question_count=body.question_count,
        source_ids=body.source_ids,
    )

    current_q = session.questions[0] if session.questions else None
    return InterviewSessionResponse(
        id=session.id,
        topic=session.topic,
        mode=session.mode.value,
        difficulty=session.difficulty.value,
        current_index=session.current_index,
        total_questions=len(session.questions),
        completed=session.completed,
        current_question=(
            InterviewQuestionResponse(
                index=current_q.index,
                question=current_q.question,
            )
            if current_q
            else None
        ),
    )


@router.post("/interview/{session_id}/answer", response_model=InterviewAnswerResponse)
async def submit_interview_answer(
    session_id: str,
    body: InterviewAnswerRequest,
    interview: Annotated[InterviewService, Depends(get_interview)],
) -> InterviewAnswerResponse:
    """Submit an answer and get feedback + next question."""
    answered_q = interview.submit_answer(session_id, body.answer)
    session = interview.get_session(session_id)

    next_q = None
    completed = False
    if session:
        completed = session.completed
        if not completed and session.current_index < len(session.questions):
            nq = session.questions[session.current_index]
            next_q = InterviewQuestionResponse(index=nq.index, question=nq.question)

    return InterviewAnswerResponse(
        question=InterviewQuestionResponse(
            index=answered_q.index,
            question=answered_q.question,
            user_answer=answered_q.user_answer,
            feedback=answered_q.feedback,
            score=answered_q.score,
            model_answer=answered_q.model_answer,
            answered=answered_q.answered,
        ),
        next_question=next_q,
        completed=completed,
    )


@router.get("/interview/{session_id}/summary", response_model=InterviewSummaryResponse)
async def get_interview_summary(
    session_id: str,
    interview: Annotated[InterviewService, Depends(get_interview)],
) -> InterviewSummaryResponse:
    """Get the interview session summary with scores."""
    session = interview.get_session_summary(session_id)
    return InterviewSummaryResponse(
        id=session.id,
        topic=session.topic,
        completed=session.completed,
        overall_score=session.overall_score,
        overall_feedback=session.overall_feedback,
        questions=[
            InterviewQuestionResponse(
                index=q.index,
                question=q.question,
                user_answer=q.user_answer,
                feedback=q.feedback,
                score=q.score,
                model_answer=q.model_answer,
                answered=q.answered,
            )
            for q in session.questions
        ],
    )
