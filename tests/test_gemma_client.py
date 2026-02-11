"""Tests for the Gemma API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.gemma_client import GemmaClient
from src.config.settings import AppSettings, GemmaSettings


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(
        google_api_key="fake-key",
        gemma=GemmaSettings(model="gemma-2-2b-it"),
    )


@patch("src.api.gemma_client.genai")
def test_client_init(mock_genai: MagicMock, settings: AppSettings) -> None:
    """Client should configure genai with the API key."""
    GemmaClient(settings)
    mock_genai.configure.assert_called_once_with(api_key="fake-key")


@patch("src.api.gemma_client.genai")
@pytest.mark.asyncio
async def test_generate(mock_genai: MagicMock, settings: AppSettings) -> None:
    """generate() should return the model's text response."""
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Hello from Gemma!"
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    mock_genai.GenerativeModel.return_value = mock_model

    client = GemmaClient(settings)
    result = await client.generate("Hi")
    assert result == "Hello from Gemma!"
    mock_model.generate_content_async.assert_awaited_once_with("Hi")


@patch("src.api.gemma_client.genai")
@pytest.mark.asyncio
async def test_generate_error(mock_genai: MagicMock, settings: AppSettings) -> None:
    """generate() should propagate exceptions."""
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(side_effect=RuntimeError("API down"))
    mock_genai.GenerativeModel.return_value = mock_model

    client = GemmaClient(settings)
    with pytest.raises(RuntimeError, match="API down"):
        await client.generate("Hi")
