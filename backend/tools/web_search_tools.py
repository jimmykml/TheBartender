from datetime import date

from app.config import get_settings

# Domains known for official press releases and investor-grade announcements
_PRESS_RELEASE_DOMAINS = [
    "prnewswire.com",
    "businesswire.com",
    "globenewswire.com",
    "accesswire.com",
    "sec.gov",
    "ir.nasdaq.com",
    "investors.google.com",
]


async def search_press_releases(ticker: str, from_date: date, to_date: date) -> str:
    """
    Search for official press releases and investor announcements for a company
    between from_date and to_date. Results are restricted to high-quality
    press release sources only.
    """
    settings = get_settings()
    if not settings.tavily_api_key:
        return f"Web search unavailable: TAVILY_API_KEY not configured."

    from tavily import AsyncTavilyClient
    from tavily.errors import InvalidAPIKeyError

    query = (
        f"{ticker} press release OR earnings OR announcement OR guidance "
        f"after:{from_date.isoformat()} before:{to_date.isoformat()}"
    )

    try:
        client = AsyncTavilyClient(api_key=settings.tavily_api_key)
        response = await client.search(
            query=query,
            search_depth="advanced",
            include_domains=_PRESS_RELEASE_DOMAINS,
            max_results=10,
        )
    except InvalidAPIKeyError:
        return "Web search unavailable: invalid Tavily API key."
    except Exception as e:
        return f"Web search unavailable: {e}"

    results = response.get("results", [])
    if not results:
        return f"No press releases found for {ticker} between {from_date} and {to_date}."

    lines = [f"{len(results)} press releases found for {ticker} ({from_date} → {to_date}):"]
    for r in results:
        date_str = r.get("published_date", "unknown date")
        lines.append(f"- [{date_str}] {r['url']}")
        lines.append(f"  {r['title']}")
        if r.get("content"):
            lines.append(f"  {r['content'][:200].strip()}...")
    return "\n".join(lines)
