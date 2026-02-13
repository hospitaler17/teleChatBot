"""Tests for message and command handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handlers.admin_handler import AdminHandler
from src.bot.handlers.command_handler import CommandHandler
from src.bot.handlers.message_handler import MessageHandler, _split_text
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
        from src.bot.filters.access_filter import AccessFilter

        s = _settings(allowed_users=[1])
        mistral = MagicMock()
        mistral.generate = AsyncMock(return_value="response text")
        af = AccessFilter(s)
        handler = MessageHandler(s, mistral, af)

        update = _update(user_id=1, text="ping")
        ctx = MagicMock()
        ctx.bot.send_chat_action = AsyncMock()
        await handler.handle(update, ctx)
        update.message.reply_text.assert_awaited_once_with("response text")

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
