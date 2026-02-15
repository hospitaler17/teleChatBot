"""Tests for the Mistral API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.mistral_client import MistralClient, GenerateResponse
from src.api.model_selector import requires_current_date
from src.config.settings import AppSettings, MistralSettings


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(
        mistral_api_key="fake-key",
        mistral=MistralSettings(model="mistral-small-latest"),
    )


def test_requires_current_date_with_date_keywords() -> None:
    """requires_current_date() should return True for queries about current date."""
    assert requires_current_date("What happened today?")
    assert requires_current_date("Какие новости сегодня?")
    assert requires_current_date("Какая будет погода завтра?")
    assert requires_current_date("What's the current exchange rate?")
    assert requires_current_date("Покажи последние новости")


def test_requires_current_date_without_date_keywords() -> None:
    """requires_current_date() should return False for queries that don't need current date."""
    assert not requires_current_date("What is Python?")
    assert not requires_current_date("Напиши функцию")
    assert not requires_current_date("Как работает интернет?")
    assert not requires_current_date("Write a poem about love")


@patch("src.api.mistral_client.Mistral")
def test_client_init(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """Client should initialize Mistral with the API key."""
    MistralClient(settings)
    mock_mistral.assert_called_once_with(api_key="fake-key")


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should return GenerateResponse with model text and metadata."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Hello from Mistral!"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    # Mock usage information
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 15
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    result = await client.generate("Hi")
    
    # Check result is GenerateResponse
    assert isinstance(result, GenerateResponse)
    assert result.content == "Hello from Mistral!"
    assert result.input_tokens == 10
    assert result.output_tokens == 15
    assert result.total_tokens == 25

    # Verify that complete_async was called with the expected arguments
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    # Model should be dynamically selected (mistral-small-latest for simple query)
    assert kwargs["model"] == "mistral-small-latest"
    # Ensure the user message content is correctly forwarded
    assert isinstance(kwargs["messages"], list)
    # Should have at least UserMessage (no system prompt configured, no date needed)
    assert len(kwargs["messages"]) >= 1, "Should have at least user message"
    # Last message should be the user message
    assert kwargs["messages"][-1].role == "user"
    assert kwargs["messages"][-1].content == "Hi"
    # Ensure generation settings are passed through
    assert kwargs["max_tokens"] == settings.mistral.max_tokens
    assert kwargs["temperature"] == settings.mistral.temperature


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_with_system_prompt(mock_mistral: MagicMock) -> None:
    """generate() should include system message when system_prompt is configured."""
    settings = AppSettings(
        mistral_api_key="fake-key",
        mistral=MistralSettings(
            model="mistral-small-latest", system_prompt="You are a helpful assistant."
        ),
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "I'm here to help!"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 5
    mock_usage.completion_tokens = 8
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    result = await client.generate("Hi")
    assert isinstance(result, GenerateResponse)
    assert result.content == "I'm here to help!"

    # Verify messages include both system and user
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    assert len(messages) == 2
    # First message should be system
    assert messages[0].role == "system"
    # System message should contain only the configured prompt
    assert "You are a helpful assistant." in messages[0].content
    # Second message should be user
    assert messages[1].role == "user"
    assert messages[1].content == "Hi"


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_with_date_context(mock_mistral: MagicMock) -> None:
    """generate() should add current date to system prompt for time-sensitive queries."""
    settings = AppSettings(
        mistral_api_key="fake-key",
        mistral=MistralSettings(model="mistral-small-latest"),
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Today is a great day!"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 12
    mock_usage.completion_tokens = 6
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    # Query that requires date context (contains "today")
    result = await client.generate("What happened today?", user_id=123)
    assert isinstance(result, GenerateResponse)
    assert result.content == "Today is a great day!"

    # Verify that date was added to system prompt
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    # First message should be system message with date
    assert messages[0].role == "system"
    # Check for date/instruction in English (more explicit)
    assert "CURRENT YEAR" in messages[0].content or "CRITICAL CONTEXT" in messages[0].content

    # Also verify that date context was added to conversation memory
    history = client._memory.get_history(123)
    # Should have system context with date
    system_messages = [msg for msg in history if msg["role"] == "system"]
    assert len(system_messages) > 0
    assert "Current date:" in system_messages[0]["content"]


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_without_date_context(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should NOT add date for queries that don't need current date."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Python is great!"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 8
    mock_usage.completion_tokens = 4
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    # Query that does NOT require date (simple question)
    result = await client.generate("What is Python?")
    assert isinstance(result, GenerateResponse)
    assert result.content == "Python is great!"

    # Verify that date was NOT added to system prompt
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    # System message should not contain date
    if len(messages) > 0 and messages[0].role == "system":
        assert "CURRENT YEAR" not in messages[0].content
        assert "CRITICAL CONTEXT" not in messages[0].content


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_code_request(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should select code model for code-related queries."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "def hello(): print('hi')"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 15
    mock_usage.completion_tokens = 10
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    result = await client.generate("Write a Python function to sort a list")
    assert isinstance(result, GenerateResponse)
    assert result.content == "def hello(): print('hi')"

    # Verify that codestral model was selected
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    assert kwargs["model"] == "codestral-latest"


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_complex_request(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should select large model for complex reasoning queries."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Detailed analysis..."
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 20
    mock_usage.completion_tokens = 30
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    result = await client.generate("Analyze step by step why this approach works")
    assert isinstance(result, GenerateResponse)
    assert result.content == "Detailed analysis..."

    # Verify that large model was selected
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    assert kwargs["model"] == "mistral-large-latest"


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_error(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should propagate exceptions."""
    mock_client = MagicMock()
    mock_client.chat.complete_async = AsyncMock(side_effect=RuntimeError("API down"))
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    with pytest.raises(RuntimeError, match="API down"):
        await client.generate("Hi")


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_empty_choices(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should raise ValueError if API returns no choices."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = []
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    with pytest.raises(ValueError, match="no choices"):
        await client.generate("Hi")


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_missing_content(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should raise ValueError if API returns no message content."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = None
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 5
    mock_usage.completion_tokens = 0
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    with pytest.raises(ValueError, match="no message content"):
        await client.generate("Hi")


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_non_string_content(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should raise TypeError if API returns non-string content."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = 123  # Non-string content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 5
    mock_usage.completion_tokens = 0
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    with pytest.raises(TypeError, match="non-string"):
        await client.generate("Hi")
