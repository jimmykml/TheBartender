from agents.base_agent import BaseAgent
from models.outputs import ValuationAnalysis
from prompts.valuation_agent_prompts import SYSTEM
from tools.valuation_agent_tools import build_valuation_context


class ValuationAgent(BaseAgent[ValuationAnalysis]):

    @property
    def output_type(self) -> type[ValuationAnalysis]:
        return ValuationAnalysis

    @property
    def system_prompt(self) -> str:
        return SYSTEM

    async def run_from_inputs(self, ticker: str) -> ValuationAnalysis:  # type: ignore[override]
        valuation_context = build_valuation_context(ticker)
        prompt = (
            f"Produce a valuation analysis for {ticker.upper()} using only the "
            f"deterministic valuation context below.\n\n{valuation_context}"
        )
        result = await self.run(prompt)
        result.valuation_context = valuation_context
        return result
