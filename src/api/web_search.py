"""Web search with multiple providers: Google, SearXNG, DuckDuckGo."""

from __future__ import annotations

import asyncio
import logging
import typing
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import httpx
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

# Default SearXNG instances to try in order when the primary one fails.
DEFAULT_SEARXNG_INSTANCES = [
    "https://searx.be",
    "https://search.sapti.me",
    "https://searxng.ch",
    "https://search.bus-hit.me",
    "https://searx.envs.net",
    "https://searx.neocat.cc",
    "https://searx.space",
]

# Realistic browser User-Agent to reduce blocks from public instances.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# HTTP status codes considered retryable (temporary failures).
_RETRYABLE_STATUS_CODES = {429, 503, 502}

# Maximum number of retry attempts for a single provider call.
_MAX_RETRIES = 2

# Base delay (seconds) for exponential backoff between retries.
_BACKOFF_BASE = 1.0


@dataclass
class SearchResult:
    """Structured web search result containing formatted text and source URLs."""

    text: str
    urls: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        """Return True when search produced non-empty text."""
        return bool(self.text)


class SearchProvider(Enum):
    """Available search providers."""

    GOOGLE = "google"
    SEARXNG = "searxng"
    PERPLEXITY = "perplexity"
    DUCKDUCKGO = "duckduckgo"


class WebSearchClient:
    """Client for performing web searches using multiple providers with fallback."""

    def __init__(
        self,
        google_api_key: Optional[str] = None,
        google_search_engine_id: Optional[str] = None,
        searxng_instance: str = "https://searx.be",
        searxng_instances: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize web search client.

        Args:
            google_api_key: Google Custom Search API key (optional)
            google_search_engine_id: Google Custom Search Engine ID (optional)
            searxng_instance: Primary SearXNG public instance URL
            searxng_instances: Additional SearXNG instances for fallback
        """
        self.google_api_key = google_api_key
        self.google_search_engine_id = google_search_engine_id

        # Build the ordered list of SearXNG instances to try.
        if searxng_instances is not None:
            self.searxng_instances = list(searxng_instances)
        else:
            self.searxng_instances = list(DEFAULT_SEARXNG_INSTANCES)
        # Ensure the primary instance is tried first.
        if searxng_instance not in self.searxng_instances:
            self.searxng_instances.insert(0, searxng_instance)

        # Determine available providers
        self.providers: list[SearchProvider] = []
        if google_api_key and google_search_engine_id:
            self.providers.append(SearchProvider.GOOGLE)
        self.providers.extend(
            [SearchProvider.SEARXNG, SearchProvider.PERPLEXITY, SearchProvider.DUCKDUCKGO]
        )

        logger.info(f"Web search initialized with providers: {[p.value for p in self.providers]}")

    async def search(self, query: str, count: int = 3) -> SearchResult:
        """
        Perform web search using available providers with fallback.

        Args:
            query: Search query
            count: Number of results to return (default: 3)

        Returns:
            SearchResult with formatted text and source URLs
        """
        errors: list[str] = []

        for provider in self.providers:
            try:
                if provider == SearchProvider.GOOGLE:
                    results = await self._search_google(query, count)
                elif provider == SearchProvider.SEARXNG:
                    results = await self._search_searxng(query, count)
                elif provider == SearchProvider.PERPLEXITY:
                    results = await self._search_perplexity(query, count)
                else:  # DUCKDUCKGO
                    results = await self._search_duckduckgo(query, count)

                if results:
                    logger.info(f"Successfully got results from {provider.value}")
                    return results

            except Exception as e:
                error_detail = f"{provider.value}: {e}"
                errors.append(error_detail)
                logger.warning(f"Search failed for {error_detail}")
                continue

        logger.error(
            "All search providers failed. Errors: %s",
            "; ".join(errors) if errors else "no providers available",
        )
        return SearchResult(text="", urls=[])

    @staticmethod
    async def _retry_with_backoff(
        coro_factory: typing.Callable[[], typing.Awaitable[httpx.Response]],
        provider_name: str,
        max_retries: int = _MAX_RETRIES,
    ) -> httpx.Response:
        """Execute an HTTP request with exponential backoff on retryable errors.

        Args:
            coro_factory: A zero-argument callable that returns a fresh awaitable
                          (e.g. ``lambda: client.get(...)``).
            provider_name: Name used in log messages.
            max_retries: Maximum number of retry attempts.

        Returns:
            The successful ``httpx.Response``.

        Raises:
            httpx.HTTPStatusError: If the request fails after all retries.
        """
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = await coro_factory()
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                last_exc = exc
                snippet = exc.response.text[:200] if exc.response.text else ""
                logger.warning(
                    "%s returned HTTP %d on attempt %d/%d. Response snippet: %s",
                    provider_name,
                    status,
                    attempt + 1,
                    max_retries + 1,
                    snippet,
                )
                if status in _RETRYABLE_STATUS_CODES and attempt < max_retries:
                    delay = _BACKOFF_BASE * (2**attempt)
                    logger.info(
                        "Retrying %s in %.1f s (attempt %d/%d)",
                        provider_name,
                        delay,
                        attempt + 2,
                        max_retries + 1,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise
        # Should not be reached, but keeps mypy happy.
        raise last_exc  # type: ignore[misc]

    async def _search_google(self, query: str, count: int) -> SearchResult:
        """Search using Google Custom Search API."""
        try:
            async with httpx.AsyncClient() as client:
                url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    "key": self.google_api_key,
                    "cx": self.google_search_engine_id,
                    "q": query,
                    "num": min(count, 10),  # Google allows max 10
                }

                response = await self._retry_with_backoff(
                    lambda: client.get(url, params=params, timeout=10.0),
                    provider_name="Google",
                )
                data = response.json()

                items = data.get("items", [])
                if not items:
                    return SearchResult(text="", urls=[])

                results = []
                urls = []
                for idx, item in enumerate(items[:count], 1):
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    link = item.get("link", "")
                    results.append(f"{idx}. {title}\n{snippet}\nИсточник: {link}")
                    if link:
                        urls.append(link)

                if results:
                    logger.info(f"Google returned {len(results)} results")
                    return SearchResult(text="\n\n".join(results), urls=urls)
                return SearchResult(text="", urls=[])

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("Google API rate limit reached")
            raise
        except Exception as e:
            logger.error(f"Google search error: {e}")
            raise

    async def _search_searxng(self, query: str, count: int) -> SearchResult:
        """Search using SearXNG public instances with instance-level fallback."""
        last_error: Exception | None = None

        for instance_url in self.searxng_instances:
            try:
                result = await self._search_searxng_instance(instance_url, query, count)
                if result:
                    return result
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                snippet = e.response.text[:200] if e.response.text else ""
                logger.warning(
                    "SearXNG instance %s returned HTTP %d. "
                    "User-Agent: %s. Response snippet: %s",
                    instance_url,
                    status,
                    DEFAULT_USER_AGENT[:60],
                    snippet,
                )
                last_error = e
                if status == 403:
                    logger.info(
                        "SearXNG instance %s blocked (403), trying next instance",
                        instance_url,
                    )
                    continue
                raise
            except Exception as e:
                logger.error(f"SearXNG search error for {instance_url}: {e}")
                last_error = e
                continue

        if last_error is not None:
            raise last_error
        return SearchResult(text="", urls=[])

    async def _search_searxng_instance(
        self, instance_url: str, query: str, count: int
    ) -> SearchResult:
        """Search a single SearXNG instance (with retry for retryable codes)."""
        async with httpx.AsyncClient() as client:
            url = f"{instance_url}/search"
            params = {"q": query, "format": "json", "language": "ru", "safesearch": "0"}
            headers = {"User-Agent": DEFAULT_USER_AGENT}

            response = await self._retry_with_backoff(
                lambda: client.get(url, params=params, timeout=15.0, headers=headers),
                provider_name=f"SearXNG({instance_url})",
            )
            data = response.json()

            results_data = data.get("results", [])
            if not results_data:
                return SearchResult(text="", urls=[])

            results = []
            urls = []
            for idx, item in enumerate(results_data[:count], 1):
                title = item.get("title", "")
                content = item.get("content", "")
                url_link = item.get("url", "")
                results.append(f"{idx}. {title}\n{content}\nИсточник: {url_link}")
                if url_link:
                    urls.append(url_link)

            if results:
                logger.info(
                    f"SearXNG ({instance_url}) returned {len(results)} results"
                )
                return SearchResult(text="\n\n".join(results), urls=urls)
            return SearchResult(text="", urls=[])

    async def _search_perplexity(self, query: str, count: int) -> SearchResult:
        """Search using the Perplexity public search API."""
        try:
            async with httpx.AsyncClient() as client:
                url = "https://api.perplexity.ai/search"
                params = {"q": query}
                headers = {"User-Agent": DEFAULT_USER_AGENT}

                response = await self._retry_with_backoff(
                    lambda: client.get(url, params=params, timeout=15.0, headers=headers),
                    provider_name="Perplexity",
                )
                data = response.json()

                results_data = data.get("results", [])
                if not results_data:
                    return SearchResult(text="", urls=[])

                results = []
                urls = []
                for idx, item in enumerate(results_data[:count], 1):
                    title = item.get("title", "")
                    content = item.get("content", item.get("snippet", ""))
                    url_link = item.get("url", "")
                    results.append(f"{idx}. {title}\n{content}\nИсточник: {url_link}")
                    if url_link:
                        urls.append(url_link)

                if results:
                    logger.info(f"Perplexity returned {len(results)} results")
                    return SearchResult(text="\n\n".join(results), urls=urls)
                return SearchResult(text="", urls=[])

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("Perplexity API rate limit reached")
            raise
        except Exception as e:
            logger.error(f"Perplexity search error: {e}")
            raise

    async def _search_duckduckgo(self, query: str, count: int) -> SearchResult:
        """Search using DuckDuckGo with retry on ratelimit errors."""
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                with DDGS() as ddgs:
                    results_list = list(ddgs.text(query, max_results=count))

                    results = []
                    urls = []
                    for idx, result in enumerate(results_list[:count], 1):
                        title = result.get("title", "")
                        body = result.get("body", "")
                        url = result.get("href", "")
                        results.append(f"{idx}. {title}\n{body}\nИсточник: {url}")
                        if url:
                            urls.append(url)

                    if results:
                        logger.info(f"DuckDuckGo returned {len(results)} results")
                        return SearchResult(text="\n\n".join(results), urls=urls)
                    return SearchResult(text="", urls=[])

            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                is_ratelimit = "ratelimit" in error_str or "202" in error_str
                logger.warning(
                    "DuckDuckGo error on attempt %d/%d: %s (ratelimit=%s)",
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    e,
                    is_ratelimit,
                )
                if is_ratelimit and attempt < _MAX_RETRIES:
                    delay = _BACKOFF_BASE * (2**attempt)
                    logger.info(
                        "Retrying DuckDuckGo in %.1f s (attempt %d/%d)",
                        delay,
                        attempt + 2,
                        _MAX_RETRIES + 1,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        if last_error is not None:
            raise last_error
        return SearchResult(text="", urls=[])
