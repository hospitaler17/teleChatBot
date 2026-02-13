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
    assert len(kwargs["messages"]) == 1
    # Ensure generation settings are passed through
    assert kwargs["max_tokens"] == settings.mistral.max_tokens
    assert kwargs["temperature"] == settings.mistral.temperature


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
