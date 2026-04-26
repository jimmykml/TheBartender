from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import httpx


@dataclass(frozen=True)
class NewsArticle:
    ticker: str
    headline: str
    summary: str
    source: str
    url: str
    published_at: datetime


class BaseNewsClient(ABC):
    """Abstract news client. Implement this to add a new provider."""

    @abstractmethod
    async def get_news(self, ticker: str, from_date: date, to_date: date) -> list[NewsArticle]:
        ...

    async def __aenter__(self) -> "BaseNewsClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    @abstractmethod
    async def close(self) -> None:
        ...


# ── Finnhub ──────────────────────────────────────────────────────────────────

class FinnhubNewsClient(BaseNewsClient):
    """
    Docs: https://finnhub.io/docs/api/company-news
    Response fields: headline, summary, source, url, datetime (unix timestamp)
    """

    _BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._http = httpx.AsyncClient(base_url=self._BASE_URL, timeout=10.0)

    async def get_news(self, ticker: str, from_date: date, to_date: date) -> list[NewsArticle]:
        response = await self._http.get(
            "/company-news",
            params={
                "symbol": ticker.upper(),
                "from": from_date.isoformat(),
                "to": to_date.isoformat(),
                "token": self._api_key,
            },
        )
        response.raise_for_status()
        return [self._parse(ticker, item) for item in response.json()]

    @staticmethod
    def _parse(ticker: str, raw: dict[str, Any]) -> NewsArticle:
        return NewsArticle(
            ticker=ticker.upper(),
            headline=raw.get("headline", ""),
            summary=raw.get("summary", ""),
            source=raw.get("source", ""),
            url=raw.get("url", ""),
            published_at=datetime.fromtimestamp(raw["datetime"], tz=timezone.utc),
        )

    async def close(self) -> None:
        await self._http.aclose()


# ── MarketAux ─────────────────────────────────────────────────────────────────

class MarketAuxNewsClient(BaseNewsClient):
    """
    Docs: https://www.marketaux.com/documentation
    Response fields: title, description, url, published_at (ISO 8601), source
    """

    _BASE_URL = "https://api.marketaux.com/v1"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._http = httpx.AsyncClient(base_url=self._BASE_URL, timeout=10.0)

    async def get_news(self, ticker: str, from_date: date, to_date: date) -> list[NewsArticle]:
        response = await self._http.get(
            "/news/all",
            params={
                "symbols": ticker.upper(),
                "published_after": f"{from_date.isoformat()}T00:00:00",
                "published_before": f"{to_date.isoformat()}T23:59:59",
                "api_token": self._api_key,
            },
        )
        response.raise_for_status()
        return [self._parse(ticker, item) for item in response.json().get("data", [])]

    @staticmethod
    def _parse(ticker: str, raw: dict[str, Any]) -> NewsArticle:
        return NewsArticle(
            ticker=ticker.upper(),
            headline=raw.get("title", ""),
            summary=raw.get("description") or raw.get("snippet", ""),
            source=raw.get("source", ""),
            url=raw.get("url", ""),
            published_at=datetime.fromisoformat(
                raw["published_at"].replace("Z", "+00:00")
            ),
        )

    async def close(self) -> None:
        await self._http.aclose()


# ── Aggregated (multi-source) ─────────────────────────────────────────────────

class AggregatedNewsClient(BaseNewsClient):
    """Fans out to multiple clients and deduplicates by URL."""

    def __init__(self, clients: list[BaseNewsClient]) -> None:
        self._clients = clients

    async def get_news(self, ticker: str, from_date: date, to_date: date) -> list[NewsArticle]:
        seen: set[str] = set()
        articles: list[NewsArticle] = []
        for client in self._clients:
            for article in await client.get_news(ticker, from_date, to_date):
                if article.url not in seen:
                    seen.add(article.url)
                    articles.append(article)
        articles.sort(key=lambda a: a.published_at, reverse=True)
        return articles

    async def close(self) -> None:
        for client in self._clients:
            await client.close()


# ── Registry & factory ────────────────────────────────────────────────────────

_REGISTRY: dict[str, type[BaseNewsClient]] = {
    "finnhub": FinnhubNewsClient,
    "marketaux": MarketAuxNewsClient,
}


def get_news_client(
    sources: list[str],
    api_keys: dict[str, str],
) -> BaseNewsClient:
    """
    Build a news client for one or more providers.

    Args:
        sources:  e.g. ["finnhub"] or ["finnhub", "marketaux"]
        api_keys: mapping of provider name → API key

    Returns:
        A single client if one source, AggregatedNewsClient if multiple.
    """
    clients: list[BaseNewsClient] = []
    for name in sources:
        cls = _REGISTRY.get(name)
        if cls is None:
            raise ValueError(f"Unknown news provider '{name}'. Available: {list(_REGISTRY)}")
        key = api_keys.get(name)
        if not key:
            raise RuntimeError(f"No API key configured for news provider '{name}'")
        clients.append(cls(api_key=key))

    if len(clients) == 1:
        return clients[0]
    return AggregatedNewsClient(clients)
