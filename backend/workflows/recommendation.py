from datetime import date, timedelta

from agents.driver_agent import DriverAgent
from agents.recommendation_agent import RecommendationAgent
from models.domain import AgentName, UserIntent, WorkflowName
from models.outputs import AgentResult, WorkflowResult
from models.requests import AnalysisRequest
from tools.market_data_tools import build_price_driver_context, has_recent_abnormal_move
from tools.scoring_tools import build_recommendation_context, compute_recommendation_scores
from workflows.state import WorkflowRun, company_name_for, run_agent, status_for


async def run_recommendation_workflow(
    request: AnalysisRequest,
    provider: str | None = None,
    model: str | None = None,
) -> WorkflowRun:
    ticker = request.ticker
    results: list[AgentResult] = []
    selected_agents: list[AgentName] = []
    usages = []

    # Step 1: News Agent
    news_result, news_usage = await run_agent(AgentName.NEWS, request, provider, model)
    results.append(news_result)
    selected_agents.append(AgentName.NEWS)
    if news_usage:
        usages.append(news_usage)

    # Step 2: Fiscal Agent
    fiscal_result, fiscal_usage = await run_agent(AgentName.FISCAL, request, provider, model)
    results.append(fiscal_result)
    selected_agents.append(AgentName.FISCAL)
    if fiscal_usage:
        usages.append(fiscal_usage)

    # Step 3: Valuation Agent
    valuation_result, val_usage = await run_agent(AgentName.VALUATION, request, provider, model)
    results.append(valuation_result)
    selected_agents.append(AgentName.VALUATION)
    if val_usage:
        usages.append(val_usage)

    # Step 4: Driver Agent — conditional on a recent abnormal price move
    driver_result: AgentResult | None = None
    if has_recent_abnormal_move(ticker):
        from_date = request.from_date or date.today() - timedelta(days=7)
        to_date = request.to_date or date.today()
        try:
            price_ctx = build_price_driver_context(ticker, from_date, to_date)
        except Exception as exc:
            price_ctx = f"Price data unavailable: {exc}"

        news_ctx = _fmt_news(news_result.output) if news_result.success else "News data unavailable."
        fiscal_ctx = _fmt_fiscal(fiscal_result.output) if fiscal_result.success else None

        try:
            driver_agent = DriverAgent(provider=provider, model=model)
            driver_output = await driver_agent.run_from_inputs(
                ticker=ticker,
                price_context=price_ctx,
                news_context=news_ctx,
                fiscal_context=fiscal_ctx,
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

    # Step 5: Deterministic scoring layer
    valuation_out = valuation_result.output if valuation_result.success else None
    fiscal_out = fiscal_result.output if fiscal_result.success else None
    news_out = news_result.output if news_result.success else None
    driver_out = driver_result.output if (driver_result and driver_result.success) else None

    scores, composite = compute_recommendation_scores(valuation_out, fiscal_out, news_out)
    context = build_recommendation_context(
        ticker=ticker,
        news=news_out,
        fiscal=fiscal_out,
        valuation=valuation_out,
        driver=driver_out,
        scores=scores,
        composite_score=composite,
    )

    # Step 6: Recommendation Agent
    try:
        rec_agent = RecommendationAgent(provider=provider, model=model)
        rec_output = await rec_agent.run_from_inputs(
            ticker=ticker,
            context=context,
            scores=scores,
            composite_score=composite,
        )
        rec_result = AgentResult(
            agent=AgentName.RECOMMENDATION,
            output=rec_output.model_dump(),
            success=True,
        )
        if rec_agent.usage():
            usages.append(rec_agent.usage())
    except Exception as exc:
        rec_result = AgentResult(
            agent=AgentName.RECOMMENDATION,
            output={},
            success=False,
            error=str(exc),
        )

    results.append(rec_result)
    selected_agents.append(AgentName.RECOMMENDATION)

    warnings = [r.error or f"{r.agent} failed" for r in results if not r.success]
    payload = {str(r.agent): r.output for r in results if r.success}

    return WorkflowRun(
        result=WorkflowResult(
            workflow_name=WorkflowName.RECOMMENDATION,
            ticker=ticker,
            company_name=company_name_for(ticker),
            user_intent=UserIntent.RECOMMENDATION,
            selected_agents=selected_agents,
            execution_status=status_for(results, warnings),
            agent_outputs=results,
            missing_data_warnings=warnings,
            confidence_summary=(
                "Recommendation confidence depends on valuation data quality, "
                "news coverage breadth, and whether fiscal filings are current."
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
