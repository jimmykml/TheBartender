import os
import requests
from datetime import datetime, timedelta


def fetch_news(ticker, days=3):
    """Fetch recent news headlines using NewsAPI"""
    api_key = os.getenv("NEWS_API_KEY")
    base_url = "https://newsapi.org/v2/everything"

    query_date = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    params = {
        "q": ticker,
        "from": query_date,
        "sortBy": "publishedAt",
        "language": "en",
        "apiKey": api_key,
        "pageSize": 10,
    }

    response = requests.get(base_url, params=params)
    if response.status_code != 200:
        return []

    articles = response.json().get("articles", [])
    return [f"{a['title']} - {a['source']['name']}" for a in articles]
