"""Tests for the Mistral API client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
    mock_client.chat.complete.return_value = mock_response
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    result = await client.generate("Hi")
    assert result == "Hello from Mistral!"
    mock_client.chat.complete.assert_called_once()


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_error(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should propagate exceptions."""
    mock_client = MagicMock()
    mock_client.chat.complete.side_effect = RuntimeError("API down")
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    with pytest.raises(RuntimeError, match="API down"):
        await client.generate("Hi")
