"""API routes for the Knowledge Hub application.

This router is mounted at /api/v1 in main.py.
"""

from __future__ import annotations

import mimetypes
from typing import Annotated

from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.responses import Response

from src.api.dependencies import (
    get_book_embedding,
    get_books,
    get_catalog,
    get_chat,
    get_file_store,
    get_ingestion,
    get_interview,
    get_knowledge_graph_service,
    get_qna,
    get_summarization,
    get_vector_store,
)
from src.api.schemas import (
    BookDetailResponse,
    BookEmbedRequest,
    BookEmbedResponse,
    BookListApiResponse,
    BookProcessingStatusResponse,
    BookSummaryResponse,
    BookUpdateRequest,
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
from src.books.models import BookUpdate
from src.books.service import BookService
from src.catalog.models import SourceUpdate
from src.catalog.service import CatalogService
from src.data.file_store import FileStore
from src.data.ingestion import IngestionPipeline
from src.features.chat import ChatService
from src.features.interview import DifficultyLevel as InterviewDifficulty
from src.features.interview import InterviewMode, InterviewService
from src.features.knowledge_graph.service import KnowledgeGraphService
from src.features.qna import DifficultyLevel as QnADifficulty
from src.features.qna import QnAService
from src.features.summarization import SummarizationService, SummaryMode
from src.pipelines.book_embedding import BookEmbeddingPipeline
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
        include_books=body.include_books,
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


# ── Books ────────────────────────────────────────────────────────────────


@router.get("/books", response_model=BookListApiResponse)
async def list_books(
    books: Annotated[BookService, Depends(get_books)],
    author: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    embedding_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> BookListApiResponse:
    """List all books with optional filters."""
    result = books.list_books(
        author=author,
        tag=tag,
        search=search,
        embedding_status=embedding_status,
        limit=limit,
        offset=offset,
    )
    return BookListApiResponse(
        books=[
            BookSummaryResponse(
                id=b.id,
                title=b.title,
                author=b.author,
                file_format=b.file_format,
                publication_year=b.publication_year,
                cover_image_path=b.cover_image_path,
                tags=b.tags,
                embedding_status=b.embedding_status,
            )
            for b in result.books
        ],
        total=result.total,
    )


@router.get("/books/{book_id}", response_model=BookDetailResponse)
async def get_book(
    book_id: str,
    books: Annotated[BookService, Depends(get_books)],
) -> BookDetailResponse:
    """Get full book detail."""
    book = books.get_book(book_id)
    return BookDetailResponse(
        id=book.id,
        title=book.title,
        author=book.author,
        isbn=book.isbn,
        publisher=book.publisher,
        publication_year=book.publication_year,
        language=book.language,
        page_count=book.page_count,
        file_format=book.file_format,
        file_size_bytes=book.file_size_bytes,
        cover_image_path=book.cover_image_path,
        description=book.description,
        table_of_contents=book.table_of_contents,
        tags=book.tags,
        drive_folder_path=book.drive_folder_path,
        drive_file_id=book.drive_file_id,
        created_at=book.created_at,
        processed_at=book.processed_at,
        embedding_status=book.embedding_status,
        graph_status=book.graph_status,
        source_id=book.source_id,
    )


@router.put("/books/{book_id}", response_model=BookDetailResponse)
async def update_book(
    book_id: str,
    body: BookUpdateRequest,
    books: Annotated[BookService, Depends(get_books)],
) -> BookDetailResponse:
    """Update book metadata (title, author, tags, description)."""
    updated = books.update_book(
        book_id,
        BookUpdate(
            title=body.title, author=body.author, tags=body.tags, description=body.description
        ),
    )
    return BookDetailResponse(
        id=updated.id,
        title=updated.title,
        author=updated.author,
        isbn=updated.isbn,
        publisher=updated.publisher,
        publication_year=updated.publication_year,
        language=updated.language,
        page_count=updated.page_count,
        file_format=updated.file_format,
        file_size_bytes=updated.file_size_bytes,
        cover_image_path=updated.cover_image_path,
        description=updated.description,
        table_of_contents=updated.table_of_contents,
        tags=updated.tags,
        drive_folder_path=updated.drive_folder_path,
        drive_file_id=updated.drive_file_id,
        created_at=updated.created_at,
        processed_at=updated.processed_at,
        embedding_status=updated.embedding_status,
        graph_status=updated.graph_status,
        source_id=updated.source_id,
    )


@router.delete("/books/{book_id}", status_code=204)
async def delete_book(
    book_id: str,
    books: Annotated[BookService, Depends(get_books)],
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
) -> None:
    """Delete a book, its file, and its vectors."""
    from pathlib import Path as _Path

    from src.utils.config import settings as _settings

    book = books.get_book(book_id)
    # Clean up files
    if book.file_path:
        _Path(book.file_path).unlink(missing_ok=True)
    if book.cover_image_path:
        _Path(book.cover_image_path).unlink(missing_ok=True)
    # Clean up vectors from books collection
    vector_store.delete_book_vectors(_settings.books.qdrant_collection, book_id)
    books.delete_book(book_id)


@router.get("/books/{book_id}/download")
async def download_book(
    book_id: str,
    books: Annotated[BookService, Depends(get_books)],
) -> Response:
    """Download the original book file."""
    from pathlib import Path as _Path

    from src.utils.config import settings as _settings

    book = books.get_book(book_id)
    if not book.file_path:
        raise AppError(
            code=ErrorCode.FILE_NOT_FOUND,
            message="Book file path not set",
            context={"book_id": book_id},
        )

    file_path = _Path(book.file_path).resolve()
    storage_dir = _Path(_settings.books.storage_dir).resolve()
    if not str(file_path).startswith(str(storage_dir)):
        raise AppError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid file path",
            context={"book_id": book_id},
        )

    if not file_path.exists():
        raise AppError(
            code=ErrorCode.FILE_NOT_FOUND,
            message="Book file not found on disk",
            context={"book_id": book_id, "path": str(file_path)},
        )

    file_bytes = file_path.read_bytes()
    filename = file_path.name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/books/{book_id}/cover")
async def get_book_cover(
    book_id: str,
    books: Annotated[BookService, Depends(get_books)],
) -> Response:
    """Get the book's cover image."""
    from pathlib import Path as _Path

    from src.utils.config import settings as _settings

    book = books.get_book(book_id)
    if not book.cover_image_path:
        raise AppError(
            code=ErrorCode.FILE_NOT_FOUND,
            message="No cover image available",
            context={"book_id": book_id},
        )

    cover_path = _Path(book.cover_image_path).resolve()
    covers_dir = _Path(_settings.books.covers_dir).resolve()
    if not str(cover_path).startswith(str(covers_dir)):
        raise AppError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid cover path",
            context={"book_id": book_id},
        )

    if not cover_path.exists():
        raise AppError(
            code=ErrorCode.FILE_NOT_FOUND,
            message="Cover image file not found",
            context={"book_id": book_id},
        )

    cover_bytes = cover_path.read_bytes()
    content_type = mimetypes.guess_type(cover_path.name)[0] or "image/jpeg"
    return Response(content=cover_bytes, media_type=content_type)


@router.post("/books/{book_id}/embed", response_model=BookEmbedResponse)
async def embed_book(
    book_id: str,
    body: BookEmbedRequest,
    pipeline: Annotated[BookEmbeddingPipeline, Depends(get_book_embedding)],
) -> BookEmbedResponse:
    """Trigger embedding for a single book."""
    result = pipeline.process_book(book_id, force=body.force)
    return BookEmbedResponse(
        book_id=result.book_id,
        chunk_count=result.chunk_count,
        total_tokens=result.total_tokens,
        duration_ms=result.duration_ms,
        validation_passed=result.validation_passed,
        skipped=result.skipped,
        error=result.error,
    )


@router.get("/books/{book_id}/status", response_model=BookProcessingStatusResponse)
async def get_book_status(
    book_id: str,
    books: Annotated[BookService, Depends(get_books)],
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
) -> BookProcessingStatusResponse:
    """Get the processing status of a book."""
    from src.utils.config import settings as _settings

    book = books.get_book(book_id)
    chunk_count = None
    if book.embedding_status == "completed":
        chunk_count = vector_store.count_collection(_settings.books.qdrant_collection)
    return BookProcessingStatusResponse(
        embedding_status=book.embedding_status,
        graph_status=book.graph_status,
        chunk_count=chunk_count,
        source_id=book.source_id,
    )


# ── Knowledge Graph ──────────────────────────────────────────────────────


@router.get("/graph/search")
async def search_graph(
    q: str,
    kg_service: Annotated[
        KnowledgeGraphService,
        Depends(get_knowledge_graph_service),
    ],
    type: str | None = None,
    limit: int = 20,
) -> dict:
    """Search entities in the knowledge graph."""
    results = kg_service.search_entities(q, entity_type=type, limit=limit)
    return {
        "results": [
            {
                "id": r.node.id,
                "label": r.node.label,
                "name": r.node.name,
                "type": r.node.type,
                "properties": r.node.properties,
                "connections_count": r.node.connections_count,
                "relevance_score": r.relevance_score,
            }
            for r in results
        ],
        "total": len(results),
    }


@router.get("/graph/entity/{entity_id}")
async def get_graph_entity(
    entity_id: str,
    kg_service: Annotated[
        KnowledgeGraphService,
        Depends(get_knowledge_graph_service),
    ],
    depth: int = 1,
) -> dict:
    """Get an entity and its neighborhood."""
    neighborhood = kg_service.get_entity(entity_id, depth=depth)
    return {
        "center_node": {
            "id": neighborhood.center_node.id,
            "label": neighborhood.center_node.label,
            "name": neighborhood.center_node.name,
            "type": neighborhood.center_node.type,
            "properties": neighborhood.center_node.properties,
        },
        "nodes": [
            {
                "id": n.id,
                "label": n.label,
                "name": n.name,
                "type": n.type,
                "properties": n.properties,
                "connections_count": n.connections_count,
            }
            for n in neighborhood.nodes
        ],
        "edges": [
            {"source": e.source, "target": e.target, "relationship": e.relationship}
            for e in neighborhood.edges
        ],
    }


@router.get("/graph/entity/{entity_id}/path/{target_id}")
async def find_graph_path(
    entity_id: str,
    target_id: str,
    kg_service: Annotated[
        KnowledgeGraphService,
        Depends(get_knowledge_graph_service),
    ],
    max_depth: int = 5,
) -> dict:
    """Find the shortest path between two entities."""
    path = kg_service.find_path(entity_id, target_id, max_depth=max_depth)
    if path is None:
        return {"found": False, "nodes": [], "edges": [], "length": 0}
    return {
        "found": True,
        "nodes": [
            {"id": n.id, "label": n.label, "name": n.name, "type": n.type} for n in path.nodes
        ],
        "edges": [
            {"source": e.source, "target": e.target, "relationship": e.relationship}
            for e in path.edges
        ],
        "length": path.length,
    }


@router.get("/graph/book/{book_id}/entities")
async def get_book_graph_entities(
    book_id: str,
    kg_service: Annotated[
        KnowledgeGraphService,
        Depends(get_knowledge_graph_service),
    ],
) -> dict:
    """Get all entities from a specific book's graph."""
    entities = kg_service.get_book_entities(book_id)
    return {
        "book_id": book_id,
        "entities": [
            {
                "id": e.id,
                "label": e.label,
                "name": e.name,
                "type": e.type,
                "properties": e.properties,
                "connections_count": e.connections_count,
            }
            for e in entities
        ],
        "total": len(entities),
    }


@router.get("/graph/book/{book_id}/related")
async def get_related_books_graph(
    book_id: str,
    kg_service: Annotated[
        KnowledgeGraphService,
        Depends(get_knowledge_graph_service),
    ],
) -> dict:
    """Get books related via shared entities."""
    related = kg_service.get_related_books(book_id)
    return {
        "book_id": book_id,
        "related": [
            {
                "book_id": r.book_id,
                "title": r.title,
                "author": r.author,
                "shared_entity_count": r.shared_entity_count,
                "shared_topic_count": r.shared_topic_count,
            }
            for r in related
        ],
    }


@router.get("/graph/topics")
async def get_topic_taxonomy(
    kg_service: Annotated[
        KnowledgeGraphService,
        Depends(get_knowledge_graph_service),
    ],
) -> dict:
    """Get the hierarchical topic structure."""
    topics = kg_service.get_topic_taxonomy()
    return {"topics": [t.model_dump() for t in topics]}


@router.get("/graph/stats")
async def get_graph_stats(
    kg_service: Annotated[
        KnowledgeGraphService,
        Depends(get_knowledge_graph_service),
    ],
) -> dict:
    """Get knowledge graph statistics."""
    stats = kg_service.get_stats()
    return {
        "node_counts": stats.node_counts,
        "relationship_counts": stats.relationship_counts,
        "total_nodes": stats.total_nodes,
        "total_relationships": stats.total_relationships,
    }
