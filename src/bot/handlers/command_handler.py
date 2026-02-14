"""Basic /start and /help command handlers."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.filters.access_filter import AccessFilter

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
)


class CommandHandler:
    """Handles ``/start`` and ``/help`` commands."""

    def __init__(self, access_filter: AccessFilter, bot_username: str) -> None:
        self._access = access_filter
        self._bot_username = bot_username

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
