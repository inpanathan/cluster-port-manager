"""LLM-based entity and relationship extraction from book chunks.

Uses the LLM to extract structured entities, relationships, and topics
from book text passages, with JSON output parsing and validation.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import TYPE_CHECKING, Protocol

from src.features.knowledge_graph.models import (
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractedTopic,
    ExtractionResult,
)
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.models.llm import LLMClient

logger = get_logger(__name__)

_EXTRACTION_PROMPT = """\
Extract entities, relationships, and topics from this book passage.
Book: {book_title}
Chapter: {chapter_title}

Return ONLY valid JSON with exactly this structure:
{{
  "entities": [
    {{"name": "...", "type": "...", "description": "...", "aliases": ["..."]}}
  ],
  "relationships": [
    {{"source_entity": "...", "target_entity": "...", "relationship_type": "...", \
"context": "..."}}
  ],
  "topics": [
    {{"name": "...", "description": "...", "parent_topic": null}}
  ]
}}

Entity types: person, organization, place, concept, technology, event, theory
Relationship types: related_to, part_of, precedes, supports, contradicts

Only extract significant entities and relationships. Skip generic terms.

Passage:
{chunk_text}
"""

_EXTRACTION_SYSTEM = (
    "You are an entity extraction assistant. Extract structured information from "
    "book passages. Return only valid JSON. Do not include any other text."
)

_VALID_ENTITY_TYPES = {e.value for e in EntityType}


class GraphExtractor(Protocol):
    """Protocol for entity/relationship extractors."""

    def extract_from_chunk(
        self, chunk_text: str, chapter_title: str, book_title: str
    ) -> ExtractionResult: ...

    def extract_from_book(self, chunks: list[dict], book_title: str) -> list[ExtractionResult]: ...


class LLMGraphExtractor:
    """Uses the LLM to extract entities and relationships from text."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    def extract_from_chunk(
        self, chunk_text: str, chapter_title: str, book_title: str
    ) -> ExtractionResult:
        """Extract entities and relationships from a single chunk."""
        if len(chunk_text.strip()) < 50:
            return ExtractionResult()

        prompt = _EXTRACTION_PROMPT.format(
            book_title=book_title,
            chapter_title=chapter_title,
            chunk_text=chunk_text[:3000],
        )

        start = time.perf_counter()
        try:
            raw = self._llm.generate(prompt, system=_EXTRACTION_SYSTEM, max_tokens=2048)
            result = _parse_extraction_result(raw)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.info(
                "entity_extraction_completed",
                entities=len(result.entities),
                relationships=len(result.relationships),
                topics=len(result.topics),
                latency_ms=elapsed_ms,
            )
            return result
        except Exception as e:
            logger.warning("entity_extraction_failed", error=str(e))
            # Retry with simpler prompt
            try:
                simple_prompt = (
                    f"List the key entities (people, places, concepts) mentioned in "
                    f'this text as JSON: {{"entities": [{{"name": "...", '
                    f'"type": "concept", "description": "..."}}]}}\n\n'
                    f"{chunk_text[:2000]}"
                )
                raw = self._llm.generate(simple_prompt, system=_EXTRACTION_SYSTEM, max_tokens=1024)
                return _parse_extraction_result(raw)
            except Exception:
                return ExtractionResult()

    def extract_from_book(self, chunks: list[dict], book_title: str) -> list[ExtractionResult]:
        """Extract entities from all chunks of a book.

        Args:
            chunks: List of dicts with keys: text, chapter_title
            book_title: Title of the book
        """
        results: list[ExtractionResult] = []
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            logger.info(
                "entity_extraction_progress",
                chunk_index=i + 1,
                total_chunks=total,
                book_title=book_title,
            )
            result = self.extract_from_chunk(
                chunk_text=chunk.get("text", ""),
                chapter_title=chunk.get("chapter_title", ""),
                book_title=book_title,
            )
            results.append(result)
        return results


class MockGraphExtractor:
    """Deterministic mock extractor for testing.

    Generates entities and relationships based on content hash
    for reproducible test behavior.
    """

    def extract_from_chunk(
        self, chunk_text: str, chapter_title: str, book_title: str
    ) -> ExtractionResult:
        if len(chunk_text.strip()) < 50:
            return ExtractionResult()

        h = hashlib.md5(chunk_text.encode()).hexdigest()  # noqa: S324
        entity_types = list(EntityType)
        idx = int(h[:2], 16) % len(entity_types)

        entities = [
            ExtractedEntity(
                name=f"Entity_{h[:6]}",
                type=entity_types[idx],
                description=f"Extracted from '{chapter_title}'",
                aliases=[],
            ),
            ExtractedEntity(
                name=f"Concept_{h[6:12]}",
                type=EntityType.CONCEPT,
                description=f"Key concept from {book_title}",
            ),
        ]
        relationships = [
            ExtractedRelationship(
                source_entity=entities[0].name,
                target_entity=entities[1].name,
                relationship_type="related_to",
                context=chunk_text[:100],
            ),
        ]
        topics = [
            ExtractedTopic(
                name=f"Topic_{h[12:18]}",
                description=f"Topic from chapter '{chapter_title}'",
            ),
        ]
        return ExtractionResult(entities=entities, relationships=relationships, topics=topics)

    def extract_from_book(self, chunks: list[dict], book_title: str) -> list[ExtractionResult]:
        return [
            self.extract_from_chunk(
                chunk_text=c.get("text", ""),
                chapter_title=c.get("chapter_title", ""),
                book_title=book_title,
            )
            for c in chunks
        ]


def create_graph_extractor(backend: str, llm_client: LLMClient) -> GraphExtractor:
    """Factory for graph extractors."""
    if backend == "mock":
        return MockGraphExtractor()
    return LLMGraphExtractor(llm_client)


def _parse_extraction_result(raw: str) -> ExtractionResult:
    """Parse LLM output into an ExtractionResult."""
    # Try to extract JSON from the response
    text = raw.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()

    data = json.loads(text)

    entities = []
    for e in data.get("entities", []):
        etype = e.get("type", "concept").lower()
        if etype not in _VALID_ENTITY_TYPES:
            etype = "concept"
        entities.append(
            ExtractedEntity(
                name=e.get("name", ""),
                type=EntityType(etype),
                description=e.get("description", ""),
                aliases=e.get("aliases", []),
            )
        )

    relationships = [
        ExtractedRelationship(
            source_entity=r.get("source_entity", ""),
            target_entity=r.get("target_entity", ""),
            relationship_type=r.get("relationship_type", "related_to"),
            context=r.get("context", ""),
            confidence=r.get("confidence", 0.8),
        )
        for r in data.get("relationships", [])
    ]

    topics = [
        ExtractedTopic(
            name=t.get("name", ""),
            description=t.get("description", ""),
            parent_topic=t.get("parent_topic"),
        )
        for t in data.get("topics", [])
    ]

    return ExtractionResult(entities=entities, relationships=relationships, topics=topics)
