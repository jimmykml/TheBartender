from datetime import date

from pydantic import BaseModel, Field
from models.domain import TimeHorizon


class AnalysisRequest(BaseModel):
    question: str = Field(
        default="",
        description="Original user question, e.g. 'Should I buy NVDA?'",
    )
    ticker: str = Field(description="Stock ticker symbol, e.g. AAPL")
    time_horizon: TimeHorizon = TimeHorizon.BOTH
    from_date: date | None = Field(
        default=None,
        description="Optional start date for time-windowed analysis such as news",
    )
    to_date: date | None = Field(
        default=None,
        description="Optional end date for time-windowed analysis such as news",
    )
    focus: str | None = Field(
        default=None,
        description="Optional free-text focus, e.g. 'earnings impact' or 'debt levels'",
    )
