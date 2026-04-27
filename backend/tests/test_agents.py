import pytest

from tools.valuation_agent_tools import (
    FundamentalSnapshot,
    calculate_dcf,
    calculate_reverse_dcf,
    classify_valuation,
    estimate_fcf_growth,
)
from agents.supervisor_agent import SupervisorAgent
from models.domain import UserIntent
from models.requests import AnalysisRequest


def _sample_snapshot() -> FundamentalSnapshot:
    return FundamentalSnapshot(
        ticker="TEST",
        company_name="Test Co",
        revenue=100_000_000_000,
        net_income=12_000_000_000,
        operating_cash_flow=18_000_000_000,
        capital_expenditures=4_000_000_000,
        free_cash_flow=14_000_000_000,
        cash_and_equivalents=20_000_000_000,
        total_debt=10_000_000_000,
        shares_outstanding=1_000_000_000,
        current_stock_price=150,
        ebitda=20_000_000_000,
        market_cap=150_000_000_000,
        enterprise_value=140_000_000_000,
        historical_fcf=[14_000_000_000, 12_000_000_000, 10_000_000_000],
    )


def test_dcf_outputs_intrinsic_value_per_share():
    result = calculate_dcf(
        snapshot=_sample_snapshot(),
        projected_growth=0.06,
        discount_rate=0.10,
        terminal_growth_rate=0.025,
    )

    assert result.enterprise_value > 0
    assert result.equity_value > result.enterprise_value
    assert result.intrinsic_value_per_share > 0


@pytest.mark.parametrize(
    ("margin", "expected"),
    [
        (0.20, "undervalued"),
        (0.05, "fairly_valued"),
        (-0.20, "overvalued"),
    ],
)
def test_classify_valuation(margin: float, expected: str):
    assert classify_valuation(margin) == expected


def test_estimate_fcf_growth_is_capped():
    assert estimate_fcf_growth([400, 100]) == 0.15
    assert estimate_fcf_growth([100, 400]) == -0.05


def test_reverse_dcf_returns_implied_growth():
    result = calculate_reverse_dcf(
        snapshot=_sample_snapshot(),
        discount_rate=0.10,
        terminal_growth_rate=0.025,
        realistic_growth_rate=0.06,
    )

    assert result.implied_growth_rate is not None
    assert -0.20 <= result.implied_growth_rate <= 0.30
    assert result.verdict in {"conservative", "reasonable", "aggressive"}


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Should I buy NVDA after earnings?", UserIntent.RECOMMENDATION),
        ("Why did NVDA drop yesterday?", UserIntent.DRIVER),
        ("Is AAPL undervalued?", UserIntent.VALUATION),
        ("Analyze AVGO earnings.", UserIntent.FISCAL),
        ("Any recent news about AAPL?", UserIntent.NEWS),
    ],
)
def test_supervisor_routes_to_fixed_workflow_intent(question: str, expected: UserIntent):
    supervisor = SupervisorAgent.__new__(SupervisorAgent)

    assert supervisor._detect_intent(AnalysisRequest(ticker="NVDA", question=question)) == expected
