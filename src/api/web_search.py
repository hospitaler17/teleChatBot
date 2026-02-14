"""Web search with multiple providers: Google, SearXNG, DuckDuckGo."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

import httpx
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


class SearchProvider(Enum):
    """Available search providers."""

    GOOGLE = "google"
    SEARXNG = "searxng"
    DUCKDUCKGO = "duckduckgo"


class WebSearchClient:
    """Client for performing web searches using multiple providers with fallback."""

    def __init__(
        self,
        google_api_key: Optional[str] = None,
        google_search_engine_id: Optional[str] = None,
        searxng_instance: str = "https://searx.be",
    ) -> None:
        """
        Initialize web search client.

        Args:
            google_api_key: Google Custom Search API key (optional)
            google_search_engine_id: Google Custom Search Engine ID (optional)
            searxng_instance: SearXNG public instance URL
        """
        self.google_api_key = google_api_key
        self.google_search_engine_id = google_search_engine_id
        self.searxng_instance = searxng_instance

        # Determine available providers
        self.providers = []
        if google_api_key and google_search_engine_id:
            self.providers.append(SearchProvider.GOOGLE)
        self.providers.extend([SearchProvider.SEARXNG, SearchProvider.DUCKDUCKGO])

        logger.info(f"Web search initialized with providers: {[p.value for p in self.providers]}")

    async def search(self, query: str, count: int = 3) -> str:
        """
        Perform web search using available providers with fallback.

        Args:
            query: Search query
            count: Number of results to return (default: 3)

        Returns:
            Formatted search results as string
        """
        for provider in self.providers:
            try:
                if provider == SearchProvider.GOOGLE:
                    results = await self._search_google(query, count)
                elif provider == SearchProvider.SEARXNG:
                    results = await self._search_searxng(query, count)
                else:  # DUCKDUCKGO
                    results = await self._search_duckduckgo(query, count)

                if results:
                    logger.info(f"Successfully got results from {provider.value}")
                    return results

            except Exception as e:
                logger.warning(f"Search failed for {provider.value}: {e}")
                continue

        logger.error("All search providers failed")
        return ""

    async def _search_google(self, query: str, count: int) -> str:
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

                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

                items = data.get("items", [])
                if not items:
                    return ""

                results = []
                for idx, item in enumerate(items[:count], 1):
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    link = item.get("link", "")
                    results.append(f"{idx}. {title}\n{snippet}\nИсточник: {link}")

                if results:
                    logger.info(f"Google returned {len(results)} results")
                    return "\n\n".join(results)
                return ""

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("Google API rate limit reached")
            raise
        except Exception as e:
            logger.error(f"Google search error: {e}")
            raise

    async def _search_searxng(self, query: str, count: int) -> str:
        """Search using SearXNG public instance."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.searxng_instance}/search"
                params = {"q": query, "format": "json", "language": "ru", "safesearch": "0"}

                response = await client.get(
                    url, params=params, timeout=15.0, headers={"User-Agent": "teleChatBot/1.0"}
                )
                response.raise_for_status()
                data = response.json()

                results_data = data.get("results", [])
                if not results_data:
                    return ""

                results = []
                for idx, item in enumerate(results_data[:count], 1):
                    title = item.get("title", "")
                    content = item.get("content", "")
                    url_link = item.get("url", "")
                    results.append(f"{idx}. {title}\n{content}\nИсточник: {url_link}")

                if results:
                    logger.info(f"SearXNG returned {len(results)} results")
                    return "\n\n".join(results)
                return ""

        except Exception as e:
            logger.error(f"SearXNG search error: {e}")
            raise

    async def _search_duckduckgo(self, query: str, count: int) -> str:
        """Search using DuckDuckGo (last fallback)."""
        try:
            with DDGS() as ddgs:
                results_list = list(ddgs.text(query, max_results=count))

                results = []
                for idx, result in enumerate(results_list[:count], 1):
                    title = result.get("title", "")
                    body = result.get("body", "")
                    url = result.get("href", "")
                    results.append(f"{idx}. {title}\n{body}\nИсточник: {url}")

                if results:
                    logger.info(f"DuckDuckGo returned {len(results)} results")
                    return "\n\n".join(results)
                return ""

        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            raise
