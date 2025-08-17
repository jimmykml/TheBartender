from tools.market_data import get_price_history
from tools.indicators import compute_rsi, compute_macd, compute_sma


class QuantAgent:
    def __init__(self, model):
        self.model = model  # Must implement BaseLLM

    def run(self, ticker: str, period: str = "3mo", **kwargs):
        prices = get_price_history(ticker, period)
        if prices.empty or len(prices) < 30:
            return {
                "ticker": ticker,
                "error": "Insufficient price history.",
                "indicators": {},
            }

        # Compute indicators
        rsi = compute_rsi(prices)
        macd_line, signal_line = compute_macd(prices)
        sma_20 = compute_sma(prices)

        prompt = f"""
        The following are recent technical indicators for {ticker}:

        - RSI: {rsi:.2f}
        - MACD: {macd_line:.2f}
        - Signal Line: {signal_line:.2f}
        - 20-day Simple Moving Average: {sma_20:.2f}
        - Current Price: {prices.iloc[-1]:.2f}

        Based on these indicators, provide a short-term (1–4 weeks) outlook for the stock.
        Is it bullish, bearish, or neutral? Justify your reasoning clearly.
        """

        analysis = self.model.generate(prompt)

        return {
            "ticker": ticker,
            "indicators": {
                "rsi": rsi,
                "macd": macd_line,
                "signal": signal_line,
                "sma_20": sma_20,
                "current_price": prices.iloc[-1],
            },
            "analysis": analysis,
        }
