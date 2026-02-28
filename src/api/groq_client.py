"""Groq API client — drop-in alternative to MistralClient for load balancing."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Optional

from groq import AsyncGroq

from src.api.mistral_client import GenerateResponse
from src.api.model_selector import ModelSelector
from src.config.settings import AppSettings

logger = logging.getLogger(__name__)


def _map_model(mistral_model: str, settings: AppSettings) -> str:
    """Map a Mistral model name to the appropriate Groq model.

    Uses explicit settings when available, otherwise falls back to the
    configured default Groq model.
    """
    if mistral_model in ("codestral-latest",):
        return settings.groq.code_model
    if mistral_model in ("mistral-large-latest", "mistral-medium-latest"):
        return settings.groq.large_model
    return settings.groq.model


class GroqClient:
    """Async wrapper around the Groq SDK.

    Exposes the same ``generate`` / ``generate_stream`` interface as
    :class:`~src.api.mistral_client.MistralClient` so that the two can be
    used interchangeably by :class:`~src.api.provider_router.ProviderRouter`.
    """

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._client = AsyncGroq(api_key=settings.groq_api_key)
        self._model_selector = ModelSelector(default_model=settings.mistral.model)
        logger.info("GroqClient initialised with default model=%s", settings.groq.model)

    async def generate(
        self,
        prompt: str,
        user_id: Optional[int] = None,
        image_urls: Optional[list[str]] = None,
        *,
        _selected_model: Optional[str] = None,
        _messages: Optional[list[dict[str, str]]] = None,
    ) -> GenerateResponse:
        """Send *prompt* to Groq and return a :class:`GenerateResponse`.

        Parameters ``_selected_model`` and ``_messages`` are internal
        overrides used by :class:`ProviderRouter` to forward the already-
        prepared request from :class:`MistralClient`.
        """
        if _messages is not None:
            messages = _messages
        else:
            messages = [{"role": "user", "content": prompt}]

        if _selected_model is not None:
            groq_model = _map_model(_selected_model, self._settings)
        else:
            selected = self._model_selector.select_model(
                prompt=prompt,
                conversation_length=0,
                has_images=bool(image_urls),
            )
            groq_model = _map_model(selected, self._settings)

        logger.info("Groq request with model=%s", groq_model)

        response = await self._client.chat.completions.create(
            model=groq_model,
            messages=messages,
            max_tokens=self._settings.groq.max_tokens,
            temperature=self._settings.groq.temperature,
        )

        choices = getattr(response, "choices", None)
        if not choices:
            raise ValueError("Groq API returned no choices in the response")

        content = choices[0].message.content
        if content is None:
            raise ValueError("Groq API returned no message content")
        if not isinstance(content, str):
            raise TypeError("Groq API returned non-string message content")

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0 if usage else 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0 if usage else 0

        logger.info(
            "Groq response: %d output tokens (input: %d, total: %d)",
            output_tokens,
            input_tokens,
            input_tokens + output_tokens,
        )

        return GenerateResponse(
            content=content,
            model=groq_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def generate_stream(
        self,
        prompt: str,
        user_id: Optional[int] = None,
        image_urls: Optional[list[str]] = None,
        *,
        _selected_model: Optional[str] = None,
        _messages: Optional[list[dict[str, str]]] = None,
    ) -> AsyncIterator[tuple[str, str, bool, list[str]]]:
        """Stream response from Groq progressively.

        Yields tuples identical to ``MistralClient.generate_stream``.
        """
        if _messages is not None:
            messages = _messages
        else:
            messages = [{"role": "user", "content": prompt}]

        if _selected_model is not None:
            groq_model = _map_model(_selected_model, self._settings)
        else:
            selected = self._model_selector.select_model(
                prompt=prompt,
                conversation_length=0,
                has_images=bool(image_urls),
            )
            groq_model = _map_model(selected, self._settings)

        logger.info("Groq streaming request with model=%s", groq_model)

        stream = await self._client.chat.completions.create(
            model=groq_model,
            messages=messages,
            max_tokens=self._settings.groq.max_tokens,
            temperature=self._settings.groq.temperature,
            stream=True,
        )

        accumulated = ""
        input_tokens = 0
        output_tokens = 0

        async for chunk in stream:
            choices = getattr(chunk, "choices", None)
            if choices:
                delta = getattr(choices[0], "delta", None)
                if delta:
                    text = getattr(delta, "content", None)
                    if text:
                        accumulated += text
                        yield (text, accumulated, False, [])
            usage = getattr(chunk, "x_groq", None)
            if usage:
                u = getattr(usage, "usage", None)
                if u:
                    input_tokens = getattr(u, "prompt_tokens", 0) or 0
                    output_tokens = getattr(u, "completion_tokens", 0) or 0

        logger.info(
            "Groq streaming completed: %d output tokens (input: %d)",
            output_tokens,
            input_tokens,
        )
        yield ("", accumulated, True, [])
