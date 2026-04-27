from enum import StrEnum


class AgentName(StrEnum):
    NEWS = "news"
    DRIVER = "driver"
    FISCAL = "fiscal"
    VALUATION = "valuation"
    RECOMMENDATION = "recommendation"


class TimeHorizon(StrEnum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    BOTH = "both"


class UserIntent(StrEnum):
    NEWS = "news"
    FISCAL = "fiscal"
    VALUATION = "valuation"
    DRIVER = "driver"
    RECOMMENDATION = "recommendation"


class WorkflowName(StrEnum):
    NEWS = "news_workflow"
    FISCAL = "fiscal_workflow"
    VALUATION = "valuation_workflow"
    DRIVER = "driver_workflow"
    RECOMMENDATION = "recommendation_workflow"
