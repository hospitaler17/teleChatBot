"""Mistral API client."""

from __future__ import annotations

import logging

from mistralai import Mistral

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
            response = await self._client.chat.complete_async(
                model=self._settings.mistral.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self._settings.mistral.max_tokens,
                temperature=self._settings.mistral.temperature,
            )
            return response.choices[0].message.content
        except Exception:
            logger.exception("Mistral API call failed")
            raise
