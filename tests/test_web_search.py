"""Tests for the web search client with retry, backoff and fallback logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.api.web_search import (
    _BACKOFF_BASE,
    _MAX_RETRIES,
    _RETRYABLE_STATUS_CODES,
    DEFAULT_SEARXNG_INSTANCES,
    DEFAULT_USER_AGENT,
    SearchProvider,
    SearchResult,
    WebSearchClient,
)

# ---------------------------------------------------------------------------
# Initialisation tests
# ---------------------------------------------------------------------------


def test_default_providers_without_google() -> None:
    """Client without Google keys should have SearXNG + Perplexity + DuckDuckGo providers."""
    client = WebSearchClient()
    assert client.providers == [SearchProvider.SEARXNG, SearchProvider.PERPLEXITY, SearchProvider.DUCKDUCKGO]


def test_default_providers_with_google() -> None:
    """Client with Google keys should have all four providers."""
    client = WebSearchClient(google_api_key="key", google_search_engine_id="cx")
    assert client.providers == [
        SearchProvider.GOOGLE,
        SearchProvider.SEARXNG,
        SearchProvider.PERPLEXITY,
        SearchProvider.DUCKDUCKGO,
    ]


def test_default_searxng_instances() -> None:
    """Default SearXNG instances list should be populated."""
    client = WebSearchClient()
    assert len(client.searxng_instances) == len(DEFAULT_SEARXNG_INSTANCES)
    assert client.searxng_instances[0] == DEFAULT_SEARXNG_INSTANCES[0]


def test_custom_searxng_instances() -> None:
    """Custom instances list should override defaults; primary is prepended."""
    custom = ["https://custom1.example.com", "https://custom2.example.com"]
    client = WebSearchClient(searxng_instances=custom)
    # The default primary instance ("https://searx.be") is prepended automatically.
    assert client.searxng_instances[0] == "https://searx.be"
    assert "https://custom1.example.com" in client.searxng_instances
    assert "https://custom2.example.com" in client.searxng_instances


def test_primary_instance_prepended() -> None:
    """Primary instance should be inserted at the front if not already present."""
    custom = ["https://custom1.example.com"]
    client = WebSearchClient(
        searxng_instance="https://primary.example.com",
        searxng_instances=custom,
    )
    assert client.searxng_instances[0] == "https://primary.example.com"
    assert "https://custom1.example.com" in client.searxng_instances


# ---------------------------------------------------------------------------
# Retry with backoff tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_backoff_succeeds_on_second_attempt() -> None:
    """_retry_with_backoff should retry on a 429 and succeed on the second call."""
    ok_response = httpx.Response(200, request=httpx.Request("GET", "https://x"))

    fail_response = httpx.Response(429, request=httpx.Request("GET", "https://x"))

    call_count = 0

    async def factory():  # noqa: ANN202
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            resp = fail_response
            resp.raise_for_status()  # raises HTTPStatusError
        return ok_response

    with patch("src.api.web_search.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await WebSearchClient._retry_with_backoff(factory, "test-provider")

    assert result.status_code == 200
    assert call_count == 2
    mock_sleep.assert_called_once_with(_BACKOFF_BASE)


@pytest.mark.asyncio
async def test_retry_backoff_raises_after_max_retries() -> None:
    """_retry_with_backoff should raise after exhausting retries."""
    fail_response = httpx.Response(429, request=httpx.Request("GET", "https://x"))

    async def factory():  # noqa: ANN202
        fail_response.raise_for_status()

    with (
        patch("src.api.web_search.asyncio.sleep", new_callable=AsyncMock),
        pytest.raises(httpx.HTTPStatusError),
    ):
        await WebSearchClient._retry_with_backoff(factory, "test-provider")


@pytest.mark.asyncio
async def test_retry_backoff_no_retry_on_non_retryable() -> None:
    """_retry_with_backoff should NOT retry on non-retryable status codes like 403."""
    fail_response = httpx.Response(403, request=httpx.Request("GET", "https://x"))

    call_count = 0

    async def factory():  # noqa: ANN202
        nonlocal call_count
        call_count += 1
        fail_response.raise_for_status()

    with pytest.raises(httpx.HTTPStatusError):
        await WebSearchClient._retry_with_backoff(factory, "test-provider")

    assert call_count == 1  # No retry


# ---------------------------------------------------------------------------
# SearXNG instance fallback tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_searxng_falls_back_on_403() -> None:
    """SearXNG should try the next instance when the first returns 403."""
    client = WebSearchClient(
        searxng_instances=["https://blocked.example.com", "https://ok.example.com"],
    )

    async def mock_instance(instance_url: str, query: str, count: int) -> SearchResult:
        if instance_url == "https://blocked.example.com":
            resp = httpx.Response(403, request=httpx.Request("GET", instance_url))
            raise httpx.HTTPStatusError("Forbidden", request=resp.request, response=resp)
        return SearchResult(
            text="1. Result\nContent\nИсточник: https://example.com",
            urls=["https://example.com"],
        )

    with patch.object(client, "_search_searxng_instance", side_effect=mock_instance):
        result = await client._search_searxng("test query", 3)

    assert "Result" in result.text


@pytest.mark.asyncio
async def test_searxng_all_instances_fail() -> None:
    """SearXNG should raise when all instances return 403."""
    client = WebSearchClient(
        searxng_instances=["https://a.example.com", "https://b.example.com"],
    )

    async def mock_instance(instance_url: str, query: str, count: int) -> SearchResult:
        resp = httpx.Response(403, request=httpx.Request("GET", instance_url))
        raise httpx.HTTPStatusError("Forbidden", request=resp.request, response=resp)

    with (
        patch.object(client, "_search_searxng_instance", side_effect=mock_instance),
        pytest.raises(httpx.HTTPStatusError),
    ):
        await client._search_searxng("test query", 3)


# ---------------------------------------------------------------------------
# DuckDuckGo retry on ratelimit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duckduckgo_retries_on_ratelimit() -> None:
    """DuckDuckGo should retry on ratelimit errors."""
    client = WebSearchClient()
    call_count = 0

    def mock_text(query: str, max_results: int = 3):  # noqa: ANN202, ARG001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Ratelimit 202")
        return [{"title": "T", "body": "B", "href": "https://example.com"}]

    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text = mock_text

    with (
        patch("src.api.web_search.DDGS", return_value=mock_ddgs),
        patch("src.api.web_search.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await client._search_duckduckgo("test", 3)

    assert "T" in result.text
    assert call_count == 2


@pytest.mark.asyncio
async def test_duckduckgo_raises_after_max_ratelimit_retries() -> None:
    """DuckDuckGo should raise after exhausting ratelimit retries."""
    client = WebSearchClient()

    def mock_text(query: str, max_results: int = 3):  # noqa: ANN202, ARG001
        raise Exception("Ratelimit 202")

    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text = mock_text

    with (
        patch("src.api.web_search.DDGS", return_value=mock_ddgs),
        patch("src.api.web_search.asyncio.sleep", new_callable=AsyncMock),
        pytest.raises(Exception, match="Ratelimit"),
    ):
        await client._search_duckduckgo("test", 3)


# ---------------------------------------------------------------------------
# Perplexity provider tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_perplexity_returns_results() -> None:
    """_search_perplexity should parse results from the API response."""
    client = WebSearchClient()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"title": "Perplexity Title", "content": "Some content", "url": "https://perplexity.example.com"},
        ]
    }

    with patch.object(client, "_retry_with_backoff", new_callable=AsyncMock, return_value=mock_response):
        result = await client._search_perplexity("test query", 3)

    assert "Perplexity Title" in result
    assert "Some content" in result
    assert "https://perplexity.example.com" in result


@pytest.mark.asyncio
async def test_search_perplexity_uses_snippet_fallback() -> None:
    """_search_perplexity should fall back to 'snippet' when 'content' is absent."""
    client = WebSearchClient()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"title": "Title", "snippet": "Snippet text", "url": "https://example.com"},
        ]
    }

    with patch.object(client, "_retry_with_backoff", new_callable=AsyncMock, return_value=mock_response):
        result = await client._search_perplexity("test query", 3)

    assert "Snippet text" in result


@pytest.mark.asyncio
async def test_search_perplexity_empty_results() -> None:
    """_search_perplexity should return empty string when no results."""
    client = WebSearchClient()

    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}

    with patch.object(client, "_retry_with_backoff", new_callable=AsyncMock, return_value=mock_response):
        result = await client._search_perplexity("test query", 3)

    assert result == ""


@pytest.mark.asyncio
async def test_search_falls_back_to_perplexity() -> None:
    """search() should fall back to Perplexity when SearXNG fails."""
    client = WebSearchClient()

    async def fail_searxng(query: str, count: int) -> str:
        raise Exception("SearXNG down")

    async def ok_perplexity(query: str, count: int) -> str:
        return "1. Perplexity Result\nContent\nИсточник: https://perplexity.example.com"

    async def fail_ddg(query: str, count: int) -> str:
        raise Exception("DDG down")

    with (
        patch.object(client, "_search_searxng", side_effect=fail_searxng),
        patch.object(client, "_search_perplexity", side_effect=ok_perplexity),
        patch.object(client, "_search_duckduckgo", side_effect=fail_ddg),
    ):
        result = await client.search("test query")

    assert "Perplexity Result" in result


# ---------------------------------------------------------------------------
# Full search() fallback tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_falls_back_to_duckduckgo() -> None:
    """search() should fall back to DuckDuckGo when SearXNG fails."""
    client = WebSearchClient()

    async def fail_searxng(query: str, count: int) -> SearchResult:
        raise Exception("SearXNG down")

    async def ok_ddg(query: str, count: int) -> SearchResult:
        return SearchResult(
            text="1. DDG Result\nContent\nИсточник: https://ddg.example.com",
            urls=["https://ddg.example.com"],
        )

    with (
        patch.object(client, "_search_searxng", side_effect=fail_searxng),
        patch.object(client, "_search_duckduckgo", side_effect=ok_ddg),
    ):
        result = await client.search("test query")

    assert "DDG Result" in result.text


@pytest.mark.asyncio
async def test_search_returns_empty_when_all_fail() -> None:
    """search() should return empty string when all providers fail."""
    client = WebSearchClient()

    async def fail(query: str, count: int) -> SearchResult:
        raise Exception("Provider down")

    with (
        patch.object(client, "_search_searxng", side_effect=fail),
        patch.object(client, "_search_perplexity", side_effect=fail),
        patch.object(client, "_search_duckduckgo", side_effect=fail),
    ):
        result = await client.search("test query")

    assert result.text == ""
    assert result.urls == []


# ---------------------------------------------------------------------------
# User-Agent header test
# ---------------------------------------------------------------------------


def test_default_user_agent_is_realistic() -> None:
    """DEFAULT_USER_AGENT should look like a real browser."""
    assert "Mozilla" in DEFAULT_USER_AGENT
    assert "Chrome" in DEFAULT_USER_AGENT


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


def test_retryable_status_codes() -> None:
    """Retryable codes should include 429 and 503."""
    assert 429 in _RETRYABLE_STATUS_CODES
    assert 503 in _RETRYABLE_STATUS_CODES


def test_max_retries_is_positive() -> None:
    assert _MAX_RETRIES >= 1


def test_backoff_base_is_positive() -> None:
    assert _BACKOFF_BASE > 0


# ---------------------------------------------------------------------------
# SearchResult tests
# ---------------------------------------------------------------------------


def test_search_result_truthy_when_text_present() -> None:
    """SearchResult should be truthy when text is non-empty."""
    result = SearchResult(text="some results", urls=["https://example.com"])
    assert result


def test_search_result_falsy_when_text_empty() -> None:
    """SearchResult should be falsy when text is empty."""
    result = SearchResult(text="", urls=[])
    assert not result


def test_search_result_urls_populated() -> None:
    """SearchResult should carry source URLs from search results."""
    result = SearchResult(
        text="1. Title\nContent\nИсточник: https://a.com",
        urls=["https://a.com", "https://b.com"],
    )
    assert result.urls == ["https://a.com", "https://b.com"]


@pytest.mark.asyncio
async def test_search_returns_urls_on_fallback() -> None:
    """search() should carry URLs through provider fallback."""
    client = WebSearchClient()

    async def fail_searxng(query: str, count: int) -> SearchResult:
        raise Exception("SearXNG down")

    async def ok_ddg(query: str, count: int) -> SearchResult:
        return SearchResult(
            text="1. Result\nBody\nИсточник: https://ddg.example.com",
            urls=["https://ddg.example.com"],
        )

    with (
        patch.object(client, "_search_searxng", side_effect=fail_searxng),
        patch.object(client, "_search_duckduckgo", side_effect=ok_ddg),
    ):
        result = await client.search("test query")

    assert result.urls == ["https://ddg.example.com"]
