from tools.news_fetcher import fetch_news


class NewsAgent:
    def __init__(self, model):
        """
        model: an instance of a class implementing BaseLLM
        """
        self.model = model

    def run(self, ticker: str, **kwargs):
        # Step 1: Fetch recent news
        headlines = fetch_news(ticker)
        if not headlines:
            return {"ticker": ticker, "error": "No recent news found.", "headlines": []}

        # Step 2: Prepare summarization prompt
        formatted = "\n".join(f"- {line}" for line in headlines)
        prompt = f"""
        Here are some recent news headlines about {ticker}:

        {formatted}

        Summarize the key themes and market sentiment from these headlines.
        Mention any major risks or opportunities.
        """

        # Step 3: Ask LLM to summarize
        summary = self.model.generate(prompt)

        return {"ticker": ticker, "headlines": headlines, "summary": summary}
