"""Interview preparation feature."""

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


class InterviewMode(StrEnum):
    """Interview question mode."""

    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    MIXED = "mixed"


class DifficultyLevel(StrEnum):
    """Interview difficulty level."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass
class InterviewQuestion:
    """A single interview question with evaluation."""

    index: int
    question: str
    user_answer: str = ""
    feedback: str = ""
    score: float = 0.0
    model_answer: str = ""
    answered: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "question": self.question,
            "user_answer": self.user_answer,
            "feedback": self.feedback,
            "score": self.score,
            "model_answer": self.model_answer,
            "answered": self.answered,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InterviewQuestion:
        return cls(
            index=data["index"],
            question=data["question"],
            user_answer=data.get("user_answer", ""),
            feedback=data.get("feedback", ""),
            score=data.get("score", 0.0),
            model_answer=data.get("model_answer", ""),
            answered=data.get("answered", False),
        )


@dataclass
class InterviewSession:
    """An interview preparation session."""

    id: str
    topic: str
    mode: InterviewMode
    difficulty: DifficultyLevel
    questions: list[InterviewQuestion] = field(default_factory=list)
    current_index: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed: bool = False
    overall_score: float = 0.0
    overall_feedback: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "mode": self.mode.value,
            "difficulty": self.difficulty.value,
            "questions": [q.to_dict() for q in self.questions],
            "current_index": self.current_index,
            "created_at": self.created_at.isoformat(),
            "completed": self.completed,
            "overall_score": self.overall_score,
            "overall_feedback": self.overall_feedback,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InterviewSession:
        return cls(
            id=data["id"],
            topic=data["topic"],
            mode=InterviewMode(data["mode"]),
            difficulty=DifficultyLevel(data["difficulty"]),
            questions=[InterviewQuestion.from_dict(q) for q in data.get("questions", [])],
            current_index=data.get("current_index", 0),
            created_at=datetime.fromisoformat(data["created_at"]),
            completed=data.get("completed", False),
            overall_score=data.get("overall_score", 0.0),
            overall_feedback=data.get("overall_feedback", ""),
        )


class InterviewService:
    """Manages interview preparation sessions."""

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

    def _cache_key(self, session_id: str) -> str:
        return f"interview:{session_id}"

    def _save_session(self, session: InterviewSession) -> None:
        self._cache.set(self._cache_key(session.id), session.to_dict())

    def _load_session(self, session_id: str) -> InterviewSession | None:
        data = self._cache.get(self._cache_key(session_id))
        if data is None:
            return None
        return InterviewSession.from_dict(data)

    def start_session(
        self,
        topic: str,
        *,
        mode: InterviewMode = InterviewMode.MIXED,
        difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
        question_count: int = 10,
        source_ids: list[str] | None = None,
    ) -> InterviewSession:
        """Start a new interview preparation session."""
        # Retrieve relevant content
        query_embedding = self._embedding.embed_query(topic)

        where_filter: dict | None = None
        if source_ids:
            if len(source_ids) == 1:
                where_filter = {"source_id": source_ids[0]}
            else:
                where_filter = {"source_id": {"$in": source_ids}}  # type: ignore[dict-item]

        results = self._vector_store.search(
            query_embedding=query_embedding,
            top_k=20,
            where=where_filter,
        )

        if not results:
            raise AppError(
                code=ErrorCode.NO_RELEVANT_CONTEXT,
                message=f"No relevant content found for topic: {topic}",
                context={"topic": topic},
            )

        context = "\n\n".join(r.text for r in results[:10])

        # Generate questions
        prompt = (
            f"Generate exactly {question_count} interview questions for the topic: '{topic}'\n\n"
            f"Requirements:\n"
            f"- Interview mode: {mode.value}\n"
            f"- Difficulty: {difficulty.value}\n"
            f"- Questions should be based on the provided content\n"
            f"- Mix of open-ended and specific questions\n\n"
            f"Format as a JSON array of strings (just the questions).\n"
            f'Example: ["Question 1?", "Question 2?"]\n\n'
            f"Content:\n{context}"
        )

        system = (
            "You are an expert interviewer. Generate realistic, insightful interview "
            "questions that test deep understanding. Return ONLY valid JSON."
        )

        response = self._llm.generate(prompt, system=system, max_tokens=2048)
        questions = self._parse_questions(response, question_count)

        session = InterviewSession(
            id=str(uuid.uuid4()),
            topic=topic,
            mode=mode,
            difficulty=difficulty,
            questions=[InterviewQuestion(index=i, question=q) for i, q in enumerate(questions)],
        )
        self._save_session(session)

        logger.info(
            "interview_session_started",
            session_id=session.id,
            topic=topic,
            question_count=len(questions),
        )

        return session

    def submit_answer(self, session_id: str, answer: str) -> InterviewQuestion:
        """Submit an answer for the current question and get feedback."""
        session = self._get_session(session_id)

        if session.completed:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Interview session is already completed",
            )

        if session.current_index >= len(session.questions):
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="All questions have been answered",
            )

        question = session.questions[session.current_index]
        question.user_answer = answer

        # Retrieve relevant context for evaluation
        query_embedding = self._embedding.embed_query(question.question)
        results = self._vector_store.search(query_embedding=query_embedding, top_k=5)
        context = "\n\n".join(r.text for r in results)

        # Evaluate answer
        prompt = (
            f"Evaluate the following interview answer.\n\n"
            f"Question: {question.question}\n\n"
            f"Candidate's Answer: {answer}\n\n"
            f"Reference Material:\n{context}\n\n"
            f"Provide:\n"
            f"1. A score from 0 to 10\n"
            f"2. Strengths of the answer\n"
            f"3. Areas for improvement\n"
            f"4. A model answer based on the reference material\n\n"
            f'Format as JSON: {{"score": N, "feedback": "...", "model_answer": "..."}}'
        )

        system = (
            "You are an expert interview evaluator. Be fair, constructive, and specific. "
            "Return ONLY valid JSON."
        )

        response = self._llm.generate(prompt, system=system, max_tokens=1024)
        self._parse_evaluation(question, response)
        question.answered = True

        # Advance to next question
        session.current_index += 1

        # Check if session is complete
        if session.current_index >= len(session.questions):
            self._complete_session(session)

        self._save_session(session)
        return question

    def get_session(self, session_id: str) -> InterviewSession | None:
        """Get an interview session by ID."""
        return self._load_session(session_id)

    def get_session_summary(self, session_id: str) -> InterviewSession:
        """Get the session summary. Must be completed."""
        return self._get_session(session_id)

    def _get_session(self, session_id: str) -> InterviewSession:
        session = self._load_session(session_id)
        if session is None:
            raise AppError(
                code=ErrorCode.SESSION_NOT_FOUND,
                message=f"Interview session not found: {session_id}",
            )
        return session

    def _complete_session(self, session: InterviewSession) -> None:
        """Calculate overall score and generate final feedback."""
        answered = [q for q in session.questions if q.answered]
        if answered:
            session.overall_score = sum(q.score for q in answered) / len(answered)

        session.overall_feedback = (
            f"You answered {len(answered)} out of {len(session.questions)} questions. "
            f"Average score: {session.overall_score:.1f}/10."
        )
        session.completed = True

        logger.info(
            "interview_session_completed",
            session_id=session.id,
            score=session.overall_score,
        )

    def _parse_questions(self, response: str, expected_count: int) -> list[str]:
        """Parse question list from LLM response."""
        try:
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                questions = json.loads(response[start:end])
                if isinstance(questions, list):
                    return [str(q) for q in questions[:expected_count]]
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback: split numbered lines
        parsed: list[str] = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith(("-", "*", "•"))):
                q = line.lstrip("0123456789.-*•) ").strip()
                if q and q.endswith("?"):
                    parsed.append(q)
        return parsed[:expected_count] if parsed else [f"Question about {response[:50]}?"]

    def _parse_evaluation(self, question: InterviewQuestion, response: str) -> None:
        """Parse evaluation from LLM response."""
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                question.score = float(data.get("score", 5))
                question.feedback = data.get("feedback", response)
                question.model_answer = data.get("model_answer", "")
                return
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

        # Fallback
        question.score = 5.0
        question.feedback = response
        question.model_answer = ""
