from agents.base_agent import BaseAgent
from models.outputs import DriverAnalysis
from prompts.driver_agent_prompts import SYSTEM


class DriverAgent(BaseAgent[DriverAnalysis]):

    @property
    def output_type(self) -> type[DriverAnalysis]:
        return DriverAnalysis

    @property
    def system_prompt(self) -> str:
        return SYSTEM

    async def run_from_inputs(  # type: ignore[override]
        self,
        ticker: str,
        price_context: str,
        news_context: str,
        fiscal_context: str | None = None,
    ) -> DriverAnalysis:
        parts = [
            f"Attribute the price move for {ticker.upper()} using the data below.",
            "",
            price_context,
            "",
            "--- News Context ---",
            news_context,
        ]
        if fiscal_context:
            parts += ["", "--- Fiscal Context (earnings occurred near this window) ---", fiscal_context]
        result = await self.run("\n".join(parts))
        result.price_context = price_context
        return result
