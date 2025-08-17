class PlannerAgent:
    def __init__(self):
        pass  # No model needed for rule-based planning

    def route(self, query: dict):
        """
        query: {
            'ticker': 'AAPL',
            'time_horizon': 'both' | 'short_term' | 'long_term'
        }
        """
        ticker = query.get("ticker")
        horizon = query.get("time_horizon", "both")

        plan = {
            "ticker": ticker,
            "run_quant": False,
            "run_fundamentals": False,
            "run_news": False,
        }

        if horizon in ["both", "short_term"]:
            plan["run_quant"] = True
            plan["run_news"] = True

        if horizon in ["both", "long_term"]:
            plan["run_fundamentals"] = True
            plan["run_news"] = True  # still useful for long-term narratives

        return plan
