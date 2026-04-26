from agents.base_agent import BaseAgent
from models.outputs import FiscalAnalysis
from prompts.fiscal_agent_prompts import SYSTEM
from tools.filings_tools import fetch_financial_data


class FiscalAgent(BaseAgent[FiscalAnalysis]):

    @property
    def output_type(self) -> type[FiscalAnalysis]:
        return FiscalAnalysis

    @property
    def system_prompt(self) -> str:
        return SYSTEM

    async def run_from_inputs(self, ticker: str) -> FiscalAnalysis:  # type: ignore[override]
        raw_data = fetch_financial_data(ticker)
        prompt = (
            f"Analyze the latest financial report for {ticker}. "
            f"The financial statements are provided below:\n\n{raw_data}"
        )
        result = await self.run(prompt)
        result.report_context = raw_data
        return result
