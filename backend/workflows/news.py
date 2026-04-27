from models.domain import AgentName, UserIntent, WorkflowName
from models.outputs import WorkflowResult
from models.requests import AnalysisRequest
from workflows.state import WorkflowRun, company_name_for, run_agent, status_for


async def run_news_workflow(
    request: AnalysisRequest,
    provider: str | None = None,
    model: str | None = None,
) -> WorkflowRun:
    result, usage = await run_agent(AgentName.NEWS, request, provider, model)
    warnings = [] if result.success else [result.error or "News analysis failed"]
    payload = result.output if result.success else {}

    return WorkflowRun(
        result=WorkflowResult(
            workflow_name=WorkflowName.NEWS,
            ticker=request.ticker,
            company_name=company_name_for(request.ticker),
            user_intent=UserIntent.NEWS,
            selected_agents=[AgentName.NEWS],
            execution_status=status_for([result], warnings),
            agent_outputs=[result],
            missing_data_warnings=warnings,
            confidence_summary=_confidence_summary(result),
            final_response_payload=payload,
        ),
        usages=[usage] if usage else [],
    )


def _confidence_summary(result) -> str:
    if not result.success:
        return "Low confidence because the news workflow did not complete."
    confidence = result.output.get("confidence")
    if isinstance(confidence, int | float):
        return f"News confidence: {confidence:.0%}."
    return "News confidence is based on the agent output."
