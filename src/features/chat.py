"""RAG chat feature with multi-turn conversation support."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.utils.cache import CacheStore
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.pipelines.rag import RAGPipeline

logger = get_logger(__name__)


@dataclass
class ChatMessage:
    """A single chat message."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    citations: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "citations": self.citations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatMessage:
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            citations=data.get("citations", []),
        )


@dataclass
class ChatSession:
    """A chat conversation session."""

    id: str
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    source_filter: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at.isoformat(),
            "source_filter": self.source_filter,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatSession:
        return cls(
            id=data["id"],
            messages=[ChatMessage.from_dict(m) for m in data.get("messages", [])],
            created_at=datetime.fromisoformat(data["created_at"]),
            source_filter=data.get("source_filter"),
        )


class ChatService:
    """Manages chat sessions and RAG-powered conversations."""

    def __init__(self, rag_pipeline: RAGPipeline, cache: CacheStore) -> None:
        self._rag = rag_pipeline
        self._cache = cache

    def _cache_key(self, session_id: str) -> str:
        return f"chat:{session_id}"

    def _save_session(self, session: ChatSession) -> None:
        self._cache.set(self._cache_key(session.id), session.to_dict())

    def _load_session(self, session_id: str) -> ChatSession | None:
        data = self._cache.get(self._cache_key(session_id))
        if data is None:
            return None
        return ChatSession.from_dict(data)

    def create_session(self, source_ids: list[str] | None = None) -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(
            id=str(uuid.uuid4()),
            source_filter=source_ids,
        )
        self._save_session(session)
        logger.info("chat_session_created", session_id=session.id)
        return session

    def send_message(
        self,
        session_id: str | None,
        message: str,
        *,
        source_ids: list[str] | None = None,
    ) -> tuple[str, ChatMessage]:
        """Send a message and get a RAG-powered response.

        Returns (session_id, assistant_message) so callers know which session was used.
        """
        # Get or create session
        session = None
        if session_id:
            session = self._load_session(session_id)
        if session is None:
            session = self.create_session(source_ids)

        # Add user message
        user_msg = ChatMessage(role="user", content=message)
        session.messages.append(user_msg)

        # Build chat history for context
        history = [
            {"role": m.role, "content": m.content}
            for m in session.messages[:-1]  # Exclude current message
        ]

        # Query RAG pipeline
        effective_source_ids = source_ids or session.source_filter
        response = self._rag.query(
            message,
            source_ids=effective_source_ids,
            chat_history=history if history else None,
        )

        # Add assistant message
        citation_dicts = [
            {
                "source_id": c.source_id,
                "source_title": c.source_title,
                "chunk_text": c.chunk_text,
                "relevance_score": c.relevance_score,
            }
            for c in response.citations
        ]
        assistant_msg = ChatMessage(
            role="assistant",
            content=response.answer,
            citations=citation_dicts,
        )
        session.messages.append(assistant_msg)
        self._save_session(session)

        logger.info(
            "chat_message_sent",
            session_id=session.id,
            has_context=response.has_context,
            citations=len(response.citations),
        )

        return session.id, assistant_msg

    def get_session(self, session_id: str) -> ChatSession | None:
        """Get a chat session by ID."""
        return self._load_session(session_id)

    def list_sessions(self) -> list[ChatSession]:
        """List all chat sessions."""
        keys = self._cache.keys("chat:*")
        sessions: list[ChatSession] = []
        for key in keys:
            data = self._cache.get(key)
            if data:
                sessions.append(ChatSession.from_dict(data))
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)
