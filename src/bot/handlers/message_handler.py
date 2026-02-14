"""Handler for regular user messages forwarded to the Mistral model."""

from __future__ import annotations

import logging

from telegram import Message, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from src.api.mistral_client import MistralClient
from src.bot.filters.access_filter import AccessFilter
from src.config.settings import AppSettings

logger = logging.getLogger(__name__)


class MessageHandler:
    """Processes incoming text messages via the Mistral model."""

    def __init__(
        self,
        settings: AppSettings,
        mistral_client: MistralClient,
        access_filter: AccessFilter,
    ) -> None:
        self._settings = settings
        self._mistral = mistral_client
        self._access = access_filter

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process messages and maintain full conversation history.

        - Records ALL messages in allowed chats to maintain context
        - Only responds to messages directly addressed to the bot
        - Uses full conversation history as context for responses
        - Handles forwarded messages, replies, and media with captions
        """
        message = update.message
        if message is None:
            return

        # Log incoming message details for debugging
        logger.debug(
            f"Incoming message - text: {message.text}, "
            f"has_reply_to: {message.reply_to_message is not None}, "
            f"caption: {message.caption}"
        )

        # Extract text from various message types
        text = self._extract_text_from_message(message)
        logger.debug(f"Extracted text result: {text}")

        if not text:
            logger.debug("No text extracted from message")
            return

        chat_type = message.chat.type

        # Determine context ID and check if this chat/user is allowed
        if chat_type == "private":
            # Private chat - check if user is allowed
            user_id = message.from_user.id if message.from_user else None
            if not self._access.is_allowed_user(user_id):
                logger.debug(f"Rejected private message from disallowed user {user_id}")
                return
            context_id = user_id
            is_direct_request = True  # All private messages are direct
            sender_name = "You" if message.from_user else "Unknown"
        elif chat_type in ("group", "supergroup"):
            # Group chat - check if chat is allowed
            if not self._access.is_allowed_chat(message.chat.id):
                logger.debug(f"Rejected message from disallowed chat {message.chat.id}")
                return
            context_id = message.chat.id
            # In groups, check if message is addressed to bot
            is_direct_request = self._access.is_direct_request(message)

            # Get sender name for context
            if message.from_user:
                sender_name = (
                    message.from_user.username or message.from_user.first_name or "Unknown"
                )
            else:
                sender_name = "Unknown"
        else:
            return

        # Extract actual prompt (removing bot mention if present)
        prompt = self._extract_prompt(text)
        if not prompt.strip():
            return

        # Format message for history: "[sender]: message"
        formatted_message = f"[{sender_name}]: {prompt}"

        # Only respond if message is directly addressed to the bot
        if not is_direct_request:
            logger.debug(
                f"Ignoring message in group (not addressed to bot): {formatted_message[:50]}..."
            )
            # Still add to history for context, even if not responding
            if context_id is not None:
                self._mistral._memory.add_message(context_id, "user", formatted_message)
            return

        await context.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

        try:
            response_text = await self._mistral.generate(prompt, user_id=context_id)
        except Exception:
            logger.exception("Failed to generate response")
            await message.reply_text("⚠️ Произошла ошибка при обращении к модели. Попробуйте позже.")
            return

        # Store both user message and bot response in history AFTER generating response
        if context_id is not None:
            self._mistral._memory.add_message(context_id, "user", formatted_message)
            self._mistral._memory.add_message(context_id, "assistant", response_text)
            logger.debug(
                f"Stored user message and bot response in memory for context_id={context_id}"
            )

        # Send response (split by max length)
        max_len = self._settings.bot.max_message_length
        for chunk in _split_text(response_text, max_len):
            await message.reply_text(chunk, parse_mode="Markdown")

    # ------------------------------------------------------------------

    def _extract_text_from_message(self, message: Message) -> str | None:
        """Extract text from various message types.

        Handles:
        - Regular text messages
        - Forwarded messages
        - Replies to messages
        - Media with captions (photo, video, audio, etc.)
        """
        text_parts = []

        # 1. Check for reply to message (add quoted text first)
        if message.reply_to_message:
            logger.debug("Found reply_to_message")
            # Get text from replied message
            replied_text = self._extract_text_from_message(message.reply_to_message)
            if replied_text:
                replied_user = message.reply_to_message.from_user
                replied_name = replied_user.first_name if replied_user else "Неизвестно"
                # Clean up the replied text if it contains nested quotes or context tags
                replied_text_clean = (
                    replied_text.replace("<context>", "").replace("</context>", "").strip()
                )

                # Check for quote in message (Telegram Premium feature)
                # If message has specific quote attribute, use that,
                # otherwise use full replied message
                quote_text = getattr(message, "quote", None)
                if quote_text:
                    replied_text_clean = (
                        quote_text.text if hasattr(quote_text, "text") else str(quote_text)
                    )

                # Format with XML-like tags for better model comprehension
                # Using a larger limit (800 chars) to give enough context
                quote_limit = 800
                quote_content = replied_text_clean[:quote_limit]
                if len(replied_text_clean) > quote_limit:
                    quote_content += "..."

                quote = f"<context>\nСообщение от {replied_name}:\n{quote_content}\n</context>"
                logger.debug(f"Added quote to text_parts: {quote[:60]}...")
                text_parts.append(quote)
            else:
                logger.debug("reply_to_message had no extractable text")

        # 2. Check for forwarded message - safely check for attributes
        forward_source = None
        if hasattr(message, "forward_origin") and message.forward_origin:
            forward_source = f"[Переслано: {message.forward_origin}]"
            logger.debug(f"Processing forward message: {forward_source}")

        if forward_source:
            text_parts.append(forward_source)

        # 3. Check for regular text
        if message.text:
            text_parts.append(message.text)
            logger.debug(f"Added text to text_parts: {message.text[:50]}")

        # 4. Check for media with caption
        elif message.caption:
            media_type = self._get_media_type(message)
            if media_type:
                text_parts.append(f"[{media_type}] {message.caption}")
            else:
                text_parts.append(message.caption)
            logger.debug(f"Added caption to text_parts: {message.caption[:50]}")

        # 5. Handle media without caption
        elif self._get_media_type(message):
            media_type = self._get_media_type(message)
            text_parts.append(f"[{media_type}]")
            logger.debug(f"Added media type to text_parts: {media_type}")

        # Combine all parts
        if text_parts:
            result = "\n".join(text_parts)
            logger.debug(f"Final text result ({len(text_parts)} parts): {result[:80]}")
            return result

        logger.debug("No text parts found for message")
        return None

    def _get_media_type(self, message: Message) -> str | None:
        """Identify the type of media in a message."""
        if message.photo:
            return "Фото"
        elif message.video:
            return "Видео"
        elif message.audio:
            return "Аудио"
        elif message.voice:
            return "Голосовое сообщение"
        elif message.document:
            return "Документ"
        elif message.sticker:
            return "Стикер"
        elif message.animation:
            return "Анимация"
        elif message.location:
            return "Геолокация"
        elif message.contact:
            return "Контакт"
        elif message.invoice:
            return "Счет"
        return None

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
