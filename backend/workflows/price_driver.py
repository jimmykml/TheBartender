from datetime import date, timedelta

from agents.driver_agent import DriverAgent
from models.domain import AgentName, UserIntent, WorkflowName
from models.outputs import AgentResult, WorkflowResult
from models.requests import AnalysisRequest
from tools.market_data_tools import build_price_driver_context, had_earnings_near_date
from workflows.state import WorkflowRun, company_name_for, run_agent, status_for


async def run_driver_workflow(
    request: AnalysisRequest,
    provider: str | None = None,
    model: str | None = None,
) -> WorkflowRun:
    ticker = request.ticker
    from_date = request.from_date or date.today() - timedelta(days=7)
    to_date = request.to_date or date.today()
    results: list[AgentResult] = []
    selected_agents: list[AgentName] = []
    usages = []

    # Step 1: Price movement context (deterministic)
    try:
        price_context = build_price_driver_context(ticker, from_date, to_date)
    except Exception as exc:
        price_context = f"Price data unavailable: {exc}"

    # Step 2: News Agent for the target window
    news_result, news_usage = await run_agent(AgentName.NEWS, request, provider, model)
    results.append(news_result)
    selected_agents.append(AgentName.NEWS)
    if news_usage:
        usages.append(news_usage)

    # Step 3: Fiscal Agent — conditional on earnings near the target window
    fiscal_result: AgentResult | None = None
    if had_earnings_near_date(ticker, to_date):
        fiscal_result, fiscal_usage = await run_agent(AgentName.FISCAL, request, provider, model)
        results.append(fiscal_result)
        selected_agents.append(AgentName.FISCAL)
        if fiscal_usage:
            usages.append(fiscal_usage)

    # Step 4: Driver Agent
    news_context = _fmt_news(news_result.output) if news_result.success else "News data unavailable."
    fiscal_context = _fmt_fiscal(fiscal_result.output) if (fiscal_result and fiscal_result.success) else None

    try:
        driver_agent = DriverAgent(provider=provider, model=model)
        driver_output = await driver_agent.run_from_inputs(
            ticker=ticker,
            price_context=price_context,
            news_context=news_context,
            fiscal_context=fiscal_context,
        )
        driver_result = AgentResult(
            agent=AgentName.DRIVER,
            output=driver_output.model_dump(),
            success=True,
        )
        if driver_agent.usage():
            usages.append(driver_agent.usage())
    except Exception as exc:
        driver_result = AgentResult(
            agent=AgentName.DRIVER,
            output={},
            success=False,
            error=str(exc),
        )

    results.append(driver_result)
    selected_agents.append(AgentName.DRIVER)

    warnings = [r.error or f"{r.agent} failed" for r in results if not r.success]
    payload = {str(r.agent): r.output for r in results if r.success}

    return WorkflowRun(
        result=WorkflowResult(
            workflow_name=WorkflowName.DRIVER,
            ticker=ticker,
            company_name=company_name_for(ticker),
            user_intent=UserIntent.DRIVER,
            selected_agents=selected_agents,
            execution_status=status_for(results, warnings),
            agent_outputs=results,
            missing_data_warnings=warnings,
            confidence_summary=(
                "Price driver confidence depends on news coverage, volume anomalies, "
                "and whether earnings coincided with the move."
            ),
            final_response_payload=payload,
        ),
        usages=usages,
    )


def _fmt_news(output: dict) -> str:
    lines = [
        f"Sentiment: {output.get('sentiment', 'N/A')} "
        f"(confidence: {output.get('confidence', 0):.0%})",
        f"Summary: {output.get('summary', '')}",
    ]
    risks = output.get("key_risks", [])
    if risks:
        lines.append(f"Key risks: {'; '.join(risks)}")
    opps = output.get("key_opportunities", [])
    if opps:
        lines.append(f"Key opportunities: {'; '.join(opps)}")
    articles = [a.get("headline", "") for a in output.get("key_articles", [])[:3]]
    if articles:
        lines.append(f"Top headlines: {'; '.join(articles)}")
    return "\n".join(lines)


def _fmt_fiscal(output: dict) -> str:
    lines = [
        f"Period: {output.get('period', 'N/A')}",
        f"Summary: {output.get('summary', '')}",
    ]
    highlights = output.get("highlights", [])
    if highlights:
        lines.append(f"Highlights: {'; '.join(highlights)}")
    concerns = output.get("concerns", [])
    if concerns:
        lines.append(f"Concerns: {'; '.join(concerns)}")
    metrics = output.get("key_metrics", [])
    if metrics:
        metric_strs = [f"{m['name']}: {m['value']}" for m in metrics[:4]]
        lines.append(f"Key metrics: {'; '.join(metric_strs)}")
    return "\n".join(lines)
