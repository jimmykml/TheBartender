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
