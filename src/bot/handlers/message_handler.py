"""Handler for regular user messages forwarded to the Mistral model."""

from __future__ import annotations

import logging
import re
import time

from telegram import Message, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.api.mistral_client import MistralClient
from src.bot.filters.access_filter import AccessFilter
from src.config.settings import AppSettings

logger = logging.getLogger(__name__)

# Localized text constants (Russian)
MSG_ERROR = "⚠️ Произошла ошибка при обращении к модели. Попробуйте позже."
MSG_STREAMING_INDICATOR = "⏳ Генерация..."
MSG_MULTI_PART_PREFIX = "часть"  # Used as: "(часть 2/3)"


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
            # Determine if we should use streaming based on configuration
            use_streaming = self._settings.bot.enable_streaming

            if use_streaming:
                # Use streaming for progressive response
                await self._handle_streaming_response(
                    message, prompt, context_id, formatted_message
                )
            else:
                # Use non-streaming (original behavior)
                response = await self._mistral.generate(prompt, user_id=context_id)
                response_text = response.content

                # Store both user message and bot response in history
                if context_id is not None:
                    self._mistral._memory.add_message(context_id, "user", formatted_message)
                    self._mistral._memory.add_message(context_id, "assistant", response_text)
                    logger.debug(
                        "Stored user message and bot response in memory "
                        f"for context_id={context_id}"
                    )

                # Send response (split by max length)
                max_len = self._settings.bot.max_message_length
                for chunk in _split_text(response_text, max_len):
                    normalized = _normalize_markdown_for_telegram(chunk)
                    await message.reply_text(normalized, parse_mode="Markdown")

        except Exception:
            logger.exception("Failed to generate response")
            await message.reply_text(MSG_ERROR)
            return

    async def _handle_streaming_response(
        self,
        message: Message,
        prompt: str,
        context_id: int | None,
        formatted_message: str,
    ) -> None:
        """Handle streaming response with progressive message updates."""


        accumulated_content = ""
        last_update_time = time.time()
        sent_message = None
        update_interval = self._settings.bot.streaming_update_interval
        threshold = self._settings.bot.streaming_threshold

        try:
            async for chunk_content, full_content, is_final in self._mistral.generate_stream(
                prompt, user_id=context_id
            ):
                accumulated_content = full_content
                current_time = time.time()

                # Only update if we've accumulated enough content and enough time has passed
                should_update = (
                    is_final
                    or (
                        len(accumulated_content) >= threshold
                        and (current_time - last_update_time) >= update_interval
                    )
                )

                if should_update and accumulated_content:
                    normalized = _normalize_markdown_for_telegram(accumulated_content)

                    # For long messages, truncate with indicator during streaming
                    max_len = self._settings.bot.max_message_length
                    if len(normalized) > max_len and not is_final:
                        # Truncate and add streaming indicator
                        normalized = normalized[:max_len - 20] + f"\n\n{MSG_STREAMING_INDICATOR}"

                    try:
                        if sent_message is None:
                            # Send initial message
                            sent_message = await message.reply_text(
                                normalized, parse_mode="Markdown"
                            )
                        else:
                            # Update existing message
                            await sent_message.edit_text(
                                normalized, parse_mode="Markdown"
                            )
                        last_update_time = current_time
                    except BadRequest as e:
                        # Handle cases where message content hasn't changed
                        if "message is not modified" not in str(e).lower():
                            logger.warning(f"Failed to update message: {e}")

            # After streaming completes, handle long messages by splitting
            if accumulated_content:
                # Store in history
                if context_id is not None:
                    self._mistral._memory.add_message(context_id, "user", formatted_message)
                    self._mistral._memory.add_message(
                        context_id, "assistant", accumulated_content
                    )
                    logger.debug(
                        "Stored user message and bot response in memory "
                        f"for context_id={context_id}"
                    )

                # Split and send full response if it exceeds max length
                max_len = self._settings.bot.max_message_length
                chunks = _split_text(accumulated_content, max_len)

                if len(chunks) > 1:
                    # First chunk was already sent/updated, send remaining chunks
                    for i, chunk in enumerate(chunks[1:], start=2):
                        normalized = _normalize_markdown_for_telegram(chunk)
                        await message.reply_text(
                            f"({MSG_MULTI_PART_PREFIX} {i}/{len(chunks)})\n\n{normalized}",
                            parse_mode="Markdown"
                        )
                elif sent_message:
                    # Update the message one final time without the streaming indicator
                    normalized = _normalize_markdown_for_telegram(chunks[0])
                    try:
                        await sent_message.edit_text(normalized, parse_mode="Markdown")
                    except BadRequest as e:
                        if "message is not modified" not in str(e).lower():
                            logger.warning(f"Failed to update final message: {e}")

        except Exception:
            logger.exception("Failed during streaming response")
            # Send error message
            if sent_message is None:
                await message.reply_text(MSG_ERROR)
            else:
                try:
                    await sent_message.edit_text(MSG_ERROR)
                except Exception:
                    await message.reply_text(MSG_ERROR)

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


def _normalize_markdown_for_telegram(text: str) -> str:
    """Convert markdown to Telegram-compatible format.

    Telegram supports: *bold*, _italic_, __underline__, ~strikethrough~, `code`
    But NOT: **bold** (double asterisks), ### headers, - lists (shows as-is)

    Conversions:
    - #### Heading → *Heading* (bold)
    - ### Heading → *Heading* (bold)
    - ## Heading → *Heading* (bold)
    - **text** → *text* (double asterisks to single)
    - - list item → • list item (for better formatting)
    """

    # Convert markdown headers (####, ###, ##) to bold
    text = re.sub(r'^#{2,4}\s+(.+?)$', r'*\1*', text, flags=re.MULTILINE)

    # Convert double asterisks to single (markdown bold to Telegram bold)
    text = text.replace('**', '*')

    # Convert markdown dashes to bullet points for better readability
    text = re.sub(r'^-\s+', '• ', text, flags=re.MULTILINE)

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
