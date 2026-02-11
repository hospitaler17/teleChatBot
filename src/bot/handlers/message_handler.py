"""Handler for regular user messages forwarded to the Gemma model."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from src.api.gemma_client import GemmaClient
from src.bot.filters.access_filter import AccessFilter
from src.config.settings import AppSettings

logger = logging.getLogger(__name__)


class MessageHandler:
    """Processes incoming text messages via the Gemma model."""

    def __init__(
        self,
        settings: AppSettings,
        gemma_client: GemmaClient,
        access_filter: AccessFilter,
    ) -> None:
        self._settings = settings
        self._gemma = gemma_client
        self._access = access_filter

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Entry point called by the dispatcher for every text message."""
        if not self._access.check(update):
            return

        message = update.message
        if message is None or not message.text:
            return

        prompt = self._extract_prompt(message.text)
        if not prompt.strip():
            return

        await context.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

        try:
            response_text = await self._gemma.generate(prompt)
        except Exception:
            logger.exception("Failed to generate response")
            await message.reply_text("⚠️ Произошла ошибка при обращении к модели. Попробуйте позже.")
            return

        # Telegram limits messages to 4096 chars
        max_len = self._settings.bot.max_message_length
        for chunk in _split_text(response_text, max_len):
            await message.reply_text(chunk)

    # ------------------------------------------------------------------

    def _extract_prompt(self, text: str) -> str:
        """Strip the bot @mention from the message text."""
        bot_username = self._settings.bot.username
        if bot_username:
            text = text.replace(f"@{bot_username}", "").strip()
        return text


def _split_text(text: str, max_length: int) -> list[str]:
    """Split *text* into chunks of at most *max_length* characters."""
    if len(text) <= max_length:
        return [text]
    chunks: list[str] = []
    while text:
        chunks.append(text[:max_length])
        text = text[max_length:]
    return chunks
