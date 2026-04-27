from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from pydantic_ai.usage import RunUsage

from agents.base_agent import BaseAgent
from agents.fiscal_agent import FiscalAgent
from agents.news_agent import NewsAgent
from agents.valuation_agent import ValuationAgent
from models.domain import AgentName
from models.outputs import AgentResult
from models.requests import AnalysisRequest


@dataclass
class WorkflowRun:
    result: Any
    usages: list[RunUsage] = field(default_factory=list)


def news_window(request: AnalysisRequest) -> tuple[date, date]:
    today = date.today()
    return request.from_date or today - timedelta(days=7), request.to_date or today


def company_name_for(ticker: str) -> str | None:
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
        return info.get("longName") or info.get("shortName")
    except Exception:
        return None


def status_for(results: list[AgentResult], warnings: list[str]) -> str:
    if results and all(r.success for r in results) and not warnings:
        return "success"
    if any(r.success for r in results):
        return "partial_success" if warnings or any(not r.success for r in results) else "success"
    return "failed"


async def run_agent(
    agent_name: AgentName,
    request: AnalysisRequest,
    provider: str | None = None,
    model: str | None = None,
) -> tuple[AgentResult, RunUsage | None]:
    agent: BaseAgent[Any]
    try:
        if agent_name == AgentName.NEWS:
            agent = NewsAgent(provider=provider, model=model)
            from_date, to_date = news_window(request)
            output = await agent.run_from_inputs(
                ticker=request.ticker,
                from_date=str(from_date),
                to_date=str(to_date),
            )
        elif agent_name == AgentName.FISCAL:
            agent = FiscalAgent(provider=provider, model=model)
            output = await agent.run_from_inputs(ticker=request.ticker)
        elif agent_name == AgentName.VALUATION:
            agent = ValuationAgent(provider=provider, model=model)
            output = await agent.run_from_inputs(ticker=request.ticker)
        else:
            return (
                AgentResult(
                    agent=agent_name,
                    output={},
                    success=False,
                    error=f"{agent_name} agent is not implemented in v1",
                ),
                None,
            )

        return (
            AgentResult(agent=agent_name, output=output.model_dump(), success=True),
            agent.usage(),
        )
    except Exception as exc:
        return AgentResult(agent=agent_name, output={}, success=False, error=str(exc)), None
