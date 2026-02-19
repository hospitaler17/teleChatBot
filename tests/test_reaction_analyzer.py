"""Tests for the ReactionAnalyzer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.reaction_analyzer import ReactionAnalyzer
from src.config.settings import AppSettings, ReactionSettings


@pytest.fixture
def settings() -> AppSettings:
    """Create test settings with reactions enabled."""
    return AppSettings(
        mistral_api_key="fake-key",
        reactions=ReactionSettings(
            enabled=True,
            model="mistral-small-latest",
            probability=1.0,  # Always analyze for testing
            min_words=3,
            moods={
                "positive": "👍",
                "negative": "👎",
                "funny": "😄",
            },
        ),
    )


@pytest.fixture
def disabled_settings() -> AppSettings:
    """Create test settings with reactions disabled."""
    return AppSettings(
        mistral_api_key="fake-key",
        reactions=ReactionSettings(
            enabled=False,
            probability=1.0,
            min_words=3,
        ),
    )


@patch("src.api.reaction_analyzer.Mistral")
def test_analyzer_init(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """ReactionAnalyzer should initialize with Mistral client."""
    ReactionAnalyzer(settings)
    mock_mistral.assert_called_once_with(api_key="fake-key")


def test_should_analyze_disabled(disabled_settings: AppSettings) -> None:
    """should_analyze() returns False when reactions are disabled."""
    analyzer = ReactionAnalyzer(disabled_settings)
    assert not analyzer.should_analyze("This is a test message")


def test_should_analyze_runtime_disabled(settings: AppSettings) -> None:
    """should_analyze() returns False when reactions_enabled is False at runtime."""
    settings.access.reactions_enabled = False
    analyzer = ReactionAnalyzer(settings)
    assert not analyzer.should_analyze("This is a test message")


def test_should_analyze_too_few_words(settings: AppSettings) -> None:
    """should_analyze() returns False when message has too few words."""
    analyzer = ReactionAnalyzer(settings)
    assert not analyzer.should_analyze("Hi")  # 1 word < 3


def test_should_analyze_enough_words(settings: AppSettings) -> None:
    """should_analyze() returns True when message meets all criteria."""
    analyzer = ReactionAnalyzer(settings)
    # Settings have probability=1.0, so this should always return True
    assert analyzer.should_analyze("This is a test message")


@patch("src.api.reaction_analyzer.random.random")
def test_should_analyze_probability(mock_random: MagicMock, settings: AppSettings) -> None:
    """should_analyze() respects probability threshold."""
    settings.reactions.probability = 0.3
    analyzer = ReactionAnalyzer(settings)

    # Mock random to return value above threshold (>= 0.3)
    mock_random.return_value = 0.5  # >= 0.3, should NOT analyze
    assert not analyzer.should_analyze("This is a test message")

    # Mock random to return value below threshold (< 0.3)
    mock_random.return_value = 0.2  # < 0.3, should analyze
    assert analyzer.should_analyze("This is a test message")


@patch("src.api.reaction_analyzer.random.random")
def test_should_analyze_probability_edge_cases(
    mock_random: MagicMock, settings: AppSettings
) -> None:
    """should_analyze() handles edge cases: 0.0 = never, 1.0 = always."""
    analyzer = ReactionAnalyzer(settings)

    # Test probability = 0.0 should never analyze
    settings.reactions.probability = 0.0
    mock_random.return_value = 0.0  # Even at 0.0, should not analyze
    assert not analyzer.should_analyze("This is a test message")

    # Test probability = 1.0 should always analyze
    settings.reactions.probability = 1.0
    mock_random.return_value = 0.0  # Any value < 1.0 should analyze
    assert analyzer.should_analyze("This is a test message")
    mock_random.return_value = 0.999  # Still < 1.0, should analyze
    assert analyzer.should_analyze("This is a test message")


@patch("src.api.reaction_analyzer.Mistral")
@pytest.mark.asyncio
async def test_analyze_mood_success(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """analyze_mood() should return mood string from API response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()

    # Setup mock response chain
    mock_message.content = "positive"
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_client.aclose = AsyncMock()
    mock_mistral.return_value = mock_client

    analyzer = ReactionAnalyzer(settings)
    mood = await analyzer.analyze_mood("This is great!")

    assert mood == "positive"
    mock_client.chat.complete_async.assert_called_once()


@patch("src.api.reaction_analyzer.Mistral")
@pytest.mark.asyncio
async def test_analyze_mood_no_choices(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """analyze_mood() should return None when API returns no choices."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = None
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_client.aclose = AsyncMock()
    mock_mistral.return_value = mock_client

    analyzer = ReactionAnalyzer(settings)
    mood = await analyzer.analyze_mood("Test message")

    assert mood is None


@patch("src.api.reaction_analyzer.Mistral")
@pytest.mark.asyncio
async def test_analyze_mood_exception(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """analyze_mood() should return None on API exception."""
    mock_client = MagicMock()
    mock_client.chat.complete_async = AsyncMock(side_effect=Exception("API Error"))
    mock_mistral.return_value = mock_client

    analyzer = ReactionAnalyzer(settings)
    mood = await analyzer.analyze_mood("Test message")

    assert mood is None


def test_get_reaction_emoji_known_mood(settings: AppSettings) -> None:
    """get_reaction_emoji() should return emoji for known mood."""
    analyzer = ReactionAnalyzer(settings)
    assert analyzer.get_reaction_emoji("positive") == "👍"
    assert analyzer.get_reaction_emoji("negative") == "👎"
    assert analyzer.get_reaction_emoji("funny") == "😄"


def test_get_reaction_emoji_unknown_mood(settings: AppSettings) -> None:
    """get_reaction_emoji() should return None for unknown mood."""
    analyzer = ReactionAnalyzer(settings)
    assert analyzer.get_reaction_emoji("unknown") is None


def test_get_reaction_emoji_case_insensitive(settings: AppSettings) -> None:
    """get_reaction_emoji() should be case insensitive."""
    analyzer = ReactionAnalyzer(settings)
    assert analyzer.get_reaction_emoji("POSITIVE") == "👍"
    assert analyzer.get_reaction_emoji("Positive") == "👍"
