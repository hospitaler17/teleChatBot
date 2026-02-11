"""Google Gemma API client."""

from __future__ import annotations

import logging

import google.generativeai as genai

from src.config.settings import AppSettings

logger = logging.getLogger(__name__)


class GemmaClient:
    """Thin wrapper around the Google Generative AI SDK for Gemma models."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        genai.configure(api_key=settings.google_api_key)
        self._model = genai.GenerativeModel(
            model_name=settings.gemma.model,
            generation_config=genai.GenerationConfig(
                max_output_tokens=settings.gemma.max_output_tokens,
                temperature=settings.gemma.temperature,
            ),
        )
        logger.info("GemmaClient initialised with model=%s", settings.gemma.model)

    async def generate(self, prompt: str) -> str:
        """Send *prompt* to the Gemma model and return the text response."""
        try:
            response = await self._model.generate_content_async(prompt)
            return response.text
        except Exception:
            logger.exception("Gemma API call failed")
            raise
