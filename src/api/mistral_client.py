"""Mistral API client."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from mistralai import Mistral
from mistralai.models import SystemMessage, UserMessage

from src.api.conversation_memory import ConversationMemory
from src.api.model_selector import TOKEN_ESTIMATION_MULTIPLIER, ModelSelector, requires_current_date
from src.api.web_search import WebSearchClient
from src.config.settings import AppSettings

logger = logging.getLogger(__name__)

# Russian month names for date formatting
RUSSIAN_MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
]

# Chain-of-thought reasoning instruction added to system prompt when reasoning mode is enabled
REASONING_INSTRUCTION = (
    "\n\n[REASONING MODE]\n"
    "Думай шаг за шагом. Подробно объясняй свои рассуждения и решения. "
    "Разбивай сложные задачи на этапы и явно показывай ход своих мыслей "
    "перед тем, как дать окончательный ответ."
)


@dataclass
class GenerateResponse:
    """Response from model generation with metadata."""

    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens


class MistralClient:
    """Thin wrapper around the Mistral AI SDK."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._client = Mistral(api_key=settings.mistral_api_key)
        self._web_search: Optional[WebSearchClient] = None
        self._memory = ConversationMemory(max_history=settings.mistral.conversation_history_size)

        # Initialize model selector for dynamic model selection
        self._model_selector = ModelSelector(default_model=settings.mistral.model)

        # Initialize web search if enabled with multiple providers
        if settings.mistral.enable_web_search:
            self._web_search = WebSearchClient(
                google_api_key=settings.google_api_key or None,
                google_search_engine_id=settings.google_search_engine_id or None,
            )
            logger.info(
                "Web search enabled with multi-provider fallback (Google → SearXNG → DuckDuckGo)"
            )

        logger.info("MistralClient initialised with default model=%s", settings.mistral.model)
        logger.info("Dynamic model selection enabled")
        logger.info("Web search setting: enable_web_search=%s", settings.mistral.enable_web_search)
        logger.info(
            "Conversation history: max_history=%d messages",
            settings.mistral.conversation_history_size,
        )

    async def generate(self, prompt: str, user_id: Optional[int] = None) -> GenerateResponse:
        """
        Send *prompt* to the Mistral model and return the response with metadata.

        Args:
            prompt: The user's message/question
            user_id: Context ID for conversation history tracking
                     (user_id for private chats, chat_id for groups)

        Returns:
            GenerateResponse with content, model, and token usage information
        """
        try:
            messages = []

            # Build system message
            system_content = self._settings.mistral.system_prompt

            # Add chain-of-thought reasoning instruction when reasoning mode is active
            # (both the config flag and the runtime toggle must be True)
            reasoning_active = (
                self._settings.mistral.reasoning_mode
                and self._settings.access.reasoning_mode_enabled
            )
            if reasoning_active:
                system_content += REASONING_INSTRUCTION
                logger.info("Reasoning mode active: added CoT instruction to system prompt")

            # Add current date to system prompt if query requires it or if
            # always_append_date flag is enabled (both config and runtime must be enabled)
            # This ensures the model always sees the correct date for time-sensitive queries
            always_append = (
                self._settings.mistral.always_append_date
                and self._settings.access.always_append_date_enabled
            )
            if always_append or requires_current_date(prompt):
                now = datetime.now()
                # Format date in a clear, unambiguous way (in Russian for better understanding)
                current_date_str = f"{now.day} {RUSSIAN_MONTHS[now.month - 1]} {now.year} года"
                current_time = now.strftime("%H:%M")

                # Add explicit date context with clear instructions (English)
                # Make it very prominent so the model cannot ignore it
                date_info = (
                    f"\n\n[CRITICAL CONTEXT - CURRENT DATE]\n"
                    f"TODAY: {current_date_str} ({now.year})\n"
                    f"CURRENT YEAR: {now.year}\n"
                    f"TIME: {current_time}\n\n"
                    f"IMPORTANT INSTRUCTIONS:\n"
                    f"- Use THIS DATE ({now.year}) for all time-sensitive queries\n"
                    f"- Your training data is from 2024 and earlier — it is OUTDATED\n"
                    f"- When user asks about 'this year' or 'recently', they mean {now.year}\n"
                    f"- Do NOT mention dates from your training period (2023-2024)\n"
                    f"- Answer as if you have current {now.year} information\n"
                )
                system_content += date_info
                logger.info(f"Added current date to system prompt: {current_date_str}")

                # Also add to context history for multi-turn conversations
                if user_id is not None:
                    date_context = (
                        f"Current date: {current_date_str}. "
                        f"Current time: {current_time}."
                    )
                    self._memory.add_system_context(user_id, date_context)
                    logger.debug(f"Added date context to conversation memory for user {user_id}")

            # Perform web search if enabled and query seems to need it
            web_results = ""
            if self._web_search and self._should_use_web_search(prompt):
                logger.info("Performing web search for query")
                web_results = await self._web_search.search(prompt, count=3)
                if web_results:
                    system_content += f"\n\nWeb search results:\n{web_results}"
                    logger.info("Added web search results to context")

            # Add system message if present
            if system_content:
                messages.append(SystemMessage(role="system", content=system_content))

            # Add conversation history if user_id provided
            conversation_length = 0
            if user_id is not None:
                history_messages = self._memory.get_messages_for_api(user_id)
                messages.extend(history_messages)
                # Estimate conversation length in tokens using standard multiplier
                for msg in history_messages:
                    msg_tokens = len(str(msg.content).split()) * TOKEN_ESTIMATION_MULTIPLIER
                    conversation_length += msg_tokens
                if history_messages:
                    logger.debug(
                        f"Added {len(history_messages)} messages from "
                        f"conversation history for context {user_id}"
                    )

            # Add current user message
            logger.debug(f"Adding current user message to API: {prompt[:200]}...")
            messages.append(UserMessage(role="user", content=prompt))

            # Select appropriate model based on request characteristics
            selected_model = self._model_selector.select_model(
                prompt=prompt,
                conversation_length=int(conversation_length),
                has_images=False,  # Future enhancement: detect images in input
            )
            logger.info(f"Selected model: {selected_model}")

            # Build request kwargs
            request_kwargs = {
                "model": selected_model,
                "messages": messages,
                "max_tokens": self._settings.mistral.max_tokens,
                "temperature": self._settings.mistral.temperature,
            }

            response = await self._client.chat.complete_async(**request_kwargs)

            # Validate response structure
            choices = getattr(response, "choices", None)
            if not choices:
                logger.error("Mistral API returned no choices in the response")
                raise ValueError("Mistral API returned no choices in the response")

            first_choice = choices[0]
            message = getattr(first_choice, "message", None)
            content = getattr(message, "content", None) if message is not None else None

            if content is None:
                logger.error("Mistral API returned no message content in the first choice")
                raise ValueError("Mistral API returned no message content in the first choice")

            if not isinstance(content, str):
                logger.error("Mistral API returned unexpected content type: %r", type(content))
                raise TypeError("Mistral API returned non-string message content")

            # Extract token usage information
            usage = getattr(response, "usage", None)
            input_tokens = 0
            output_tokens = 0
            if usage:
                input_tokens = getattr(usage, "prompt_tokens", 0) or 0
                output_tokens = getattr(usage, "completion_tokens", 0) or 0

            logger.info(
                f"Generated response with {output_tokens} output tokens "
                f"(input: {input_tokens}, total: {input_tokens + output_tokens})"
            )

            return GenerateResponse(
                content=content,
                model=selected_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except (ValueError, TypeError):
            # Re-raise validation errors with their specific messages
            raise
        except Exception:
            # Catch and log any other unexpected errors
            logger.exception("Mistral API call failed")
            raise

    async def generate_stream(
        self, prompt: str, user_id: Optional[int] = None
    ) -> AsyncIterator[tuple[str, str, bool]]:
        """
        Stream response from Mistral model progressively.

        Args:
            prompt: The user's message/question
            user_id: Context ID for conversation history tracking

        Yields:
            Tuples of (chunk_content, accumulated_content, is_final)
            - chunk_content: New text fragment received
            - accumulated_content: Complete text so far
            - is_final: True on the last chunk with final metadata
        """
        try:
            messages = []
            accumulated_content = ""

            # Build system message (same logic as generate)
            system_content = self._settings.mistral.system_prompt

            # Add chain-of-thought reasoning instruction when reasoning mode is active
            reasoning_active = (
                self._settings.mistral.reasoning_mode
                and self._settings.access.reasoning_mode_enabled
            )
            if reasoning_active:
                system_content += REASONING_INSTRUCTION
                logger.info("Reasoning mode active: added CoT instruction to system prompt")

            # Check both config and runtime flags for always_append_date
            always_append = (
                self._settings.mistral.always_append_date
                and self._settings.access.always_append_date_enabled
            )
            if always_append or requires_current_date(prompt):
                now = datetime.now()
                current_date_str = f"{now.day} {RUSSIAN_MONTHS[now.month - 1]} {now.year} года"
                current_time = now.strftime("%H:%M")

                date_info = (
                    f"\n\n[CRITICAL CONTEXT - CURRENT DATE]\n"
                    f"TODAY: {current_date_str} ({now.year})\n"
                    f"CURRENT YEAR: {now.year}\n"
                    f"TIME: {current_time}\n\n"
                    f"IMPORTANT INSTRUCTIONS:\n"
                    f"- Use THIS DATE ({now.year}) for all time-sensitive queries\n"
                    f"- Your training data is from 2024 and earlier — it is OUTDATED\n"
                    f"- When user asks about 'this year' or 'recently', they mean {now.year}\n"
                    f"- Do NOT mention dates from your training period (2023-2024)\n"
                    f"- Answer as if you have current {now.year} information\n"
                )
                system_content += date_info
                logger.info(f"Added current date to system prompt: {current_date_str}")

                if user_id is not None:
                    date_context = (
                        f"Current date: {current_date_str}. Current time: {current_time}."
                    )
                    self._memory.add_system_context(user_id, date_context)
                    logger.debug(
                        f"Added date context to conversation memory for user {user_id}"
                    )

            # Perform web search if enabled
            if self._web_search and self._should_use_web_search(prompt):
                logger.info("Performing web search for query")
                web_results = await self._web_search.search(prompt, count=3)
                if web_results:
                    system_content += f"\n\nWeb search results:\n{web_results}"
                    logger.info("Added web search results to context")

            if system_content:
                messages.append(SystemMessage(role="system", content=system_content))

            # Add conversation history
            conversation_length = 0
            if user_id is not None:
                history_messages = self._memory.get_messages_for_api(user_id)
                messages.extend(history_messages)
                for msg in history_messages:
                    msg_tokens = len(str(msg.content).split()) * TOKEN_ESTIMATION_MULTIPLIER
                    conversation_length += msg_tokens
                if history_messages:
                    logger.debug(
                        f"Added {len(history_messages)} messages from "
                        f"conversation history for context {user_id}"
                    )

            messages.append(UserMessage(role="user", content=prompt))

            # Select appropriate model
            selected_model = self._model_selector.select_model(
                prompt=prompt,
                conversation_length=int(conversation_length),
                has_images=False,
            )
            logger.info(f"Selected model for streaming: {selected_model}")

            # Build request kwargs
            request_kwargs = {
                "model": selected_model,
                "messages": messages,
                "max_tokens": self._settings.mistral.max_tokens,
                "temperature": self._settings.mistral.temperature,
            }

            # Stream the response
            input_tokens = 0
            output_tokens = 0

            stream = await self._client.chat.stream_async(**request_kwargs)

            async for chunk in stream:
                # Extract content delta from chunk
                if hasattr(chunk, "data") and chunk.data:
                    data = chunk.data
                    choices = getattr(data, "choices", None)

                    if choices and len(choices) > 0:
                        delta = getattr(choices[0], "delta", None)
                        if delta:
                            content_delta = getattr(delta, "content", None)
                            if content_delta:
                                accumulated_content += content_delta
                                yield (content_delta, accumulated_content, False)

                    # Extract usage information if present (usually in the last chunk)
                    usage = getattr(data, "usage", None)
                    if usage:
                        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
                        output_tokens = getattr(usage, "completion_tokens", 0) or 0

            # Yield final chunk with metadata
            logger.info(
                f"Streaming completed: {output_tokens} output tokens "
                f"(input: {input_tokens}, total: {input_tokens + output_tokens})"
            )
            yield ("", accumulated_content, True)

        except Exception:
            logger.exception("Mistral streaming API call failed")
            raise

    def _should_use_web_search(self, prompt: str) -> bool:
        """
        Determine if web search should be used for this prompt.

        Uses keywords to detect queries that likely need current information
        or explicit search requests.

        Uses simple substring matching to prioritize recall over precision:
        some false positives are acceptable to ensure explicit search
        requests are not missed and to maintain broad coverage of query
        variations.
        """
        prompt_lower = prompt.lower()

        # Keywords that suggest need for current information or explicit search requests
        search_keywords = [
            # Time-sensitive queries
            "новост",
            "сегодня",
            "сейчас",
            "текущ",
            "последн",
            "актуальн",
            "погода",
            "курс",
            "цена",
            "стоимость",
            "событи",
            "происход",
            "news",
            "today",
            "current",
            "latest",
            "weather",
            "price",
            "когда",
            "where",
            "где",
            "what happened",
            "что случилось",
            # Explicit search requests
            # Using more specific phrases to reduce false positives
            "поиск",
            "поищи",
            "найди",
            "найти",
            "искать",
            "погугли",
            "узнай",
            "посмотри в интернете",
            "посмотри в сети",
            "проверь онлайн",
            "интернет",
            "в сети",
            "онлайн",
            "search",
            "find information",
            "find info",
            "find articles",
            "look up",
            "google",
            "check online",
            "search online",
            "internet",
        ]

        return any(keyword in prompt_lower for keyword in search_keywords)
