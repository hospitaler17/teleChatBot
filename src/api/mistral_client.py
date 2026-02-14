"""Mistral API client."""

from __future__ import annotations

import logging

from mistralai import Mistral
from mistralai.models import SystemMessage, UserMessage

from src.config.settings import AppSettings

logger = logging.getLogger(__name__)


class MistralClient:
    """Thin wrapper around the Mistral AI SDK."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._client = Mistral(api_key=settings.mistral_api_key)
        logger.info("MistralClient initialised with model=%s", settings.mistral.model)

    async def generate(self, prompt: str) -> str:
        """Send *prompt* to the Mistral model and return the text response."""
        try:
            messages = []
            # Add system message if configured
            if self._settings.mistral.system_prompt:
                messages.append(
                    SystemMessage(role="system", content=self._settings.mistral.system_prompt)
                )
            # Add user message
            messages.append(
                UserMessage(role="user", content=prompt)
            )

            response = await self._client.chat.complete_async(
                model=self._settings.mistral.model,
                messages=messages,
                max_tokens=self._settings.mistral.max_tokens,
                temperature=self._settings.mistral.temperature,
            )

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
