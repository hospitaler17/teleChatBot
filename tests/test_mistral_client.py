"""Tests for the Mistral API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.mistral_client import MistralClient
from src.config.settings import AppSettings, MistralSettings


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(
        mistral_api_key="fake-key",
        mistral=MistralSettings(model="mistral-small-latest"),
    )


@patch("src.api.mistral_client.Mistral")
def test_client_init(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """Client should initialize Mistral with the API key."""
    MistralClient(settings)
    mock_mistral.assert_called_once_with(api_key="fake-key")


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should return the model's text response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Hello from Mistral!"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    result = await client.generate("Hi")
    assert result == "Hello from Mistral!"

    # Verify that complete_async was called with the expected arguments
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    assert kwargs["model"] == settings.mistral.model
    # Ensure the user message content is correctly forwarded
    assert isinstance(kwargs["messages"], list)
    # Should have SystemMessage (with date/time) + UserMessage
    assert len(kwargs["messages"]) >= 2, "Should have system message and user message"
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
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    result = await client.generate("Hi")
    assert result == "I'm here to help!"

    # Verify messages include both system and user
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    assert len(messages) == 2
    # First message should be system
    assert messages[0].role == "system"
    # System message should contain the prompt and also date/time info
    assert "You are a helpful assistant." in messages[0].content
    assert "дата" in messages[0].content.lower() or "время" in messages[0].content.lower()
    # Second message should be user
    assert messages[1].role == "user"
    assert messages[1].content == "Hi"
    # Second message should be user
    assert messages[1].role == "user"
    assert messages[1].content == "Hi"


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
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    with pytest.raises(TypeError, match="non-string"):
        await client.generate("Hi")
