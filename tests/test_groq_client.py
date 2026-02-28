"""Tests for the Groq API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.groq_client import GroqClient, _map_model
from src.api.mistral_client import GenerateResponse
from src.config.settings import AppSettings, GroqSettings, MistralSettings


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(
        mistral_api_key="fake-mistral-key",
        groq_api_key="fake-groq-key",
        mistral=MistralSettings(model="mistral-small-latest"),
        groq=GroqSettings(enabled=True),
    )


# ------------------------------------------------------------------
# Model mapping
# ------------------------------------------------------------------


def test_map_model_default(settings: AppSettings) -> None:
    """Default Mistral model should map to the configured Groq model."""
    result = _map_model("mistral-small-latest", settings)
    assert result == settings.groq.model


def test_map_model_code(settings: AppSettings) -> None:
    """Code model should map to Groq code_model."""
    result = _map_model("codestral-latest", settings)
    assert result == settings.groq.code_model


def test_map_model_large(settings: AppSettings) -> None:
    """Large / medium models should map to Groq large_model."""
    assert _map_model("mistral-large-latest", settings) == settings.groq.large_model
    assert _map_model("mistral-medium-latest", settings) == settings.groq.large_model


def test_map_model_unknown(settings: AppSettings) -> None:
    """Unknown model names should fall back to the default Groq model."""
    result = _map_model("some-unknown-model", settings)
    assert result == settings.groq.model


# ------------------------------------------------------------------
# Client initialisation
# ------------------------------------------------------------------


@patch("src.api.groq_client.AsyncGroq")
def test_client_init(mock_groq: MagicMock, settings: AppSettings) -> None:
    """GroqClient should initialise AsyncGroq with the API key."""
    GroqClient(settings)
    mock_groq.assert_called_once_with(api_key="fake-groq-key")


# ------------------------------------------------------------------
# generate()
# ------------------------------------------------------------------


@patch("src.api.groq_client.AsyncGroq")
@pytest.mark.asyncio
async def test_generate(mock_groq: MagicMock, settings: AppSettings) -> None:
    """generate() should return GenerateResponse with Groq output."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Hello from Groq!"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 5
    mock_usage.completion_tokens = 10
    mock_response.usage = mock_usage
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_groq.return_value = mock_client

    client = GroqClient(settings)
    result = await client.generate("Hi")

    assert isinstance(result, GenerateResponse)
    assert result.content == "Hello from Groq!"
    assert result.input_tokens == 5
    assert result.output_tokens == 10
    assert result.total_tokens == 15


@patch("src.api.groq_client.AsyncGroq")
@pytest.mark.asyncio
async def test_generate_no_choices(mock_groq: MagicMock, settings: AppSettings) -> None:
    """generate() should raise ValueError when API returns no choices."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = []
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_groq.return_value = mock_client

    client = GroqClient(settings)
    with pytest.raises(ValueError, match="no choices"):
        await client.generate("Hi")


@patch("src.api.groq_client.AsyncGroq")
@pytest.mark.asyncio
async def test_generate_with_selected_model(
    mock_groq: MagicMock, settings: AppSettings
) -> None:
    """generate() should use _selected_model override when provided."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "code answer"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_response.usage = None
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_groq.return_value = mock_client

    client = GroqClient(settings)
    result = await client.generate("code", _selected_model="codestral-latest")

    assert result.content == "code answer"
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == settings.groq.code_model
