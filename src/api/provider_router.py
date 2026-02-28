"""Provider router — distributes requests between Mistral and Groq.

The router implements round-robin distribution with automatic fallback:
when the primary provider fails (e.g. rate limit), the request is retried
on the secondary provider.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Optional

from src.api.groq_client import GroqClient
from src.api.mistral_client import GenerateResponse, MistralClient
from src.config.settings import AppSettings

logger = logging.getLogger(__name__)

# Providers cycle:  "mistral" → "groq" → "mistral" → …
_PROVIDERS = ("mistral", "groq")


class ProviderRouter:
    """Thin layer that round-robins between Mistral and Groq providers.

    If only one provider has a valid API key, all traffic goes through it.
    When both providers are available, the router alternates requests and
    automatically falls back to the other provider on failure.
    """

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._mistral = MistralClient(settings)
        self._groq: GroqClient | None = None

        if settings.groq.enabled and settings.groq_api_key:
            self._groq = GroqClient(settings)
            logger.info("ProviderRouter: Groq provider enabled — round-robin active")
        else:
            logger.info("ProviderRouter: Groq not configured — Mistral-only mode")

        self._index = 0  # simple round-robin counter

    # Expose internal clients for cases where handler accesses _web_search etc.
    @property
    def mistral(self) -> MistralClient:
        """Return the underlying MistralClient."""
        return self._mistral

    def _next_provider(self) -> str:
        """Return the name of the next provider in the round-robin cycle."""
        if self._groq is None:
            return "mistral"
        provider = _PROVIDERS[self._index % len(_PROVIDERS)]
        self._index += 1
        return provider

    # ------------------------------------------------------------------
    # Public API — mirrors MistralClient.generate / generate_stream
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        user_id: Optional[int] = None,
        image_urls: Optional[list[str]] = None,
    ) -> GenerateResponse:
        """Generate a response using the next available provider.

        On failure the router retries once with the other provider.
        """
        primary = self._next_provider()
        providers = [primary]
        if self._groq is not None:
            fallback = "groq" if primary == "mistral" else "mistral"
            providers.append(fallback)

        last_exc: BaseException | None = None
        for provider_name in providers:
            try:
                if provider_name == "groq" and self._groq is not None:
                    logger.info("ProviderRouter: routing to Groq")
                    return await self._groq.generate(prompt, user_id=user_id, image_urls=image_urls)
                else:
                    logger.info("ProviderRouter: routing to Mistral")
                    return await self._mistral.generate(
                        prompt, user_id=user_id, image_urls=image_urls
                    )
            except Exception as exc:
                logger.warning(
                    "Provider %s failed: %s — trying fallback", provider_name, exc
                )
                last_exc = exc

        # All providers exhausted — re-raise the last error
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No providers available")

    async def generate_stream(
        self,
        prompt: str,
        user_id: Optional[int] = None,
        image_urls: Optional[list[str]] = None,
    ) -> AsyncIterator[tuple[str, str, bool, list[str]]]:
        """Stream a response using the next available provider.

        On failure the router retries once with the other provider.
        """
        primary = self._next_provider()
        providers = [primary]
        if self._groq is not None:
            fallback = "groq" if primary == "mistral" else "mistral"
            providers.append(fallback)

        last_exc: BaseException | None = None
        for provider_name in providers:
            try:
                if provider_name == "groq" and self._groq is not None:
                    logger.info("ProviderRouter: streaming via Groq")
                    async for chunk in self._groq.generate_stream(
                        prompt, user_id=user_id, image_urls=image_urls
                    ):
                        yield chunk
                else:
                    logger.info("ProviderRouter: streaming via Mistral")
                    async for chunk in self._mistral.generate_stream(
                        prompt, user_id=user_id, image_urls=image_urls
                    ):
                        yield chunk
                return  # success — stop iterating providers
            except Exception as exc:
                logger.warning(
                    "Provider %s streaming failed: %s — trying fallback",
                    provider_name,
                    exc,
                )
                last_exc = exc

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No providers available")
