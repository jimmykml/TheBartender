from tools.fundamentals_data import get_fundamental_metrics

class FundamentalsAgent():
    def run(self, ticker: str, **kwargs):
        # Step 1: Fetch fundamental data
        metrics = get_fundamental_metrics(ticker)
        if not metrics:
            return {"ticker": ticker, "error": "No fundamental data found."}

        # Step 2: Format the data into a prompt
        prompt = f"""
        Analyze the following fundamental metrics for long-term investment potential of {ticker}:

        - Revenue Growth (5Y): {metrics.get('revenue_growth_5y')}
        - Net Margin: {metrics.get('net_margin')}
        - Return on Equity: {metrics.get('roe')}
        - P/E Ratio: {metrics.get('pe_ratio')}
        - Debt to Equity: {metrics.get('de_ratio')}
        - Free Cash Flow: {metrics.get('free_cash_flow')}
        - DCF Valuation: {metrics.get('dcf_value')}
        - Current Price: {metrics.get('current_price')}

        Based on these, provide a long-term investment recommendation.
        """

        # Step 3: Get LLM-generated insight
        response = self.model.generate(prompt)

        return {
            "ticker": ticker,
            "metrics": metrics,
            "analysis": response
        }
