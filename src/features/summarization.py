"""Content summarization feature."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.catalog.service import CatalogService
    from src.models.embeddings import EmbeddingModel
    from src.models.llm import LLMClient
    from src.utils.vector_store import VectorStore

logger = get_logger(__name__)


class SummaryMode(StrEnum):
    """Summary output mode."""

    SHORT = "short"
    DETAILED = "detailed"


@dataclass
class SummaryResult:
    """Result of a summarization request."""

    summary: str
    mode: SummaryMode
    source_ids: list[str]
    source_titles: list[str]


class SummarizationService:
    """Generates summaries of indexed content."""

    def __init__(
        self,
        llm_client: LLMClient,
        vector_store: VectorStore,
        embedding_model: EmbeddingModel,
        catalog: CatalogService,
    ) -> None:
        self._llm = llm_client
        self._vector_store = vector_store
        self._embedding = embedding_model
        self._catalog = catalog

    def summarize_sources(
        self,
        source_ids: list[str],
        *,
        mode: SummaryMode = SummaryMode.SHORT,
    ) -> SummaryResult:
        """Generate a summary of one or more sources."""
        if not source_ids:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="At least one source ID is required",
            )

        # Collect content from each source
        all_content: list[str] = []
        titles: list[str] = []

        for sid in source_ids:
            source = self._catalog.get_source(sid)
            titles.append(source.title)

            # Retrieve chunks for this source
            dummy_embedding = self._embedding.embed_query(source.title)
            results = self._vector_store.search(
                query_embedding=dummy_embedding,
                top_k=50,
                where={"source_id": sid},
            )
            chunks = sorted(results, key=lambda r: r.metadata.get("chunk_index", 0))
            source_text = "\n\n".join(r.text for r in chunks)
            all_content.append(f"[Source: {source.title}]\n{source_text}")

        combined = "\n\n---\n\n".join(all_content)

        # Build prompt based on mode
        if mode == SummaryMode.SHORT:
            prompt = (
                f"Provide a concise summary (1-3 paragraphs) of the following content. "
                f"Focus on the key takeaways and main points.\n\n"
                f"Content:\n{combined}"
            )
        else:
            prompt = (
                f"Provide a detailed, comprehensive summary of the following content. "
                f"Organize the summary with clear sections and subsections. "
                f"Include key points, important details, and notable insights. "
                f"If there are multiple sources, organize by source with clear attribution.\n\n"
                f"Content:\n{combined}"
            )

        system = (
            "You are a skilled summarizer. Create clear, accurate summaries that "
            "capture the essential information from the provided content. "
            "Never fabricate information not present in the source material."
        )

        summary = self._llm.generate(prompt, system=system, max_tokens=2048)

        logger.info(
            "summary_generated",
            mode=mode.value,
            source_count=len(source_ids),
            summary_length=len(summary),
        )

        return SummaryResult(
            summary=summary,
            mode=mode,
            source_ids=source_ids,
            source_titles=titles,
        )

    def summarize_topic(
        self,
        topic: str,
        *,
        mode: SummaryMode = SummaryMode.SHORT,
    ) -> SummaryResult:
        """Summarize a topic across all indexed sources."""
        query_embedding = self._embedding.embed_query(topic)
        results = self._vector_store.search(query_embedding=query_embedding, top_k=20)

        if not results:
            raise AppError(
                code=ErrorCode.NO_RELEVANT_CONTEXT,
                message=f"No relevant content found for topic: {topic}",
                context={"topic": topic},
            )

        # Group by source
        source_ids = list({r.metadata.get("source_id", "") for r in results})
        titles: list[str] = []
        for sid in source_ids:
            try:
                source = self._catalog.get_source(sid)
                titles.append(source.title)
            except Exception:
                titles.append("Unknown")

        combined = "\n\n---\n\n".join(r.text for r in results)

        if mode == SummaryMode.SHORT:
            prompt = (
                f"Provide a concise summary (1-3 paragraphs) about '{topic}' "
                f"based on the following content.\n\n"
                f"Content:\n{combined}"
            )
        else:
            prompt = (
                f"Provide a detailed summary about '{topic}' based on the following content. "
                f"Organize by subtopics with clear sections.\n\n"
                f"Content:\n{combined}"
            )

        system = (
            "You are a skilled summarizer. Create clear, accurate summaries that "
            "capture the essential information. Never fabricate information."
        )

        summary = self._llm.generate(prompt, system=system, max_tokens=2048)

        return SummaryResult(
            summary=summary,
            mode=mode,
            source_ids=source_ids,
            source_titles=titles,
        )
