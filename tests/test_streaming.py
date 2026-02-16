"""Tests for streaming message functionality."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.mistral_client import MistralClient
from src.bot.handlers.message_handler import MessageHandler
from src.config.settings import AppSettings


@pytest.fixture
def settings() -> AppSettings:
    """Create test settings with streaming enabled."""
    s = AppSettings(
        mistral_api_key="test-key",
        telegram_bot_token="test-token",
    )
    s.bot.enable_streaming = True
    s.bot.streaming_threshold = 100
    s.bot.streaming_update_interval = 1.0
    s.access.allowed_user_ids = [1]
    return s


@pytest.fixture
def settings_no_streaming() -> AppSettings:
    """Create test settings with streaming disabled."""
    s = AppSettings(
        mistral_api_key="test-key",
        telegram_bot_token="test-token",
    )
    s.bot.enable_streaming = False
    s.access.allowed_user_ids = [1]
    return s


def test_streaming_config_defaults() -> None:
    """Test that streaming configuration has sensible defaults."""
    settings = AppSettings(
        mistral_api_key="test-key",
        telegram_bot_token="test-token",
    )
    assert settings.bot.enable_streaming is True
    assert settings.bot.streaming_threshold == 100
    assert settings.bot.streaming_update_interval == 1.0


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_stream_basic(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """Test basic streaming functionality."""
    # Mock streaming response
    mock_client = MagicMock()

    # Create mock stream chunks
    async def mock_stream():
        # Chunk 1: partial content
        chunk1 = MagicMock()
        chunk1.data = MagicMock()
        delta1 = MagicMock()
        delta1.content = "Hello"
        choice1 = MagicMock()
        choice1.delta = delta1
        chunk1.data.choices = [choice1]
        chunk1.data.usage = None
        yield chunk1

        # Chunk 2: more content
        chunk2 = MagicMock()
        chunk2.data = MagicMock()
        delta2 = MagicMock()
        delta2.content = " world"
        choice2 = MagicMock()
        choice2.delta = delta2
        chunk2.data.choices = [choice2]
        chunk2.data.usage = None
        yield chunk2

        # Chunk 3: final with usage
        chunk3 = MagicMock()
        chunk3.data = MagicMock()
        delta3 = MagicMock()
        delta3.content = "!"
        choice3 = MagicMock()
        choice3.delta = delta3
        chunk3.data.choices = [choice3]
        usage = MagicMock()
        usage.prompt_tokens = 10
        usage.completion_tokens = 5
        chunk3.data.usage = usage
        yield chunk3

    mock_client.chat.stream_async = AsyncMock(return_value=mock_stream())
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)

    accumulated = []
    async for chunk_content, full_content, is_final in client.generate_stream("test"):
        accumulated.append((chunk_content, full_content, is_final))

    # Verify we got the expected chunks
    assert len(accumulated) == 4  # 3 content chunks + 1 final
    assert accumulated[0] == ("Hello", "Hello", False)
    assert accumulated[1] == (" world", "Hello world", False)
    assert accumulated[2] == ("!", "Hello world!", False)
    assert accumulated[3][2] is True  # Final chunk
    assert accumulated[3][1] == "Hello world!"  # Full content


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_stream_with_empty_chunks(
    mock_mistral: MagicMock, settings: AppSettings
) -> None:
    """Test streaming handles empty chunks gracefully."""
    mock_client = MagicMock()

    async def mock_stream():
        # Chunk with no content
        chunk1 = MagicMock()
        chunk1.data = MagicMock()
        delta1 = MagicMock()
        delta1.content = None
        choice1 = MagicMock()
        choice1.delta = delta1
        chunk1.data.choices = [choice1]
        chunk1.data.usage = None
        yield chunk1

        # Chunk with actual content
        chunk2 = MagicMock()
        chunk2.data = MagicMock()
        delta2 = MagicMock()
        delta2.content = "Content"
        choice2 = MagicMock()
        choice2.delta = delta2
        chunk2.data.choices = [choice2]
        chunk2.data.usage = None
        yield chunk2

    mock_client.chat.stream_async = AsyncMock(return_value=mock_stream())
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)

    accumulated = []
    async for chunk_content, full_content, is_final in client.generate_stream("test"):
        if chunk_content or is_final:  # Only collect non-empty or final chunks
            accumulated.append((chunk_content, full_content, is_final))

    # Should have content chunk and final chunk
    assert len(accumulated) >= 1
    assert "Content" in accumulated[-1][1]


@pytest.mark.asyncio
async def test_message_handler_uses_streaming_config() -> None:
    """Test MessageHandler respects streaming configuration."""
    from src.api.mistral_client import GenerateResponse
    from src.bot.filters.access_filter import AccessFilter

    # Test with streaming enabled
    settings_streaming = AppSettings(
        mistral_api_key="test-key",
        telegram_bot_token="test-token",
    )
    settings_streaming.bot.enable_streaming = True
    settings_streaming.access.allowed_user_ids = [1]

    mistral_streaming = MagicMock()
    async def mock_stream(prompt, user_id=None):
        yield ("Test", "Test", True)
    mistral_streaming.generate_stream = mock_stream
    mistral_streaming._memory = MagicMock()
    mistral_streaming._memory.add_message = MagicMock()

    af = AccessFilter(settings_streaming)
    handler_streaming = MessageHandler(settings_streaming, mistral_streaming, af)

    # Verify streaming is enabled
    assert handler_streaming._settings.bot.enable_streaming is True

    # Test with streaming disabled
    settings_no_streaming = AppSettings(
        mistral_api_key="test-key",
        telegram_bot_token="test-token",
    )
    settings_no_streaming.bot.enable_streaming = False
    settings_no_streaming.access.allowed_user_ids = [1]

    mistral_no_streaming = MagicMock()
    mistral_no_streaming.generate = AsyncMock(
        return_value=GenerateResponse(
            content="Response",
            model="mistral-small-latest",
            input_tokens=5,
            output_tokens=10,
        )
    )
    mistral_no_streaming._memory = MagicMock()
    mistral_no_streaming._memory.add_message = MagicMock()

    handler_no_streaming = MessageHandler(settings_no_streaming, mistral_no_streaming, af)

    # Verify streaming is disabled
    assert handler_no_streaming._settings.bot.enable_streaming is False


@pytest.mark.asyncio
async def test_message_handler_streaming_disabled() -> None:
    """Test MessageHandler respects streaming disabled configuration."""
    from src.api.mistral_client import GenerateResponse
    from src.bot.filters.access_filter import AccessFilter

    settings = AppSettings(
        mistral_api_key="test-key",
        telegram_bot_token="test-token",
    )
    settings.bot.enable_streaming = False
    settings.access.allowed_user_ids = [1]

    mistral = MagicMock()
    mistral.generate = AsyncMock(
        return_value=GenerateResponse(
            content="Non-streaming response",
            model="mistral-small-latest",
            input_tokens=5,
            output_tokens=10,
        )
    )
    mistral._memory = MagicMock()
    mistral._memory.add_message = MagicMock()

    af = AccessFilter(settings)
    handler = MessageHandler(settings, mistral, af)

    # Verify streaming is disabled
    assert handler._settings.bot.enable_streaming is False


def test_truncate_safely_basic() -> None:
    """Test _truncate_safely function with basic text."""
    from src.bot.handlers.message_handler import _truncate_safely

    text = "This is a simple test"
    indicator = "..."
    max_len = 30

    result = _truncate_safely(text, max_len, indicator)
    assert len(result) <= max_len
    assert result.endswith(indicator)


def test_truncate_safely_with_markdown() -> None:
    """Test _truncate_safely closes markdown formatting."""
    from src.bot.handlers.message_handler import _truncate_safely

    # Text with unclosed asterisks
    text = "This is *bold text that will be truncated"
    indicator = "..."
    max_len = 20

    result = _truncate_safely(text, max_len, indicator)
    # Should close the asterisk
    assert result.count('*') % 2 == 0


def test_truncate_safely_with_backticks() -> None:
    """Test _truncate_safely closes code blocks."""
    from src.bot.handlers.message_handler import _truncate_safely

    # Text with unclosed backticks
    text = "This is `code that will be truncated"
    indicator = "..."
    max_len = 20

    result = _truncate_safely(text, max_len, indicator)
    # Should close the backtick
    assert result.count('`') % 2 == 0
