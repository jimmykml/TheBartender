from agents.planner_agent import PlannerAgent
from agents.quant_agent import QuantAgent
from agents.fundamentals_agent import FundamentalsAgent
from agents.news_agent import NewsAgent
from agents.recommender_agent import RecommenderAgent


class AgentOrchestrator:
    def __init__(self, model):
        self.model = model  # Any BaseLLM implementation

        # Initialize agents
        self.planner = PlannerAgent()
        self.quant_agent = QuantAgent(model)
        self.fundamentals_agent = FundamentalsAgent(model)
        self.news_agent = NewsAgent(model)
        self.recommender = RecommenderAgent(model)

    def analyze(self, ticker: str, time_horizon: str = "both") -> dict:
        """
        Run the full pipeline and return recommendation summary.
        time_horizon: "short_term", "long_term", or "both"
        """
        plan = self.planner.route({"ticker": ticker, "time_horizon": time_horizon})

        results = {"ticker": ticker}

        if plan.get("run_quant"):
            results["quant"] = self.quant_agent.run(ticker)

        if plan.get("run_fundamentals"):
            results["fundamentals"] = self.fundamentals_agent.run(ticker)

        if plan.get("run_news"):
            results["news"] = self.news_agent.run(ticker)

        # Final recommendation based on outputs
        recommendation = self.recommender.run(results)
        results["final_recommendation"] = recommendation

        return results
