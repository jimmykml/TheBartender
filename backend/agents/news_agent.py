from agents.base_agent import BaseAgent
from models.outputs import NewsAnalysis
from prompts.news_agent_prompts import SYSTEM
from tools.news_agent_tools import get_company_news
from tools.web_search_tools import search_press_releases


class NewsAgent(BaseAgent[NewsAnalysis]):

    @property
    def output_type(self) -> type[NewsAnalysis]:
        return NewsAnalysis

    @property
    def system_prompt(self) -> str:
        return SYSTEM

    @property
    def tools(self) -> list:
        return [get_company_news, search_press_releases]

    def build_prompt(self, ticker: str, from_date: str, to_date: str) -> str:  # type: ignore[override]
        return f"Analyze news for {ticker} between {from_date} and {to_date}."
