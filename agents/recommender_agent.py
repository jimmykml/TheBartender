class RecommenderAgent:
    def __init__(self, model):
        self.model = model  # Any BaseLLM implementation

    def run(self, inputs: dict):
        ticker = inputs.get("ticker", "UNKNOWN")
        quant = inputs.get("quant", {}).get("analysis", "")
        fundamentals = inputs.get("fundamentals", {}).get("analysis", "")
        news = inputs.get("news", {}).get("summary", "")

        # Compose prompt
        prompt = f"""
        You are a financial analyst. Based on the following analyses, provide a short-term and long-term recommendation for the stock {ticker}.
        Choose one of: Buy, Hold, or Sell. Justify each recommendation.

        --- Technical Analysis (Short-Term) ---
        {quant}

        --- Fundamental Analysis (Long-Term) ---
        {fundamentals}

        --- News Summary ---
        {news}

        Structure your response like this:
        Short-Term Recommendation: <Buy/Hold/Sell>
        Long-Term Recommendation: <Buy/Hold/Sell>
        Summary: <1-2 sentence rationale combining all insights>
        Confidence Scores (0-100): short_term=X, long_term=Y
        """

        # Ask the model
        response = self.model.generate(prompt)

        # Basic post-processing (or optionally parse LLM response if structured)
        return {"ticker": ticker, "raw_recommendation": response}
