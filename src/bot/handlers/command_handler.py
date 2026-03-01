"""Basic /start, /help and /info command handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.filters.access_filter import AccessFilter

if TYPE_CHECKING:
    from src.api.mistral_client import MistralClient

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "🤖 *teleChatBot*\n\n"
    "Я бот-мост к Mistral AI.\n\n"
    "*Как пользоваться:*\n"
    "• В личном диалоге — просто отправьте сообщение.\n"
    "• В групповом чате — упомяните меня через `@{username}` или ответьте на моё сообщение.\n\n"
    "*Команды:*\n"
    "/start — приветствие\n"
    "/help — эта справка\n"
    "/info — информация о пользователе и использовании контекста\n"
)


class CommandHandler:
    """Handles ``/start``, ``/help`` and ``/info`` commands."""

    def __init__(
        self,
        access_filter: AccessFilter,
        bot_username: str,
        mistral_client: MistralClient | None = None,
    ) -> None:
        self._access = access_filter
        self._bot_username = bot_username
        self._mistral = mistral_client

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """``/start`` command."""
        if not self._access.check(update):
            return
        await update.message.reply_text(
            "Привет! Я *teleChatBot* 🤖\nОтправь /help для справки.",
            parse_mode="Markdown",
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """``/help`` command."""
        if not self._access.check(update):
            return
        text = HELP_TEXT.replace("{username}", self._bot_username)
        await update.message.reply_text(text, parse_mode="Markdown")

    async def info(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """``/info`` command — display user ID, context usage and token stats."""
        if not self._access.check(update):
            return

        message = update.message
        if message is None:
            return

        user_id = message.from_user.id if message.from_user else None

        # Determine the context ID used for conversation history
        chat_type = message.chat.type
        if chat_type == "private":
            context_id = user_id
        else:
            context_id = message.chat.id

        if self._mistral is not None and context_id is not None:
            info = self._mistral.get_context_info(context_id)
            used = info["used"]
            limit = info["limit"]
            if limit:
                context_line = f"{used}/{limit} ({int(used / limit * 100)}%)"
            else:
                context_line = f"{used}/—"
            cached_tokens = info["cached_tokens"]
            system_tokens = info["system_tokens"]
            total_tokens = info["total_tokens"]

            text = (
                f"Ваш user\\_id: `{user_id}`\n"
                f"Использование контекста: {context_line}\n"
                f"Токены:\n"
                f"  • В кэше: {cached_tokens}\n"
                f"  • Системный промт: {system_tokens}\n"
                f"  • Суммарно: {total_tokens}"
            )
        else:
            text = f"Ваш user\\_id: `{user_id}`"

        await message.reply_text(text, parse_mode="Markdown")
