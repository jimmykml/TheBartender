from pydantic import BaseModel, Field
from models.domain import TimeHorizon


class AnalysisRequest(BaseModel):
    ticker: str = Field(description="Stock ticker symbol, e.g. AAPL")
    time_horizon: TimeHorizon = TimeHorizon.BOTH
    focus: str | None = Field(
        default=None,
        description="Optional free-text focus, e.g. 'earnings impact' or 'debt levels'",
    )
