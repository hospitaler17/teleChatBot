"""Tests for rate limiting and RetryAfter exception handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import RetryAfter

from src.bot.handlers.message_handler import _safe_edit_message, _safe_send_message


@pytest.mark.asyncio
async def test_safe_edit_message_success() -> None:
    """Test that _safe_edit_message successfully edits a message."""
    message = MagicMock()
    message.edit_text = AsyncMock()

    result = await _safe_edit_message(message, "test text")

    assert result is True
    message.edit_text.assert_awaited_once_with("test text", parse_mode="Markdown")


@pytest.mark.asyncio
async def test_safe_edit_message_retry_after() -> None:
    """Test that _safe_edit_message handles RetryAfter exception and retries."""
    message = MagicMock()

    # First call raises RetryAfter, second call succeeds
    retry_error = RetryAfter(1)
    message.edit_text = AsyncMock(side_effect=[retry_error, None])

    with patch(
        "src.bot.handlers.message_handler.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        result = await _safe_edit_message(message, "test text", max_retries=3)

    assert result is True
    assert message.edit_text.await_count == 2
    # Should sleep for retry_after + 0.5 seconds
    mock_sleep.assert_awaited_once_with(1.5)


@pytest.mark.asyncio
async def test_safe_edit_message_retry_after_max_retries() -> None:
    """Test that _safe_edit_message fails after max retries."""
    message = MagicMock()

    # Always raises RetryAfter
    retry_error = RetryAfter(1)
    message.edit_text = AsyncMock(side_effect=retry_error)

    with patch(
        "src.bot.handlers.message_handler.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        result = await _safe_edit_message(message, "test text", max_retries=3)

    assert result is False
    assert message.edit_text.await_count == 3
    # Should sleep twice (attempts 1 and 2, but not attempt 3)
    assert mock_sleep.await_count == 2


@pytest.mark.asyncio
async def test_safe_send_message_success() -> None:
    """Test that _safe_send_message successfully sends a message."""
    message = MagicMock()
    sent_message = MagicMock()
    message.reply_text = AsyncMock(return_value=sent_message)

    result = await _safe_send_message(message, "test text")

    assert result == sent_message
    message.reply_text.assert_awaited_once_with("test text", parse_mode="Markdown")


@pytest.mark.asyncio
async def test_safe_send_message_retry_after() -> None:
    """Test that _safe_send_message handles RetryAfter exception and retries."""
    message = MagicMock()
    sent_message = MagicMock()

    # First call raises RetryAfter, second call succeeds
    retry_error = RetryAfter(1)
    message.reply_text = AsyncMock(side_effect=[retry_error, sent_message])

    with patch(
        "src.bot.handlers.message_handler.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        result = await _safe_send_message(message, "test text", max_retries=3)

    assert result == sent_message
    assert message.reply_text.await_count == 2
    # Should sleep for retry_after + 0.5 seconds
    mock_sleep.assert_awaited_once_with(1.5)


@pytest.mark.asyncio
async def test_safe_send_message_retry_after_max_retries() -> None:
    """Test that _safe_send_message fails after max retries."""
    message = MagicMock()

    # Always raises RetryAfter
    retry_error = RetryAfter(2)
    message.reply_text = AsyncMock(side_effect=retry_error)

    with patch(
        "src.bot.handlers.message_handler.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        result = await _safe_send_message(message, "test text", max_retries=3)

    assert result is None
    assert message.reply_text.await_count == 3
    # Should sleep twice (attempts 1 and 2, but not attempt 3)
    assert mock_sleep.await_count == 2


@pytest.mark.asyncio
async def test_safe_edit_message_handles_message_not_modified() -> None:
    """Test that _safe_edit_message handles 'message is not modified' error."""
    from telegram.error import BadRequest

    message = MagicMock()
    bad_request = BadRequest("Message is not modified")
    message.edit_text = AsyncMock(side_effect=bad_request)

    result = await _safe_edit_message(message, "test text")

    # Should return True because message not modified is not a real error
    assert result is True
    message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_safe_edit_message_handles_parse_error() -> None:
    """Test that _safe_edit_message handles markdown parse errors."""
    from telegram.error import BadRequest

    message = MagicMock()
    parse_error = BadRequest("Can't parse entities")
    # First call with Markdown fails, second call without parse_mode succeeds
    message.edit_text = AsyncMock(side_effect=[parse_error, None])

    result = await _safe_edit_message(message, "test text")

    assert result is True
    assert message.edit_text.await_count == 2
    # First call with Markdown, second call without parse_mode
    message.edit_text.assert_any_await("test text", parse_mode="Markdown")
    message.edit_text.assert_any_await("test text", parse_mode=None)


@pytest.mark.asyncio
async def test_safe_send_message_handles_parse_error() -> None:
    """Test that _safe_send_message handles markdown parse errors."""
    from telegram.error import BadRequest

    message = MagicMock()
    sent_message = MagicMock()
    parse_error = BadRequest("Can't parse entities")
    # First call with Markdown fails, second call without parse_mode succeeds
    message.reply_text = AsyncMock(side_effect=[parse_error, sent_message])

    result = await _safe_send_message(message, "test text")

    assert result == sent_message
    assert message.reply_text.await_count == 2
    # First call with Markdown, second call without parse_mode
    message.reply_text.assert_any_await("test text", parse_mode="Markdown")
    message.reply_text.assert_any_await("test text", parse_mode=None)
