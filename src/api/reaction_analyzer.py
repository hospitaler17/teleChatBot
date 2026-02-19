"""Sentiment analysis for automatic message reactions."""

from __future__ import annotations

import logging
import random

from mistralai import Mistral
from mistralai.models import SystemMessage, UserMessage

from src.config.settings import AppSettings

logger = logging.getLogger(__name__)


class ReactionAnalyzer:
    """Analyzes message sentiment and suggests reactions."""

    def __init__(self, settings: AppSettings) -> None:
        """Initialize reaction analyzer.

        Args:
            settings: Application settings containing reaction configuration
                and the Mistral API key.
        """
        self._settings = settings
        self._client = Mistral(api_key=settings.mistral_api_key)

    def should_analyze(self, text: str) -> bool:
        """Determine if a message should be analyzed for reactions.

        Args:
            text: The message text to check

        Returns:
            True if the message meets criteria and probability check passes
        """
        # Check if reactions are enabled
        if not self._settings.reactions.enabled:
            return False

        # Check runtime toggle
        if not self._settings.access.reactions_enabled:
            return False

        # Count words in message
        word_count = len(text.split())
        if word_count < self._settings.reactions.min_words:
            logger.debug(
                f"Message has {word_count} words, below threshold of "
                f"{self._settings.reactions.min_words}"
            )
            return False

        # Check probability
        if random.random() >= self._settings.reactions.probability:
            logger.debug("Message skipped due to probability threshold")
            return False

        return True

    async def analyze_mood(self, text: str) -> str | None:
        """Analyze the mood/sentiment of a message.

        Args:
            text: The message text to analyze

        Returns:
            The detected mood as a string, or None if analysis fails
        """
        try:
            messages = [
                SystemMessage(
                    role="system",
                    content=self._settings.reactions.system_prompt,
                ),
                UserMessage(role="user", content=text),
            ]

            response = await self._client.chat.complete_async(
                model=self._settings.reactions.model,
                messages=messages,
                max_tokens=10,  # We only need one word
                temperature=0.3,  # Lower temperature for more consistent results
            )

            # Extract the mood from response
            choices = getattr(response, "choices", None)
            if not choices:
                logger.warning("Mood analysis returned no choices")
                return None

            first_choice = choices[0]
            message = getattr(first_choice, "message", None)
            content = getattr(message, "content", None) if message is not None else None

            if not content:
                logger.warning("Mood analysis returned no content")
                return None

            # Extract the mood word and normalize
            mood = content.strip().lower()
            logger.info(f"Detected mood: {mood}")
            return mood

        except Exception:
            logger.exception("Failed to analyze mood")
            return None

    def get_reaction_emoji(self, mood: str) -> str | None:
        """Get the emoji reaction for a given mood.

        Args:
            mood: The mood string (e.g., "positive", "funny")

        Returns:
            The emoji string, or None if mood is not recognized
        """
        return self._settings.reactions.moods.get(mood.lower())
