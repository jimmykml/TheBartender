from datetime import date

from clients.news_api import NewsArticle, get_news_client
from app.config import get_settings

_GENERIC_WORDS = {
    "corporation", "corp", "inc", "incorporated",
    "ltd", "limited", "company", "co", "group", "holdings",
}


async def get_company_news(ticker: str, from_date: date, to_date: date) -> str:
    """
    Fetch news articles for a stock ticker between from_date and to_date,
    filtered to only relevant results. Returns a formatted list of headlines.
    """
    settings = get_settings()

    async with get_news_client(settings.news_sources, settings.news_api_keys()) as client:
        articles = await client.get_news(ticker, from_date, to_date)

    relevant = _filter_relevant(articles, ticker)

    if not relevant:
        return f"No relevant news found for {ticker} between {from_date} and {to_date}."

    lines = [f"{len(relevant)} relevant articles for {ticker} ({from_date} → {to_date}):"]
    for a in relevant:
        lines.append(f"- [{a.published_at.strftime('%Y-%m-%d')}] {a.source}: {a.headline}")
    return "\n".join(lines)


# ── private helpers ───────────────────────────────────────────────────────────

def _filter_relevant(articles: list[NewsArticle], ticker: str) -> list[NewsArticle]:
    keywords = _build_keywords(ticker)
    return [a for a in articles if _matches(a.headline, keywords)]


def _build_keywords(ticker: str) -> list[str]:
    keywords = [ticker.upper()]
    name = _resolve_company_name(ticker)
    if name:
        keywords.extend(w for w in name.split() if w.lower() not in _GENERIC_WORDS)
    return keywords


def _matches(headline: str, keywords: list[str]) -> bool:
    lower = headline.lower()
    return any(kw.lower() in lower for kw in keywords)


def _resolve_company_name(ticker: str) -> str | None:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName")
    except Exception:
        return None
