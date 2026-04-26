from typing import Any, Literal
from pydantic import BaseModel, Field
from models.domain import AgentName, TimeHorizon


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


class SupervisorResult(BaseModel):
    ticker: str
    plan: ExecutionPlan
    results: list[AgentResult]

    def get(self, agent: AgentName) -> AgentResult | None:
        return next((r for r in self.results if r.agent == agent), None)
