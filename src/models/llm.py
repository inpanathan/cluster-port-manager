"""LLM client wrapper with mock and Claude API backends."""

from __future__ import annotations

from typing import Protocol

from src.utils.errors import AppError, ErrorCode
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient(Protocol):
    """Protocol for LLM clients."""

    def generate(self, prompt: str, *, system: str = "", max_tokens: int = 1024) -> str: ...


class MockLLMClient:
    """Deterministic mock LLM for testing.

    Returns structured responses based on the prompt content.
    """

    def __init__(self) -> None:
        logger.info("mock_llm_loaded")

    def generate(self, prompt: str, *, system: str = "", max_tokens: int = 1024) -> str:
        """Generate a mock response based on prompt keywords."""
        prompt_lower = prompt.lower()

        if "summary" in prompt_lower or "summarize" in prompt_lower:
            return (
                "This document covers several key topics. "
                "The main points include the core concepts discussed, "
                "practical applications, and important considerations. "
                "The content provides a comprehensive overview of the subject matter."
            )

        if "interview" in prompt_lower or "question" in prompt_lower:
            return (
                "1. Can you explain the fundamental concepts discussed in the material?\n"
                "2. How would you apply these concepts in a real-world scenario?\n"
                "3. What are the key trade-offs to consider?\n"
                "4. Describe a situation where you had to make a difficult technical decision.\n"
                "5. How do you stay current with developments in this area?"
            )

        if "evaluate" in prompt_lower or "feedback" in prompt_lower:
            return (
                "Your answer demonstrates a good understanding of the core concepts. "
                "Strengths: You correctly identified the key principles. "
                "Areas for improvement: Consider providing more specific examples. "
                "Suggested answer: A comprehensive response would include concrete examples "
                "and discuss trade-offs."
            )

        if "q&a" in prompt_lower or "question and answer" in prompt_lower:
            return (
                "Q: What are the main concepts covered?\n"
                "A: The main concepts include core principles, practical applications, "
                "and best practices for implementation.\n\n"
                "Q: How can these concepts be applied?\n"
                "A: These concepts can be applied through systematic implementation, "
                "following established patterns and guidelines."
            )

        # Default: answer based on context
        return (
            "Based on the provided context, here is what I found: "
            "The information relates to the topics in the indexed content. "
            "This answer is grounded in the available sources."
        )


class ClaudeLLMClient:
    """Claude API client via the Anthropic SDK."""

    def __init__(
        self,
        api_key: str,
        model_id: str = "claude-sonnet-4-20250514",
        temperature: float = 0.3,
        timeout: int = 60,
    ) -> None:
        try:
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
            self._model_id = model_id
            self._temperature = temperature
            logger.info("claude_llm_loaded", model=model_id)
        except ImportError as e:
            raise AppError(
                code=ErrorCode.MODEL_LOAD_FAILED,
                message="anthropic SDK not installed",
                cause=e,
            ) from e

    def generate(self, prompt: str, *, system: str = "", max_tokens: int = 1024) -> str:
        """Generate a response using the Claude API."""
        try:
            import anthropic

            kwargs: dict = {
                "model": self._model_id,
                "max_tokens": max_tokens,
                "temperature": self._temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system

            response = self._client.messages.create(**kwargs)
            text = response.content[0].text
            logger.info(
                "llm_response_generated",
                model=self._model_id,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            return text
        except anthropic.APITimeoutError as e:
            raise AppError(
                code=ErrorCode.LLM_TIMEOUT,
                message="Claude API request timed out",
                cause=e,
            ) from e
        except Exception as e:
            raise AppError(
                code=ErrorCode.LLM_GENERATION_FAILED,
                message=f"LLM generation failed: {e}",
                cause=e,
            ) from e


def create_llm_client(
    backend: str,
    api_key: str = "",
    model_id: str = "claude-sonnet-4-20250514",
    temperature: float = 0.3,
    timeout: int = 60,
) -> LLMClient:
    """Factory to create the appropriate LLM client."""
    if backend == "mock":
        return MockLLMClient()
    return ClaudeLLMClient(
        api_key=api_key,
        model_id=model_id,
        temperature=temperature,
        timeout=timeout,
    )
