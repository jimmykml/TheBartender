from models.domain import AgentName, UserIntent, WorkflowName
from models.outputs import WorkflowResult
from models.requests import AnalysisRequest
from workflows.state import WorkflowRun, company_name_for, run_agent, status_for


async def run_valuation_workflow(
    request: AnalysisRequest,
    provider: str | None = None,
    model: str | None = None,
) -> WorkflowRun:
    result, usage = await run_agent(AgentName.VALUATION, request, provider, model)
    warnings = [] if result.success else [result.error or "Valuation analysis failed"]
    payload = result.output if result.success else {}

    return WorkflowRun(
        result=WorkflowResult(
            workflow_name=WorkflowName.VALUATION,
            ticker=request.ticker,
            company_name=company_name_for(request.ticker),
            user_intent=UserIntent.VALUATION,
            selected_agents=[AgentName.VALUATION],
            execution_status=status_for([result], warnings),
            agent_outputs=[result],
            missing_data_warnings=warnings,
            confidence_summary=(
                "Valuation confidence depends on positive free cash flow, current market data, and usable peer multiples."
            ),
            final_response_payload=payload,
        ),
        usages=[usage] if usage else [],
    )
