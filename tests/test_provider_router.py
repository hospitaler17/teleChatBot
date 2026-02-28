"""Tests for the ProviderRouter — round-robin with fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.mistral_client import GenerateResponse
from src.api.provider_router import ProviderRouter
from src.config.settings import AppSettings, GroqSettings, MistralSettings


def _make_settings(groq_enabled: bool = False) -> AppSettings:
    return AppSettings(
        mistral_api_key="fake-mistral-key",
        groq_api_key="fake-groq-key" if groq_enabled else "",
        mistral=MistralSettings(model="mistral-small-latest"),
        groq=GroqSettings(enabled=groq_enabled),
    )


_RESPONSE = GenerateResponse(
    content="ok", model="test-model", input_tokens=1, output_tokens=2
)


# ------------------------------------------------------------------
# Mistral-only mode (Groq disabled)
# ------------------------------------------------------------------


@patch("src.api.provider_router.GroqClient")
@patch("src.api.provider_router.MistralClient")
def test_mistral_only_mode(mock_mistral_cls: MagicMock, mock_groq_cls: MagicMock) -> None:
    """When Groq is disabled, GroqClient should NOT be created."""
    settings = _make_settings(groq_enabled=False)
    router = ProviderRouter(settings)
    assert router._groq is None
    mock_groq_cls.assert_not_called()


@patch("src.api.provider_router.GroqClient")
@patch("src.api.provider_router.MistralClient")
@pytest.mark.asyncio
async def test_mistral_only_generate(
    mock_mistral_cls: MagicMock, mock_groq_cls: MagicMock
) -> None:
    """When Groq is disabled, generate() should always use Mistral."""
    settings = _make_settings(groq_enabled=False)
    mock_instance = MagicMock()
    mock_instance.generate = AsyncMock(return_value=_RESPONSE)
    mock_mistral_cls.return_value = mock_instance
    router = ProviderRouter(settings)

    result = await router.generate("hello")
    assert result.content == "ok"
    mock_instance.generate.assert_awaited_once()


# ------------------------------------------------------------------
# Dual-provider mode (round-robin)
# ------------------------------------------------------------------


@patch("src.api.provider_router.GroqClient")
@patch("src.api.provider_router.MistralClient")
def test_dual_mode_groq_created(
    mock_mistral_cls: MagicMock, mock_groq_cls: MagicMock
) -> None:
    """When Groq is enabled with an API key, GroqClient should be created."""
    settings = _make_settings(groq_enabled=True)
    router = ProviderRouter(settings)
    assert router._groq is not None
    mock_groq_cls.assert_called_once()


@patch("src.api.provider_router.GroqClient")
@patch("src.api.provider_router.MistralClient")
@pytest.mark.asyncio
async def test_round_robin_alternation(
    mock_mistral_cls: MagicMock, mock_groq_cls: MagicMock
) -> None:
    """Requests should alternate between Mistral and Groq."""
    settings = _make_settings(groq_enabled=True)
    mistral_inst = MagicMock()
    groq_inst = MagicMock()
    mistral_resp = GenerateResponse(content="mistral", model="m", input_tokens=0, output_tokens=0)
    groq_resp = GenerateResponse(content="groq", model="g", input_tokens=0, output_tokens=0)
    mistral_inst.generate = AsyncMock(return_value=mistral_resp)
    groq_inst.generate = AsyncMock(return_value=groq_resp)
    mock_mistral_cls.return_value = mistral_inst
    mock_groq_cls.return_value = groq_inst

    router = ProviderRouter(settings)

    r1 = await router.generate("first")
    r2 = await router.generate("second")

    # Should get one from each provider
    providers_used = {r1.content, r2.content}
    assert providers_used == {"mistral", "groq"}


# ------------------------------------------------------------------
# Fallback on failure
# ------------------------------------------------------------------


@patch("src.api.provider_router.GroqClient")
@patch("src.api.provider_router.MistralClient")
@pytest.mark.asyncio
async def test_fallback_on_primary_failure(
    mock_mistral_cls: MagicMock, mock_groq_cls: MagicMock
) -> None:
    """When the primary provider fails, the fallback should be used."""
    settings = _make_settings(groq_enabled=True)
    mistral_inst = MagicMock()
    groq_inst = MagicMock()
    mistral_inst.generate = AsyncMock(side_effect=RuntimeError("rate limit"))
    groq_resp = GenerateResponse(content="groq-ok", model="g", input_tokens=0, output_tokens=0)
    groq_inst.generate = AsyncMock(return_value=groq_resp)
    mock_mistral_cls.return_value = mistral_inst
    mock_groq_cls.return_value = groq_inst

    router = ProviderRouter(settings)
    # Force mistral first
    router._index = 0

    result = await router.generate("test")
    assert result.content == "groq-ok"


@patch("src.api.provider_router.GroqClient")
@patch("src.api.provider_router.MistralClient")
@pytest.mark.asyncio
async def test_all_providers_fail_raises(
    mock_mistral_cls: MagicMock, mock_groq_cls: MagicMock
) -> None:
    """When all providers fail, the last exception should be raised."""
    settings = _make_settings(groq_enabled=True)
    mistral_inst = MagicMock()
    groq_inst = MagicMock()
    mistral_inst.generate = AsyncMock(side_effect=RuntimeError("mistral down"))
    groq_inst.generate = AsyncMock(side_effect=RuntimeError("groq down"))
    mock_mistral_cls.return_value = mistral_inst
    mock_groq_cls.return_value = groq_inst

    router = ProviderRouter(settings)

    with pytest.raises(RuntimeError, match="groq down|mistral down"):
        await router.generate("test")
