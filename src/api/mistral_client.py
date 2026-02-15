"""Mistral API client."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from mistralai import Mistral
from mistralai.models import SystemMessage, UserMessage

from src.api.conversation_memory import ConversationMemory
from src.api.model_selector import TOKEN_ESTIMATION_MULTIPLIER, ModelSelector
from src.api.web_search import WebSearchClient
from src.config.settings import AppSettings

logger = logging.getLogger(__name__)


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

    async def generate(self, prompt: str, user_id: Optional[int] = None) -> str:
        """
        Send *prompt* to the Mistral model and return the text response.

        Args:
            prompt: The user's message/question
            user_id: Context ID for conversation history tracking
                     (user_id for private chats, chat_id for groups)

        Returns:
            The model's text response
        """
        try:
            messages = []

            # Build system message with current date
            system_content = self._settings.mistral.system_prompt
            current_date = datetime.now().strftime("%d.%m.%Y")
            current_datetime = datetime.now().strftime("%d.%m.%Y %H:%M")
            date_info = (
                f"\\n\\nТекущая дата: {current_date}. Текущие дата и время: {current_datetime}."
            )
            system_content = (system_content + date_info) if system_content else date_info.strip()

            # Perform web search if enabled and query seems to need it
            web_results = ""
            if self._web_search and self._should_use_web_search(prompt):
                logger.info("Performing web search for query")
                web_results = await self._web_search.search(prompt, count=3)
                if web_results:
                    system_content += f"\\n\\nРезультаты поиска в интернете:\\n{web_results}"
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

            return content
        except (ValueError, TypeError):
            # Re-raise validation errors with their specific messages
            raise
        except Exception:
            # Catch and log any other unexpected errors
            logger.exception("Mistral API call failed")
            raise

    def _should_use_web_search(self, prompt: str) -> bool:
        """
        Determine if web search should be used for this prompt.

        Uses keywords to detect queries that likely need current information.
        """
        prompt_lower = prompt.lower()

        # Keywords that suggest need for current information
        search_keywords = [
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
        ]

        return any(keyword in prompt_lower for keyword in search_keywords)
