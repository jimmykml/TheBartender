import asyncio
import logging
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.usage import RunUsage

from agents.base_agent import BaseAgent
from clients.llm import build_model
from models.domain import AgentName
from models.outputs import AgentResult, ExecutionPlan, SupervisorResult
from models.requests import AnalysisRequest
from prompts.supervisor_agent_prompts import SYSTEM

logger = logging.getLogger(__name__)

# Registry maps AgentName → BaseAgent subclass.
# Add entries here as agents are implemented.
_REGISTRY: dict[AgentName, type[BaseAgent[Any]]] = {}

try:
    from agents.news_agent import NewsAgent
    _REGISTRY[AgentName.NEWS] = NewsAgent
except ImportError:
    pass

try:
    from agents.driver_agent import DriverAgent
    _REGISTRY[AgentName.DRIVER] = DriverAgent
except ImportError:
    pass

try:
    from agents.fiscal_agent import FiscalAgent
    _REGISTRY[AgentName.FISCAL] = FiscalAgent
except ImportError:
    pass

try:
    from agents.valuation_agent import ValuationAgent
    _REGISTRY[AgentName.VALUATION] = ValuationAgent
except ImportError:
    pass

try:
    from agents.recommendation_agent import RecommendationAgent
    _REGISTRY[AgentName.RECOMMENDATION] = RecommendationAgent
except ImportError:
    pass


class SupervisorAgent:
    """
    Plans and orchestrates specialist agents for a given AnalysisRequest.

    Flow:
      1. LLM planner produces an ExecutionPlan (which agents, why).
      2. Parallel agents run concurrently via asyncio.gather.
      3. If needs_recommendation, RecommendationAgent runs last with all prior outputs.
    """

    def __init__(self, provider: str | None = None, model: str | None = None) -> None:
        self._provider = provider
        self._model = model
        self._planner: Agent[None, ExecutionPlan] = Agent(
            build_model(provider, model),
            output_type=ExecutionPlan,
            system_prompt=SYSTEM,
        )
        self._last_usage: list[RunUsage] = []

    async def run(self, request: AnalysisRequest) -> SupervisorResult:
        self._last_usage.clear()

        plan = await self._plan(request)
        logger.info(
            "Plan for %s: agents=%s recommend=%s",
            request.ticker,
            plan.parallel_agents,
            plan.needs_recommendation,
        )

        results = await self._execute_parallel(plan, request)

        if plan.needs_recommendation and AgentName.RECOMMENDATION in _REGISTRY:
            rec_result = await self._run_recommendation(plan, request, results)
            results.append(rec_result)

        return SupervisorResult(ticker=request.ticker, plan=plan, results=results)

    def usage(self) -> list[RunUsage]:
        """Token usage across all LLM calls in the last run."""
        return self._last_usage

    # ── private ──────────────────────────────────────────────────────────────

    async def _plan(self, request: AnalysisRequest) -> ExecutionPlan:
        prompt = (
            f"Ticker: {request.ticker}\n"
            f"Time horizon: {request.time_horizon}\n"
            f"Focus: {request.focus or 'general analysis'}"
        )
        result = await self._planner.run(prompt)
        self._last_usage.append(result.usage())
        return result.output

    async def _execute_parallel(
        self, plan: ExecutionPlan, request: AnalysisRequest
    ) -> list[AgentResult]:
        tasks = [
            self._run_agent(name, request)
            for name in plan.parallel_agents
            if name != AgentName.RECOMMENDATION
        ]
        return list(await asyncio.gather(*tasks))

    async def _run_agent(
        self, name: AgentName, request: AnalysisRequest
    ) -> AgentResult:
        cls = _REGISTRY.get(name)
        if cls is None:
            return AgentResult(
                agent=name,
                output={},
                success=False,
                error=f"{name} agent not implemented yet",
            )
        try:
            agent: BaseAgent[Any] = cls(provider=self._provider, model=self._model)
            output = await agent.run_from_inputs(ticker=request.ticker)
            if hasattr(agent, "usage") and agent.usage():
                self._last_usage.append(agent.usage())  # type: ignore[arg-type]
            return AgentResult(
                agent=name,
                output=output.model_dump(),
                success=True,
            )
        except Exception as exc:
            logger.exception("Agent %s failed: %s", name, exc)
            return AgentResult(agent=name, output={}, success=False, error=str(exc))

    async def _run_recommendation(
        self,
        plan: ExecutionPlan,
        request: AnalysisRequest,
        prior: list[AgentResult],
    ) -> AgentResult:
        summaries = "\n\n".join(
            f"[{r.agent}]\n{r.output}" for r in prior if r.success
        )
        prompt = (
            f"Ticker: {request.ticker}\n"
            f"Time horizon: {plan.time_horizon}\n\n"
            f"Research inputs:\n{summaries}"
        )
        cls = _REGISTRY[AgentName.RECOMMENDATION]
        agent: BaseAgent[Any] = cls(provider=self._provider, model=self._model)
        try:
            output = await agent.run(prompt)
            if hasattr(agent, "usage") and agent.usage():
                self._last_usage.append(agent.usage())  # type: ignore[arg-type]
            return AgentResult(
                agent=AgentName.RECOMMENDATION,
                output=output.model_dump(),
                success=True,
            )
        except Exception as exc:
            logger.exception("RecommendationAgent failed: %s", exc)
            return AgentResult(
                agent=AgentName.RECOMMENDATION,
                output={},
                success=False,
                error=str(exc),
            )
