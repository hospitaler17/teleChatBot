"""Tests for message and command handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handlers.admin_handler import AdminHandler
from src.bot.handlers.command_handler import CommandHandler
from src.bot.handlers.message_handler import (
    MessageHandler,
    _send_typing_periodically,
    _split_text,
)
from src.config.settings import AccessSettings, AdminSettings, AppSettings, BotSettings

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _settings(
    admin_ids: list[int] | None = None,
    allowed_users: list[int] | None = None,
) -> AppSettings:
    return AppSettings(
        telegram_bot_token="fake",
        mistral_api_key="fake",
        admin=AdminSettings(user_ids=admin_ids or []),
        access=AccessSettings(allowed_user_ids=allowed_users or []),
        bot=BotSettings(username="testbot"),
    )


def _update(user_id: int = 1, text: str = "hello", chat_type: str = "private") -> MagicMock:
    update = MagicMock()
    update.message.from_user.id = user_id
    update.message.chat.type = chat_type
    update.message.chat.id = user_id
    update.message.text = text
    update.message.photo = None
    update.message.reply_to_message = None
    update.message.entities = None
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    return update


# ------------------------------------------------------------------
# _split_text
# ------------------------------------------------------------------


def test_split_text_short() -> None:
    assert _split_text("hello", 100) == ["hello"]


def test_split_text_long() -> None:
    chunks = _split_text("abcdef", 2)
    assert chunks == ["ab", "cd", "ef"]


# ------------------------------------------------------------------
# CommandHandler
# ------------------------------------------------------------------


class TestCommandHandler:
    @pytest.mark.asyncio
    async def test_start_allowed(self) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(allowed_users=[1])
        af = AccessFilter(s)
        handler = CommandHandler(af, "testbot")
        update = _update(user_id=1)
        ctx = MagicMock()
        await handler.start(update, ctx)
        update.message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_help_disallowed(self) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(allowed_users=[1])
        af = AccessFilter(s)
        handler = CommandHandler(af, "testbot")
        update = _update(user_id=99)
        ctx = MagicMock()
        await handler.help(update, ctx)
        update.message.reply_text.assert_not_awaited()


# ------------------------------------------------------------------
# MessageHandler
# ------------------------------------------------------------------


class TestMessageHandler:
    @pytest.mark.asyncio
    async def test_handle_allowed(self) -> None:
        from src.api.mistral_client import GenerateResponse
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(allowed_users=[1])
        # Disable streaming for this test to verify non-streaming path still works
        s.bot.enable_streaming = False

        mistral = MagicMock()
        mistral.generate = AsyncMock(
            return_value=GenerateResponse(
                content="response text",
                model="mistral-small-latest",
                input_tokens=5,
                output_tokens=10,
            )
        )
        mistral._web_search = None
        mistral._should_use_web_search = MagicMock(return_value=False)
        af = AccessFilter(s)
        handler = MessageHandler(s, mistral, af)

        update = _update(user_id=1, text="ping")
        # Make reply_text return a mock message so status edit works
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=status_msg)
        ctx = MagicMock()
        ctx.bot.send_chat_action = AsyncMock()
        await handler.handle(update, ctx)
        # First call sends status, second is not needed since edit replaces it
        calls = update.message.reply_text.call_args_list
        assert calls[0][0][0] == s.status_messages.thinking
        # The response is edited into the status message
        status_msg.edit_text.assert_awaited_once_with(
            "response text", parse_mode="Markdown"
        )

    @pytest.mark.asyncio
    async def test_handle_disallowed(self) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(allowed_users=[1])
        mistral = MagicMock()
        af = AccessFilter(s)
        handler = MessageHandler(s, mistral, af)

        update = _update(user_id=99)
        ctx = MagicMock()
        await handler.handle(update, ctx)
        update.message.reply_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_photo_message(self) -> None:
        """Should pass image_urls to generate when photo is attached."""
        from src.api.mistral_client import GenerateResponse
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(allowed_users=[1])
        s.bot.enable_streaming = False

        mistral = MagicMock()
        mistral.generate = AsyncMock(
            return_value=GenerateResponse(
                content="I see a cat",
                model="pixtral-12b-latest",
                input_tokens=50,
                output_tokens=10,
            )
        )
        mistral._web_search = None
        mistral._should_use_web_search = MagicMock(return_value=False)
        af = AccessFilter(s)
        handler = MessageHandler(s, mistral, af)

        # Create update with photo
        update = _update(user_id=1, text="")
        update.message.text = None
        update.message.caption = "What is this?"
        # Simulate photo: list of PhotoSize objects
        mock_photo = MagicMock()
        mock_photo.file_id = "fake_file_id"
        update.message.photo = [mock_photo]
        update.message.video = None
        update.message.audio = None
        update.message.voice = None
        update.message.document = None
        update.message.sticker = None
        update.message.animation = None
        update.message.location = None
        update.message.contact = None
        update.message.invoice = None

        # Mock file download
        mock_file = AsyncMock()
        mock_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"\xff\xd8test"))

        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=status_msg)

        ctx = MagicMock()
        ctx.bot.send_chat_action = AsyncMock()
        ctx.bot.get_file = AsyncMock(return_value=mock_file)

        await handler.handle(update, ctx)

        # Verify generate was called with image_urls
        mistral.generate.assert_awaited_once()
        call_kwargs = mistral.generate.call_args
        assert call_kwargs.kwargs.get("image_urls") is not None
        assert len(call_kwargs.kwargs["image_urls"]) == 1
        assert call_kwargs.kwargs["image_urls"][0].startswith("data:image/jpeg;base64,")


# ------------------------------------------------------------------
# AdminHandler
# ------------------------------------------------------------------


class TestAdminHandler:
    @pytest.mark.asyncio
    async def test_add_user_as_admin(self, tmp_path) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(admin_ids=[1])
        af = AccessFilter(s)
        handler = AdminHandler(s, af)

        update = _update(user_id=1)
        ctx = MagicMock()
        ctx.args = ["42"]
        # Use a temp directory so save_access writes to disk without error
        with patch("src.config.settings.CONFIG_DIR", tmp_path):
            await handler.add_user(update, ctx)
        assert 42 in s.access.allowed_user_ids
        update.message.reply_text.assert_awaited()

    @pytest.mark.asyncio
    async def test_add_user_rejected_for_non_admin(self) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(admin_ids=[1])
        af = AccessFilter(s)
        handler = AdminHandler(s, af)

        update = _update(user_id=99)
        ctx = MagicMock()
        ctx.args = ["42"]
        await handler.add_user(update, ctx)
        assert 42 not in s.access.allowed_user_ids

    @pytest.mark.asyncio
    async def test_list_access(self) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(admin_ids=[1], allowed_users=[10, 20])
        af = AccessFilter(s)
        handler = AdminHandler(s, af)

        update = _update(user_id=1)
        ctx = MagicMock()
        await handler.list_access(update, ctx)
        update.message.reply_text.assert_awaited_once()
        call_text = update.message.reply_text.call_args[0][0]
        assert "10" in call_text
        assert "20" in call_text

    @pytest.mark.asyncio
    async def test_reactions_on_as_admin(self, tmp_path) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(admin_ids=[1])
        s.access.reactions_enabled = False
        af = AccessFilter(s)
        handler = AdminHandler(s, af)

        update = _update(user_id=1)
        ctx = MagicMock()
        with patch("src.config.settings.CONFIG_DIR", tmp_path):
            await handler.reactions_on(update, ctx)
        assert s.access.reactions_enabled is True
        update.message.reply_text.assert_awaited()

    @pytest.mark.asyncio
    async def test_reactions_off_as_admin(self, tmp_path) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(admin_ids=[1])
        s.access.reactions_enabled = True
        af = AccessFilter(s)
        handler = AdminHandler(s, af)

        update = _update(user_id=1)
        ctx = MagicMock()
        with patch("src.config.settings.CONFIG_DIR", tmp_path):
            await handler.reactions_off(update, ctx)
        assert s.access.reactions_enabled is False
        update.message.reply_text.assert_awaited()

    @pytest.mark.asyncio
    async def test_reactions_status_as_admin(self) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(admin_ids=[1])
        s.access.reactions_enabled = True
        af = AccessFilter(s)
        handler = AdminHandler(s, af)

        update = _update(user_id=1)
        ctx = MagicMock()
        await handler.reactions_status(update, ctx)
        update.message.reply_text.assert_awaited_once()
        call_text = update.message.reply_text.call_args[0][0]
        # Should show status information
        assert "Статус реакций" in call_text

    @pytest.mark.asyncio
    async def test_reactions_commands_rejected_for_non_admin(self) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(admin_ids=[1])
        af = AccessFilter(s)
        handler = AdminHandler(s, af)

        update = _update(user_id=99)  # Non-admin user
        ctx = MagicMock()

        # Test all three commands are rejected
        await handler.reactions_on(update, ctx)
        await handler.reactions_off(update, ctx)
        await handler.reactions_status(update, ctx)

        # All should have rejected the user
        assert update.message.reply_text.call_count == 3

    @pytest.mark.asyncio
    async def test_date_on_as_admin(self, tmp_path) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(admin_ids=[1])
        s.access.always_append_date_enabled = False
        af = AccessFilter(s)
        handler = AdminHandler(s, af)

        update = _update(user_id=1)
        ctx = MagicMock()
        with patch("src.config.settings.CONFIG_DIR", tmp_path):
            await handler.date_on(update, ctx)
        assert s.access.always_append_date_enabled is True
        update.message.reply_text.assert_awaited()

    @pytest.mark.asyncio
    async def test_date_off_as_admin(self, tmp_path) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(admin_ids=[1])
        s.access.always_append_date_enabled = True
        af = AccessFilter(s)
        handler = AdminHandler(s, af)

        update = _update(user_id=1)
        ctx = MagicMock()
        with patch("src.config.settings.CONFIG_DIR", tmp_path):
            await handler.date_off(update, ctx)
        assert s.access.always_append_date_enabled is False
        update.message.reply_text.assert_awaited()

    @pytest.mark.asyncio
    async def test_date_status_as_admin(self) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(admin_ids=[1])
        s.access.always_append_date_enabled = True
        af = AccessFilter(s)
        handler = AdminHandler(s, af)

        update = _update(user_id=1)
        ctx = MagicMock()
        await handler.date_status(update, ctx)
        update.message.reply_text.assert_awaited_once()
        call_text = update.message.reply_text.call_args[0][0]
        # Should show status information
        assert "Статус добавления даты" in call_text

    @pytest.mark.asyncio
    async def test_date_commands_rejected_for_non_admin(self) -> None:
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(admin_ids=[1])
        af = AccessFilter(s)
        handler = AdminHandler(s, af)

        update = _update(user_id=99)  # Non-admin user
        ctx = MagicMock()

        # Test all three commands are rejected
        await handler.date_on(update, ctx)
        await handler.date_off(update, ctx)
        await handler.date_status(update, ctx)

        # All should have rejected the user
        assert update.message.reply_text.call_count == 3


# ------------------------------------------------------------------
# _error_handler
# ------------------------------------------------------------------


class TestErrorHandler:
    @pytest.mark.asyncio
    async def test_network_error_logs_warning(self, caplog) -> None:
        """NetworkError should be logged at WARNING without re-raising."""
        import logging

        from telegram.error import NetworkError

        from src.bot.bot import _error_handler

        ctx = MagicMock()
        ctx.error = NetworkError("502 Bad Gateway")

        with caplog.at_level(logging.WARNING, logger="src.bot.bot"):
            await _error_handler(object(), ctx)

        assert any("NetworkError" in r.message for r in caplog.records)
        assert all(r.levelno < logging.ERROR for r in caplog.records)

    @pytest.mark.asyncio
    async def test_timed_out_logs_warning(self, caplog) -> None:
        """TimedOut should be logged at WARNING without re-raising."""
        import logging

        from telegram.error import TimedOut

        from src.bot.bot import _error_handler

        ctx = MagicMock()
        ctx.error = TimedOut()

        with caplog.at_level(logging.WARNING, logger="src.bot.bot"):
            await _error_handler(object(), ctx)

        assert any("TimedOut" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_telegram_error_logs_error(self, caplog) -> None:
        """Non-transient TelegramError should be logged at ERROR level."""
        import logging

        from telegram.error import TelegramError

        from src.bot.bot import _error_handler

        ctx = MagicMock()
        ctx.error = TelegramError("some api error")

        with caplog.at_level(logging.ERROR, logger="src.bot.bot"):
            await _error_handler(object(), ctx)

        assert any(r.levelno == logging.ERROR for r in caplog.records)


# ------------------------------------------------------------------
# Search unavailable notification
# ------------------------------------------------------------------


class TestSearchUnavailableNotification:
    @pytest.mark.asyncio
    async def test_search_unavailable_prepends_notice(self) -> None:
        """When search_unavailable=True, response should start with the notice."""
        from src.api.mistral_client import GenerateResponse
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(allowed_users=[1])
        s.bot.enable_streaming = False

        mistral = MagicMock()
        mistral.generate = AsyncMock(
            return_value=GenerateResponse(
                content="answer text",
                model="mistral-small-latest",
                search_unavailable=True,
            )
        )
        mistral._web_search = MagicMock()  # non-None to trigger web search status message
        mistral._should_use_web_search = MagicMock(return_value=True)
        af = AccessFilter(s)
        handler = MessageHandler(s, mistral, af)

        update = _update(user_id=1, text="what's new?")
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=status_msg)
        ctx = MagicMock()
        ctx.bot.send_chat_action = AsyncMock()
        await handler.handle(update, ctx)

        # The edited text should include the search-unavailable notice
        edit_call_text = status_msg.edit_text.call_args[0][0]
        assert "Поиск временно недоступен" in edit_call_text

    @pytest.mark.asyncio
    async def test_no_notice_when_search_available(self) -> None:
        """When search_unavailable=False, no notice should be prepended."""
        from src.api.mistral_client import GenerateResponse
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(allowed_users=[1])
        s.bot.enable_streaming = False

        mistral = MagicMock()
        mistral.generate = AsyncMock(
            return_value=GenerateResponse(
                content="answer text",
                model="mistral-small-latest",
                search_unavailable=False,
            )
        )
        mistral._web_search = None
        mistral._should_use_web_search = MagicMock(return_value=False)
        af = AccessFilter(s)
        handler = MessageHandler(s, mistral, af)

        update = _update(user_id=1, text="hello")
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=status_msg)
        ctx = MagicMock()
        ctx.bot.send_chat_action = AsyncMock()
        await handler.handle(update, ctx)

        edit_call_text = status_msg.edit_text.call_args[0][0]
        assert "Поиск временно недоступен" not in edit_call_text


# ------------------------------------------------------------------
# Typing indicator
# ------------------------------------------------------------------


class TestTypingIndicator:
    @pytest.mark.asyncio
    async def test_send_typing_periodically_sends_action_after_interval(self) -> None:
        """_send_typing_periodically should sleep first and then call send_chat_action."""
        import asyncio

        bot = MagicMock()
        bot.send_chat_action = AsyncMock()

        # Use a tiny but non-zero interval to better simulate real timing
        task = asyncio.create_task(_send_typing_periodically(bot, chat_id=42, interval=0.01))
        # Wait for the interval to elapse and the action to fire
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        bot.send_chat_action.assert_awaited_with(
            chat_id=42, action=pytest.importorskip("telegram").constants.ChatAction.TYPING
        )

    @pytest.mark.asyncio
    async def test_send_typing_periodically_does_not_send_before_interval(self) -> None:
        """_send_typing_periodically should NOT call send_chat_action before the interval."""
        import asyncio

        bot = MagicMock()
        bot.send_chat_action = AsyncMock()

        # Large interval — task should not send before we cancel it
        task = asyncio.create_task(_send_typing_periodically(bot, chat_id=42, interval=100.0))
        # Yield once to let the task start its sleep
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        bot.send_chat_action.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_sends_typing_action(self) -> None:
        """handle() must call send_chat_action with TYPING before generating a response."""
        from telegram.constants import ChatAction

        from src.api.mistral_client import GenerateResponse
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(allowed_users=[1])
        s.bot.enable_streaming = False

        mistral = MagicMock()
        mistral.generate = AsyncMock(
            return_value=GenerateResponse(
                content="hello",
                model="mistral-small-latest",
            )
        )
        mistral._web_search = None
        mistral._should_use_web_search = MagicMock(return_value=False)
        af = AccessFilter(s)
        handler = MessageHandler(s, mistral, af)

        update = _update(user_id=1, text="hi")
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=status_msg)
        ctx = MagicMock()
        ctx.bot.send_chat_action = AsyncMock()

        await handler.handle(update, ctx)

        ctx.bot.send_chat_action.assert_awaited()
        first_call = ctx.bot.send_chat_action.call_args_list[0]
        assert first_call.kwargs.get("action") == ChatAction.TYPING or (
            len(first_call.args) >= 2 and first_call.args[1] == ChatAction.TYPING
        )
