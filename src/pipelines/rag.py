"""Core RAG pipeline: retrieve → augment → generate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.catalog.service import CatalogService
    from src.models.embeddings import EmbeddingModel
    from src.models.llm import LLMClient
    from src.utils.vector_store import VectorStore

logger = get_logger(__name__)


@dataclass
class Citation:
    """A source citation for a RAG answer."""

    source_id: str
    source_title: str
    chunk_text: str
    relevance_score: float


@dataclass
class RAGResponse:
    """Response from the RAG pipeline."""

    answer: str
    citations: list[Citation] = field(default_factory=list)
    has_context: bool = True


class RAGPipeline:
    """Retrieve relevant context, augment prompt, generate answer."""

    def __init__(
        self,
        embedding_model: EmbeddingModel,
        vector_store: VectorStore,
        llm_client: LLMClient,
        catalog: CatalogService,
        top_k: int = 5,
        similarity_threshold: float = 0.3,
    ) -> None:
        self._embedding = embedding_model
        self._vector_store = vector_store
        self._llm = llm_client
        self._catalog = catalog
        self._top_k = top_k
        self._threshold = similarity_threshold

    def query(
        self,
        question: str,
        *,
        source_ids: list[str] | None = None,
        top_k: int | None = None,
        chat_history: list[dict[str, str]] | None = None,
        system_prompt: str = "",
    ) -> RAGResponse:
        """Run the full RAG pipeline for a question."""
        k = top_k or self._top_k

        # 1. Embed the question
        query_embedding = self._embedding.embed_query(question)

        # 2. Retrieve relevant chunks
        where_filter = None
        if source_ids:
            if len(source_ids) == 1:
                where_filter = {"source_id": source_ids[0]}
            else:
                where_filter = {"source_id": {"$in": source_ids}}

        results = self._vector_store.search(
            query_embedding=query_embedding,
            top_k=k,
            where=where_filter,
        )

        # Filter by similarity threshold
        relevant = [r for r in results if r.score >= self._threshold]

        if not relevant:
            return RAGResponse(
                answer=(
                    "I couldn't find relevant information in the indexed content "
                    "to answer this question. Try rephrasing your question or "
                    "indexing more relevant documents."
                ),
                has_context=False,
            )

        # 3. Build citations
        citations: list[Citation] = []
        source_cache: dict[str, str] = {}
        for r in relevant:
            sid = r.metadata.get("source_id", "")
            if sid not in source_cache:
                try:
                    source = self._catalog.get_source(sid)
                    source_cache[sid] = source.title
                except Exception:
                    source_cache[sid] = "Unknown"
            citations.append(
                Citation(
                    source_id=sid,
                    source_title=source_cache[sid],
                    chunk_text=r.text[:200],
                    relevance_score=r.score,
                )
            )

        # 4. Build augmented prompt
        context = "\n\n---\n\n".join(
            f"[Source: {c.source_title}]\n{r.text}"
            for r, c in zip(relevant, citations, strict=True)
        )

        history_text = ""
        if chat_history:
            history_lines = []
            for msg in chat_history[-6:]:  # Last 6 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_lines.append(f"{role}: {content}")
            history_text = "\n".join(history_lines) + "\n\n"

        prompt = (
            f"Answer the following question based on the provided context. "
            f"Cite your sources when possible. If the context doesn't contain "
            f"enough information, say so clearly.\n\n"
            f"Context:\n{context}\n\n"
            f"{history_text}"
            f"Question: {question}"
        )

        default_system = (
            "You are a helpful knowledge assistant. Answer questions accurately "
            "based on the provided context. Always cite which source your information "
            "comes from. If you're not sure about something, say so."
        )

        # 5. Generate answer
        answer = self._llm.generate(
            prompt,
            system=system_prompt or default_system,
            max_tokens=1024,
        )

        logger.info(
            "rag_query_completed",
            question_length=len(question),
            chunks_retrieved=len(relevant),
            answer_length=len(answer),
        )

        return RAGResponse(answer=answer, citations=citations, has_context=True)
