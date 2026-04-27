import logging

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.usage import RunUsage

from clients.llm import build_model
from models.domain import UserIntent
from models.outputs import WorkflowResult
from models.requests import AnalysisRequest
from workflows.fiscal_summary import run_fiscal_workflow
from workflows.news import run_news_workflow
from workflows.price_driver import run_driver_workflow
from workflows.recommendation import run_recommendation_workflow
from workflows.valuation import run_valuation_workflow

logger = logging.getLogger(__name__)


class _TickerResult(BaseModel):
    ticker: str = Field(
        description="Uppercase stock ticker symbol extracted from the question, e.g. 'NVDA'. "
                    "Empty string if no ticker is found."
    )


class SupervisorAgent:
    """
    Deterministic v1 supervisor.

    Flow:
      1. Detect one user intent with fixed priority rules.
      2. Select the matching predefined workflow.
      3. Execute that workflow.
      4. Return the workflow's standard output contract.
    """

    def __init__(self, provider: str | None = None, model: str | None = None) -> None:
        self._provider = provider
        self._model = model
        self._last_usage: list[RunUsage] = []

    async def _resolve_ticker(self, question: str, hint: str) -> str:
        """Use a small LLM call to extract the ticker from the raw question."""
        if not question.strip():
            return hint
        extractor: Agent[None, _TickerResult] = Agent(
            build_model(self._provider, self._model),
            output_type=_TickerResult,
            system_prompt=(
                "Extract the stock ticker symbol from the user's question. "
                "Return only the uppercase ticker (e.g. NVDA, AAPL, TSLA). "
                "Return an empty string if no ticker is mentioned."
            ),
        )
        try:
            result = await extractor.run(question)
            self._last_usage.append(result.usage())
            ticker = result.output.ticker.strip().upper()
            return ticker or hint
        except Exception:
            return hint

    async def run(self, request: AnalysisRequest) -> WorkflowResult:
        self._last_usage.clear()
        ticker = await self._resolve_ticker(request.question, request.ticker)
        if not ticker:
            raise ValueError(
                "No stock ticker found in your question. "
                "Please mention one, e.g. 'Should I buy NVDA?'"
            )
        request = request.model_copy(update={"ticker": ticker})
        intent = self._detect_intent(request)
        logger.info("Selected %s workflow for %s", intent, request.ticker)

        match intent:
            case UserIntent.RECOMMENDATION:
                run = await run_recommendation_workflow(request, self._provider, self._model)
            case UserIntent.DRIVER:
                run = await run_driver_workflow(request, self._provider, self._model)
            case UserIntent.VALUATION:
                run = await run_valuation_workflow(request, self._provider, self._model)
            case UserIntent.FISCAL:
                run = await run_fiscal_workflow(request, self._provider, self._model)
            case UserIntent.NEWS:
                run = await run_news_workflow(request, self._provider, self._model)

        self._last_usage.extend(run.usages)
        return run.result

    def usage(self) -> list[RunUsage]:
        """Token usage across all LLM calls in the last run."""
        return self._last_usage

    def _detect_intent(self, request: AnalysisRequest) -> UserIntent:
        text = " ".join(
            part for part in [request.question, request.focus, str(request.time_horizon)] if part
        ).lower()

        # Priority order: Recommendation > Driver > Valuation > Fiscal > News.
        if _contains_any(text, _RECOMMENDATION_TERMS):
            return UserIntent.RECOMMENDATION
        if _contains_any(text, _DRIVER_TERMS):
            return UserIntent.DRIVER
        if _contains_any(text, _VALUATION_TERMS):
            return UserIntent.VALUATION
        if _contains_any(text, _FISCAL_TERMS):
            return UserIntent.FISCAL
        return UserIntent.NEWS


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


_RECOMMENDATION_TERMS = {
    "should i buy",
    "should i sell",
    "buy",
    "sell",
    "hold",
    "recommend",
    "recommendation",
    "investment",
    "worth buying",
    "invest",
}

_DRIVER_TERMS = {
    "why did",
    "what drove",
    "driver",
    "dropped",
    "drop",
    "fell",
    "fall",
    "skyrocket",
    "spike",
    "surge",
    "move",
    "moved",
    "after earnings",
}

_VALUATION_TERMS = {
    "valuation",
    "value",
    "valued",
    "undervalued",
    "overvalued",
    "expensive",
    "cheap",
    "fair value",
    "intrinsic",
}

_FISCAL_TERMS = {
    "earnings",
    "fiscal",
    "filing",
    "10-q",
    "10-k",
    "8-k",
    "financial results",
    "financial report",
    "quarter",
    "revenue",
    "margin",
}
