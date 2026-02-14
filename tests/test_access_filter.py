"""Tests for the access filter."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.bot.filters.access_filter import AccessFilter
from src.config.settings import AccessSettings, AdminSettings, AppSettings, BotSettings


def _make_settings(
    admin_ids: list[int] | None = None,
    allowed_users: list[int] | None = None,
    allowed_chats: list[int] | None = None,
    bot_username: str = "testbot",
) -> AppSettings:
    return AppSettings(
        admin=AdminSettings(user_ids=admin_ids or []),
        access=AccessSettings(
            allowed_user_ids=allowed_users or [],
            allowed_chat_ids=allowed_chats or [],
        ),
        bot=BotSettings(username=bot_username),
    )


def _make_update(
    user_id: int = 1,
    chat_type: str = "private",
    chat_id: int = 1,
    text: str = "hello",
    username: str | None = None,
    reply_from_username: str | None = None,
    reply_is_bot: bool = False,
    entities: list | None = None,
) -> MagicMock:
    update = MagicMock()
    update.message.from_user.id = user_id
    update.message.chat.type = chat_type
    update.message.chat.id = chat_id
    update.message.text = text
    update.message.from_user.username = username

    if reply_from_username:
        update.message.reply_to_message.from_user.username = reply_from_username
        update.message.reply_to_message.from_user.is_bot = reply_is_bot
    else:
        update.message.reply_to_message = None

    update.message.entities = entities
    return update


# ------------------------------------------------------------------
# Private chat tests
# ------------------------------------------------------------------


def test_private_allowed_user() -> None:
    af = AccessFilter(_make_settings(allowed_users=[10]))
    update = _make_update(user_id=10, chat_type="private")
    assert af.check(update) is True


def test_private_disallowed_user() -> None:
    af = AccessFilter(_make_settings(allowed_users=[10]))
    update = _make_update(user_id=99, chat_type="private")
    assert af.check(update) is False


def test_private_admin_always_allowed() -> None:
    af = AccessFilter(_make_settings(admin_ids=[5]))
    update = _make_update(user_id=5, chat_type="private")
    assert af.check(update) is True


# ------------------------------------------------------------------
# Group chat tests
# ------------------------------------------------------------------


def test_group_disallowed_chat() -> None:
    af = AccessFilter(_make_settings(allowed_chats=[-100]))
    update = _make_update(chat_type="group", chat_id=-999)
    assert af.check(update) is False


def test_group_allowed_chat_no_mention() -> None:
    """Allowed chat but no direct mention → reject."""
    af = AccessFilter(_make_settings(allowed_chats=[-100]))
    update = _make_update(chat_type="group", chat_id=-100)
    assert af.check(update) is False


def test_group_allowed_chat_with_reply() -> None:
    """Reply to bot message in allowed chat → accept."""
    af = AccessFilter(_make_settings(allowed_chats=[-100], bot_username="testbot"))
    update = _make_update(
        chat_type="group",
        chat_id=-100,
        reply_from_username="testbot",
        reply_is_bot=True,
    )
    assert af.check(update) is True


def test_group_allowed_chat_with_mention() -> None:
    """@mention of bot in allowed chat → accept."""
    entity = MagicMock()
    entity.type = "mention"
    entity.offset = 0
    entity.length = 8  # @testbot

    af = AccessFilter(_make_settings(allowed_chats=[-100], bot_username="testbot"))
    update = _make_update(
        chat_type="group",
        chat_id=-100,
        text="@testbot what's up?",
        entities=[entity],
    )
    assert af.check(update) is True


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


def test_no_message() -> None:
    af = AccessFilter(_make_settings())
    update = MagicMock()
    update.message = None
    assert af.check(update) is False
