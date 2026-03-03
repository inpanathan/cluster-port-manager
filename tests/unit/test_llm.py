"""Unit tests for LLM client factory and implementations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.models.llm import (
    ClaudeLLMClient,
    MockLLMClient,
    VLLMLLMClient,
    create_llm_client,
)


def test_factory_returns_mock_client() -> None:
    """create_llm_client('mock') returns MockLLMClient."""
    client = create_llm_client("mock")
    assert isinstance(client, MockLLMClient)


def test_factory_returns_vllm_client_for_local() -> None:
    """create_llm_client('local') returns VLLMLLMClient."""
    client = create_llm_client(
        "local",
        vllm_base_url="http://localhost:8001/v1",
        vllm_model="test-model",
    )
    assert isinstance(client, VLLMLLMClient)


def test_factory_returns_claude_client_for_cloud() -> None:
    """create_llm_client('cloud') returns ClaudeLLMClient."""
    with patch("anthropic.Anthropic"):
        client = create_llm_client("cloud", api_key="test-key")
    assert isinstance(client, ClaudeLLMClient)


def test_mock_client_generate_returns_string() -> None:
    """MockLLMClient.generate returns a non-empty string."""
    client = MockLLMClient()
    result = client.generate("Tell me about Python")
    assert isinstance(result, str)
    assert len(result) > 0


def test_vllm_client_generate_calls_openai_api() -> None:
    """VLLMLLMClient.generate calls OpenAI chat completions."""
    client = create_llm_client(
        "local",
        vllm_base_url="http://localhost:8001/v1",
        vllm_model="test-model",
    )

    # Mock the OpenAI client's response
    mock_choice = MagicMock()
    mock_choice.message.content = "test response"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5

    client._client.chat.completions.create = MagicMock(return_value=mock_response)

    result = client.generate("test prompt", system="test system", max_tokens=512)
    assert result == "test response"

    call_kwargs = client._client.chat.completions.create.call_args
    messages = call_kwargs.kwargs["messages"]
    assert messages[0] == {"role": "system", "content": "test system"}
    assert messages[1] == {"role": "user", "content": "test prompt"}
    assert call_kwargs.kwargs["max_tokens"] == 512
