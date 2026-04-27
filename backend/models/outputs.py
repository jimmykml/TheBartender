from typing import Any, Literal
from pydantic import BaseModel, Field
from models.domain import AgentName, TimeHorizon, UserIntent, WorkflowName


class NewsItem(BaseModel):
    headline: str
    url: str
    source: str = Field(description="Publication or domain name")


class NewsAnalysis(BaseModel):
    ticker: str
    sentiment: Literal["bullish", "bearish", "neutral"]
    summary: str = Field(description="2-3 sentence summary of news impact")
    key_risks: list[str] = Field(default_factory=list)
    key_opportunities: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0–1")
    key_articles: list[NewsItem] = Field(
        default_factory=list,
        description="Most relevant news articles that informed this analysis",
    )


# ── Fiscal types ─────────────────────────────────────────────────────────────

class FiscalMetric(BaseModel):
    name: str
    value: str
    change: str | None = Field(default=None, description="YoY or QoQ change, e.g. '+12%'")
    note: str | None = Field(default=None, description="Brief context if needed")


class FiscalAnalysis(BaseModel):
    ticker: str
    period: str = Field(description="Most recent reporting period, e.g. 'FY2024 (ended Dec 31, 2024)'")
    summary: str = Field(description="3-4 sentence executive summary of financial health")
    key_metrics: list[FiscalMetric] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list, description="Positive takeaways")
    concerns: list[str] = Field(default_factory=list, description="Red flags or areas of concern")
    report_context: str = Field(default="", description="Raw financial data for follow-up Q&A")


# ── Valuation types ──────────────────────────────────────────────────────────

class DCFValuation(BaseModel):
    intrinsic_value_per_share: float
    projected_fcf_growth: float = Field(description="Annual FCF growth assumption, e.g. 0.08 for 8%")
    discount_rate: float = Field(description="Discount rate assumption, e.g. 0.10 for 10%")
    terminal_growth_rate: float = Field(description="Terminal growth assumption, e.g. 0.025 for 2.5%")
    enterprise_value: float
    equity_value: float


class RelativeValuation(BaseModel):
    implied_value_per_share: float | None = None
    peer_tickers: list[str] = Field(default_factory=list)
    peer_median_pe: float | None = None
    peer_median_ps: float | None = None
    peer_median_ev_ebitda: float | None = None
    method_values: dict[str, float] = Field(default_factory=dict)


class ReverseDCFValuation(BaseModel):
    implied_growth_rate: float | None = Field(
        default=None,
        description="Growth rate implied by current price, e.g. 0.12 for 12%",
    )
    realistic_growth_rate: float
    verdict: Literal["conservative", "reasonable", "aggressive", "unavailable"]


class ValuationAnalysis(BaseModel):
    ticker: str
    valuation_view: Literal["undervalued", "fairly_valued", "overvalued"]
    current_price: float
    intrinsic_value_per_share: float
    margin_of_safety: float = Field(description="Intrinsic value premium/discount vs current price")
    summary: str = Field(description="3-4 sentence valuation summary")
    dcf: DCFValuation
    relative: RelativeValuation
    reverse_dcf: ReverseDCFValuation
    key_assumptions: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    valuation_context: str = Field(default="", description="Raw valuation data and calculations")


# ── Driver types ─────────────────────────────────────────────────────────────

class DriverAnalysis(BaseModel):
    ticker: str
    period: str = Field(description="Analysis window, e.g. 'Mar 17–Mar 18 2025'")
    price_change_pct: float = Field(description="Percentage price change, e.g. 0.08 for 8%")
    primary_driver: str = Field(description="One-line attribution, e.g. 'Earnings beat + short squeeze'")
    summary: str = Field(description="3-4 sentence narrative explanation of the move")
    fundamental_factors: list[str] = Field(default_factory=list)
    technical_factors: list[str] = Field(default_factory=list)
    macro_factors: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    price_context: str = Field(default="", description="Raw price/technical data used for analysis")


# ── Recommendation types ──────────────────────────────────────────────────────

class ScoreComponent(BaseModel):
    component: str
    score: float = Field(ge=-1.0, le=1.0, description="Score from -1 (bearish) to +1 (bullish)")
    weight: float = Field(ge=0.0, le=1.0)
    note: str


class RecommendationAnalysis(BaseModel):
    ticker: str
    action: Literal["buy", "hold", "sell"]
    short_term_verdict: Literal["buy", "hold", "sell"]
    long_term_verdict: Literal["buy", "hold", "sell"]
    confidence: float = Field(ge=0.0, le=1.0)
    composite_score: float = Field(default=0.0, description="Weighted composite score -1 to +1")
    rationale: str = Field(description="4-5 sentence investment thesis")
    bull_case: list[str] = Field(default_factory=list)
    bear_case: list[str] = Field(default_factory=list)
    key_catalysts: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    scores: list[ScoreComponent] = Field(default_factory=list, description="Deterministic component scores")


# ── Supervisor types ─────────────────────────────────────────────────────────

class ExecutionPlan(BaseModel):
    ticker: str
    time_horizon: TimeHorizon
    parallel_agents: list[AgentName] = Field(
        description="Agents to run concurrently for data gathering"
    )
    needs_recommendation: bool = Field(
        description="Whether to synthesize results with RecommendationAgent at the end"
    )
    rationale: str = Field(description="Why these agents were selected")


class AgentResult(BaseModel):
    agent: AgentName
    output: dict[str, Any]
    success: bool
    error: str | None = None


class WorkflowResult(BaseModel):
    workflow_name: WorkflowName
    ticker: str
    company_name: str | None = None
    user_intent: UserIntent
    selected_agents: list[AgentName] = Field(default_factory=list)
    execution_status: Literal["success", "partial_success", "failed"]
    agent_outputs: list[AgentResult] = Field(default_factory=list)
    missing_data_warnings: list[str] = Field(default_factory=list)
    confidence_summary: str
    final_response_payload: dict[str, Any] = Field(default_factory=dict)


class SupervisorResult(BaseModel):
    ticker: str
    plan: ExecutionPlan
    results: list[AgentResult]

    def get(self, agent: AgentName) -> AgentResult | None:
        return next((r for r in self.results if r.agent == agent), None)
