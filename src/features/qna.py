"""Q&A generation feature."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from src.utils.cache import CacheStore
from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.catalog.service import CatalogService
    from src.models.embeddings import EmbeddingModel
    from src.models.llm import LLMClient
    from src.utils.vector_store import VectorStore

logger = get_logger(__name__)


class DifficultyLevel(StrEnum):
    """Difficulty level for generated questions."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class QuestionType(StrEnum):
    """Type of question."""

    FACTUAL = "factual"
    CONCEPTUAL = "conceptual"
    APPLICATION = "application"


@dataclass
class QAPair:
    """A single question-answer pair."""

    question: str
    answer: str
    source_id: str = ""
    source_title: str = ""
    difficulty: str = ""
    question_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "source_id": self.source_id,
            "source_title": self.source_title,
            "difficulty": self.difficulty,
            "question_type": self.question_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QAPair:
        return cls(
            question=data["question"],
            answer=data["answer"],
            source_id=data.get("source_id", ""),
            source_title=data.get("source_title", ""),
            difficulty=data.get("difficulty", ""),
            question_type=data.get("question_type", ""),
        )


@dataclass
class QASet:
    """A set of generated Q&A pairs."""

    id: str
    topic: str
    pairs: list[QAPair] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    difficulty: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "pairs": [p.to_dict() for p in self.pairs],
            "created_at": self.created_at.isoformat(),
            "difficulty": self.difficulty,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QASet:
        return cls(
            id=data["id"],
            topic=data["topic"],
            pairs=[QAPair.from_dict(p) for p in data.get("pairs", [])],
            created_at=datetime.fromisoformat(data["created_at"]),
            difficulty=data.get("difficulty", ""),
        )


class QnAService:
    """Generates question-and-answer pairs from indexed content."""

    def __init__(
        self,
        llm_client: LLMClient,
        vector_store: VectorStore,
        embedding_model: EmbeddingModel,
        catalog: CatalogService,
        cache: CacheStore,
    ) -> None:
        self._llm = llm_client
        self._vector_store = vector_store
        self._embedding = embedding_model
        self._catalog = catalog
        self._cache = cache

    def _cache_key(self, set_id: str) -> str:
        return f"qna:{set_id}"

    def _save_set(self, qa_set: QASet) -> None:
        self._cache.set(self._cache_key(qa_set.id), qa_set.to_dict())

    def _load_set(self, set_id: str) -> QASet | None:
        data = self._cache.get(self._cache_key(set_id))
        if data is None:
            return None
        return QASet.from_dict(data)

    def generate(
        self,
        *,
        topic: str | None = None,
        source_ids: list[str] | None = None,
        count: int = 10,
        difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
        question_types: list[QuestionType] | None = None,
    ) -> QASet:
        """Generate Q&A pairs from indexed content."""
        if not topic and not source_ids:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Either topic or source_ids is required",
            )

        # Retrieve relevant content
        if source_ids:
            content_parts: list[str] = []
            source_titles: dict[str, str] = {}
            for sid in source_ids:
                source = self._catalog.get_source(sid)
                source_titles[sid] = source.title
                dummy_embedding = self._embedding.embed_query(source.title)
                results = self._vector_store.search(
                    query_embedding=dummy_embedding,
                    top_k=30,
                    where={"source_id": sid},
                )
                chunks = sorted(results, key=lambda r: r.metadata.get("chunk_index", 0))
                content_parts.extend(r.text for r in chunks)
        else:
            query_embedding = self._embedding.embed_query(topic or "")
            results = self._vector_store.search(query_embedding=query_embedding, top_k=20)
            content_parts = [r.text for r in results]
            source_titles = {}
            for r in results:
                sid = r.metadata.get("source_id", "")
                if sid and sid not in source_titles:
                    try:
                        source = self._catalog.get_source(sid)
                        source_titles[sid] = source.title
                    except Exception:
                        source_titles[sid] = "Unknown"

        if not content_parts:
            raise AppError(
                code=ErrorCode.NO_RELEVANT_CONTEXT,
                message="No relevant content found to generate Q&A",
            )

        combined = "\n\n".join(content_parts[:15])  # Limit context size
        types_str = ", ".join(question_types or ["factual", "conceptual", "application"])

        prompt = (
            f"Based on the following content, generate exactly {count} "
            f"question-and-answer pairs.\n\n"
            f"Requirements:\n"
            f"- Difficulty level: {difficulty.value}\n"
            f"- Question types: {types_str}\n"
            f"- Each answer should be comprehensive and accurate\n"
            f"- Questions should test understanding, not just recall\n\n"
            f"Format your response as a JSON array of objects with 'question' and 'answer' keys.\n"
            f"Example: [{{'question': '...', 'answer': '...'}}]\n\n"
            f"Content:\n{combined}"
        )

        system = (
            "You are an expert educator. Generate high-quality questions and detailed answers "
            "based strictly on the provided content. Return ONLY valid JSON."
        )

        response = self._llm.generate(prompt, system=system, max_tokens=4096)

        # Parse Q&A pairs
        pairs = self._parse_qa_response(response, source_titles, difficulty.value)

        qa_set = QASet(
            id=str(uuid.uuid4()),
            topic=topic or "Selected sources",
            pairs=pairs[:count],
            difficulty=difficulty.value,
        )
        self._save_set(qa_set)

        logger.info(
            "qna_generated",
            set_id=qa_set.id,
            topic=qa_set.topic,
            pair_count=len(qa_set.pairs),
        )

        return qa_set

    def get_set(self, set_id: str) -> QASet | None:
        """Get a Q&A set by ID."""
        return self._load_set(set_id)

    def export_set(self, set_id: str, *, fmt: str = "json") -> str:
        """Export a Q&A set as JSON or Markdown."""
        qa_set = self._load_set(set_id)
        if qa_set is None:
            raise AppError(
                code=ErrorCode.NOT_FOUND,
                message=f"Q&A set not found: {set_id}",
            )

        if fmt == "markdown":
            lines = [f"# Q&A: {qa_set.topic}\n"]
            for i, pair in enumerate(qa_set.pairs, 1):
                lines.append(f"## Question {i}")
                lines.append(f"{pair.question}\n")
                lines.append(f"**Answer:** {pair.answer}\n")
                if pair.source_title:
                    lines.append(f"*Source: {pair.source_title}*\n")
            return "\n".join(lines)

        # JSON format
        data = {
            "id": qa_set.id,
            "topic": qa_set.topic,
            "difficulty": qa_set.difficulty,
            "pairs": [
                {
                    "question": p.question,
                    "answer": p.answer,
                    "source_title": p.source_title,
                }
                for p in qa_set.pairs
            ],
        }
        return json.dumps(data, indent=2)

    def _parse_qa_response(
        self, response: str, source_titles: dict[str, str], difficulty: str
    ) -> list[QAPair]:
        """Parse LLM response into Q&A pairs."""
        # Try JSON parsing
        try:
            # Find JSON array in response
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                pairs: list[QAPair] = []
                first_source_id = next(iter(source_titles), "")
                first_source_title = source_titles.get(first_source_id, "")
                for item in data:
                    pairs.append(
                        QAPair(
                            question=item.get("question", ""),
                            answer=item.get("answer", ""),
                            source_id=first_source_id,
                            source_title=first_source_title,
                            difficulty=difficulty,
                        )
                    )
                return pairs
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback: parse Q/A lines
        pairs = []
        lines = response.strip().split("\n")
        current_q = ""
        current_a = ""
        first_source_id = next(iter(source_titles), "")
        first_source_title = source_titles.get(first_source_id, "")

        for line in lines:
            line = line.strip()
            if line.startswith(("Q:", "Q.", "Question")):
                if current_q and current_a:
                    pairs.append(
                        QAPair(
                            question=current_q,
                            answer=current_a,
                            source_id=first_source_id,
                            source_title=first_source_title,
                            difficulty=difficulty,
                        )
                    )
                current_q = line.split(":", 1)[-1].strip() if ":" in line else line
                current_a = ""
            elif line.startswith(("A:", "A.", "Answer")):
                current_a = line.split(":", 1)[-1].strip() if ":" in line else line

        if current_q and current_a:
            pairs.append(
                QAPair(
                    question=current_q,
                    answer=current_a,
                    source_id=first_source_id,
                    source_title=first_source_title,
                    difficulty=difficulty,
                )
            )

        return pairs
