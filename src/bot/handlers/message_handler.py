"""Handler for regular user messages forwarded to the Mistral model."""

from __future__ import annotations

import asyncio
import base64
import logging
import time

from telegram import Message, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest, RetryAfter
from telegram.ext import ContextTypes

from src.api.mistral_client import MistralClient
from src.api.reaction_analyzer import ReactionAnalyzer
from src.bot.filters.access_filter import AccessFilter
from src.config.settings import AppSettings
from src.utils.telegram_format import markdown_to_telegram

logger = logging.getLogger(__name__)

# Localized text constants (Russian)
MSG_ERROR = "⚠️ Произошла ошибка при обращении к модели. Попробуйте позже."
MSG_STREAMING_INDICATOR = "⏳ Генерация..."
MSG_MULTI_PART_PREFIX = "часть"  # Used as: "(часть 2/3)"


def _detect_image_mime(data: bytearray | bytes) -> str:
    """Return MIME type based on image magic bytes, defaulting to image/jpeg."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:3] == b"GIF":
        return "image/gif"
    return "image/jpeg"


def _truncate_safely(text: str, max_len: int, indicator: str) -> str:
    """Truncate text safely without breaking markdown formatting.

    Args:
        text: The text to truncate
        max_len: Maximum length
        indicator: Streaming indicator to append

    Returns:
        Truncated text with indicator
    """
    indicator_with_newlines = f"\n\n{indicator}"
    available_len = max_len - len(indicator_with_newlines)

    if available_len <= 0:
        return indicator

    if len(text) <= available_len:
        return text + indicator_with_newlines

    # Truncate text
    truncated = text[:available_len]

    # Close any open markdown formatting to prevent parse errors
    # Count unclosed asterisks, underscores, backticks
    asterisk_count = truncated.count('*') % 2
    underscore_count = truncated.count('_') % 2
    backtick_count = truncated.count('`') % 2

    # Close open formatting
    if asterisk_count:
        truncated += '*'
    if underscore_count:
        truncated += '_'
    if backtick_count:
        truncated += '`'

    return truncated + indicator_with_newlines


async def _safe_edit_message(
    message: Message,
    text: str,
    parse_mode: str | None = "Markdown",
    max_retries: int = 3,
    allow_parse_retry: bool = True
) -> bool:
    """Safely edit a message with retry logic for rate limiting.

    Args:
        message: The message to edit
        text: New text content
        parse_mode: Parse mode for formatting (default: "Markdown")
        max_retries: Maximum total attempts (default: 3, including initial attempt)
        allow_parse_retry: Allow retry with parse_mode=None on parse errors

    Returns:
        True if edit was successful, False otherwise
    """
    for attempt in range(max_retries):
        try:
            await message.edit_text(text, parse_mode=parse_mode)
            return True
        except RetryAfter as e:
            if attempt < max_retries - 1:
                # Wait for the specified time plus a small buffer
                wait_time = e.retry_after + 0.5
                logger.warning(
                    f"Rate limit exceeded, waiting {wait_time}s before retry "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait_time)
            else:
                # Max retries exceeded
                logger.error(
                    f"Failed to edit message after {max_retries} attempts "
                    "due to rate limiting"
                )
                return False
        except BadRequest as e:
            # Handle other BadRequest errors (not rate limiting)
            error_msg = str(e).lower()
            if "message is not modified" in error_msg:
                # Content unchanged, consider it a success
                return True
            elif "can't parse" in error_msg or "parse error" in error_msg:
                # Try again without parse mode (preserve retry count)
                if parse_mode is not None and allow_parse_retry:
                    logger.warning(f"Markdown parse error, retrying as plain text: {e}")
                    return await _safe_edit_message(
                        message, text, parse_mode=None,
                        max_retries=max_retries, allow_parse_retry=False
                    )
            # For other BadRequest errors, fail
            logger.warning(f"Failed to edit message: {e}")
            return False
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error while editing message: {e}")
            return False

    return False


async def _safe_send_message(
    message: Message,
    text: str,
    parse_mode: str | None = "Markdown",
    max_retries: int = 3,
    allow_parse_retry: bool = True
) -> Message | None:
    """Safely send a message with retry logic for rate limiting.

    Args:
        message: The original message to reply to
        text: Text content to send
        parse_mode: Parse mode for formatting (default: "Markdown")
        max_retries: Maximum total attempts (default: 3, including initial attempt)
        allow_parse_retry: Allow retry with parse_mode=None on parse errors

    Returns:
        The sent message, or None if failed
    """
    for attempt in range(max_retries):
        try:
            return await message.reply_text(text, parse_mode=parse_mode)
        except RetryAfter as e:
            if attempt < max_retries - 1:
                # Wait for the specified time plus a small buffer
                wait_time = e.retry_after + 0.5
                logger.warning(
                    f"Rate limit exceeded, waiting {wait_time}s before retry "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait_time)
            else:
                # Max retries exceeded
                logger.error(
                    f"Failed to send message after {max_retries} attempts "
                    "due to rate limiting"
                )
                return None
        except BadRequest as e:
            # Try again without parse mode if it's a parse error
            error_msg = str(e).lower()
            if "can't parse" in error_msg or "parse error" in error_msg:
                if parse_mode is not None and allow_parse_retry:
                    logger.warning(f"Markdown parse error, retrying as plain text: {e}")
                    return await _safe_send_message(
                        message, text, parse_mode=None,
                        max_retries=max_retries, allow_parse_retry=False
                    )
            # For other BadRequest errors, fail
            logger.warning(f"Failed to send message: {e}")
            return None
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error while sending message: {e}")
            return None

    return None


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
        self._reaction_analyzer = ReactionAnalyzer(settings)

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

        # Try to add a reaction to the message (if enabled and conditions met)
        # This runs in background to avoid blocking message processing
        asyncio.create_task(self._try_add_reaction(message, prompt))

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

        # Download image data if photo is attached
        image_urls = await self._get_image_urls(message, context)

        try:
            # Determine if we should use streaming based on configuration
            use_streaming = self._settings.bot.enable_streaming

            if use_streaming:
                # Use streaming for progressive response
                await self._handle_streaming_response(
                    message, prompt, context_id, formatted_message, image_urls
                )
            else:
                # Use non-streaming (original behavior)
                # Send initial status message
                status_messages = self._settings.status_messages
                if (
                    self._mistral._web_search
                    and self._mistral._should_use_web_search(prompt)
                ):
                    status_text = status_messages.searching
                else:
                    status_text = status_messages.thinking
                status_msg = await _safe_send_message(
                    message, status_text, parse_mode=None
                )

                response = await self._mistral.generate(
                    prompt, user_id=context_id, image_urls=image_urls
                )
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
                chunks = _split_text(response_text, max_len)
                for i, chunk in enumerate(chunks):
                    normalized = _normalize_markdown_for_telegram(chunk)
                    if i == 0 and status_msg:
                        # Edit the status message with the first chunk
                        success = await _safe_edit_message(
                            status_msg, normalized, parse_mode="Markdown"
                        )
                        if not success:
                            await message.reply_text(normalized, parse_mode="Markdown")
                    else:
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
        image_urls: list[str] | None = None,
    ) -> None:
        """Handle streaming response with progressive message updates."""
        accumulated_content = ""
        last_update_time = time.time()
        sent_message = None
        update_interval = self._settings.bot.streaming_update_interval
        threshold = self._settings.bot.streaming_threshold
        streaming_successful = False

        # Determine the initial status message
        status_messages = self._settings.status_messages
        if (
            self._mistral._web_search
            and self._mistral._should_use_web_search(prompt)
        ):
            status_text = status_messages.searching
        else:
            status_text = status_messages.thinking

        # Send the initial status message
        sent_message = await _safe_send_message(message, status_text, parse_mode=None)

        try:
            async for chunk_content, full_content, is_final in self._mistral.generate_stream(
                prompt, user_id=context_id, image_urls=image_urls
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
                    # Normalize first to get accurate length
                    normalized = _normalize_markdown_for_telegram(accumulated_content)

                    # For long messages during streaming, truncate safely
                    max_len = self._settings.bot.max_message_length
                    display_text = normalized
                    if len(normalized) > max_len and not is_final:
                        # Use markdown-aware truncation
                        display_text = _truncate_safely(
                            normalized, max_len, MSG_STREAMING_INDICATOR
                        )

                    if sent_message is None:
                        # Send initial message
                        sent_message = await _safe_send_message(
                            message, display_text, parse_mode="Markdown"
                        )
                        if sent_message:
                            last_update_time = current_time
                    else:
                        # Update existing message
                        success = await _safe_edit_message(
                            sent_message, display_text, parse_mode="Markdown"
                        )
                        if success:
                            last_update_time = current_time

            # Streaming completed successfully
            streaming_successful = True

            # After streaming completes, handle final message
            if accumulated_content:
                # Calculate chunks with proper accounting for multi-part prefix
                max_len = self._settings.bot.max_message_length
                # Reserve space for multi-part prefix: "(часть X/YY)\n\n" ≈ 20 chars
                chunk_max_len = max_len - 25 if max_len > 25 else max_len
                chunks = _split_text(accumulated_content, chunk_max_len)

                if len(chunks) > 1:
                    # Multi-part message: update first chunk and send remaining
                    first_chunk_normalized = _normalize_markdown_for_telegram(chunks[0])
                    # Add part indicator to first chunk
                    first_chunk_text = (
                        f"({MSG_MULTI_PART_PREFIX} 1/{len(chunks)})\n\n{first_chunk_normalized}"
                    )

                    if sent_message:
                        # Update the first message with proper prefix
                        edit_success = await _safe_edit_message(
                            sent_message, first_chunk_text, parse_mode="Markdown"
                        )
                        if not edit_success:
                            logger.warning(
                                "Failed to edit first chunk of multi-part message; "
                                "sending new message instead"
                            )
                            sent_message = await _safe_send_message(
                                message, first_chunk_text, parse_mode="Markdown"
                            )
                    else:
                        # First message was never sent (short response), send it now
                        sent_message = await _safe_send_message(
                            message, first_chunk_text, parse_mode="Markdown"
                        )

                    # Send remaining chunks
                    for i, chunk in enumerate(chunks[1:], start=2):
                        normalized = _normalize_markdown_for_telegram(chunk)
                        chunk_text = (
                            f"({MSG_MULTI_PART_PREFIX} {i}/{len(chunks)})\n\n{normalized}"
                        )
                        result = await _safe_send_message(
                            message, chunk_text, parse_mode="Markdown"
                        )
                        if result is None:
                            logger.warning(
                                f"Failed to send chunk {i}/{len(chunks)} of multi-part message"
                            )
                else:
                    # Single message: ensure it's sent or updated properly
                    normalized = _normalize_markdown_for_telegram(chunks[0])
                    if sent_message:
                        # Update to remove streaming indicator if present
                        success = await _safe_edit_message(
                            sent_message, normalized, parse_mode="Markdown"
                        )
                        if not success:
                            logger.warning(
                                "Failed to update final streaming message to remove indicator"
                            )
                    else:
                        # Short response that never triggered threshold, send now
                        sent_message = await _safe_send_message(
                            message, normalized, parse_mode="Markdown"
                        )

                # Store in memory only after successful completion
                if streaming_successful and context_id is not None:
                    self._mistral._memory.add_message(context_id, "user", formatted_message)
                    self._mistral._memory.add_message(
                        context_id, "assistant", accumulated_content
                    )
                    logger.debug(
                        "Stored user message and bot response in memory "
                        f"for context_id={context_id}"
                    )

        except Exception:
            logger.exception("Failed during streaming response")
            # Send error message
            if sent_message is None:
                error_msg_sent = await _safe_send_message(message, MSG_ERROR, parse_mode=None)
                if error_msg_sent is None:
                    logger.error("Failed to send error message to user")
            else:
                # Try to edit, if that fails, send a new message
                success = await _safe_edit_message(sent_message, MSG_ERROR, parse_mode=None)
                if not success:
                    error_msg_sent = await _safe_send_message(message, MSG_ERROR, parse_mode=None)
                    if error_msg_sent is None:
                        logger.error("Failed to send error message to user")

    # ------------------------------------------------------------------

    async def _get_image_urls(
        self, message: Message, context: ContextTypes.DEFAULT_TYPE
    ) -> list[str] | None:
        """Download photo from message and return as base64 data URI list.

        Args:
            message: Telegram message that may contain a photo
            context: Telegram bot context for file download

        Returns:
            List with a single base64 data URI, or None if no photo
        """
        if not message.photo:
            return None

        try:
            # Use the largest available photo (last in the list)
            photo = message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            image_bytes = await file.download_as_bytearray()
            mime = _detect_image_mime(image_bytes)
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            data_url = f"data:{mime};base64,{b64}"
            logger.info("Downloaded photo (%d bytes, %s) for vision processing",
                        len(image_bytes), mime)
            return [data_url]
        except Exception:
            logger.exception("Failed to download photo from Telegram")
            return None

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

    async def _try_add_reaction(self, message: Message, text: str) -> None:
        """Try to add a reaction to the message based on sentiment analysis.

        Args:
            message: The Telegram message object
            text: The extracted text from the message
        """
        try:
            # Check if we should analyze this message
            if not self._reaction_analyzer.should_analyze(text):
                return

            logger.info("Analyzing message for reaction")

            # Analyze the mood
            mood = await self._reaction_analyzer.analyze_mood(text)
            if not mood:
                logger.debug("No mood detected")
                return

            # Get the emoji for this mood
            emoji = self._reaction_analyzer.get_reaction_emoji(mood)
            if not emoji:
                logger.warning(f"No emoji configured for mood: {mood}")
                return

            # Set the reaction
            await message.set_reaction(emoji)
            logger.info(f"Set reaction {emoji} for mood {mood}")

        except Exception:
            # Don't fail the message handling if reactions fail
            logger.exception("Failed to add reaction")


def _normalize_markdown_for_telegram(text: str) -> str:
    """Convert markdown to Telegram-compatible format.

    This is a legacy wrapper that delegates to the new utility function.
    Use src.utils.telegram_format.markdown_to_telegram directly in new code.

    Telegram supports: *bold*, _italic_, __underline__, ~strikethrough~, `code`
    But NOT: **bold** (double asterisks), ### headers, - lists (shows as-is)

    Conversions:
    - #### Heading → *Heading* (bold)
    - ### Heading → *Heading* (bold)
    - ## Heading → *Heading* (bold)
    - **text** → *text* (double asterisks to single)
    - - list item → • list item (for better formatting)
    - Special characters are properly escaped to prevent parse errors
    """
    return markdown_to_telegram(text)


def _split_text(text: str, max_length: int) -> list[str]:
    """Split *text* into chunks of at most *max_length* characters."""
    if len(text) <= max_length:
        return [text]
    chunks: list[str] = []
    while text:
        chunks.append(text[:max_length])
        text = text[max_length:]
    return chunks
