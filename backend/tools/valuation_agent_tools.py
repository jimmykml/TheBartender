from __future__ import annotations

from dataclasses import dataclass
from statistics import median

import pandas as pd
import requests
import yfinance as yf


PEER_GROUPS: dict[str, list[str]] = {
    "AAPL": ["MSFT", "GOOGL", "META", "AMZN"],
    "MSFT": ["AAPL", "GOOGL", "ORCL", "CRM"],
    "GOOGL": ["META", "MSFT", "AMZN", "AAPL"],
    "META": ["GOOGL", "SNAP", "PINS", "AAPL"],
    "AMZN": ["WMT", "COST", "BABA", "MELI"],
    "NVDA": ["AMD", "AVGO", "INTC", "QCOM"],
    "AMD": ["NVDA", "INTC", "QCOM", "AVGO"],
    "TSLA": ["GM", "F", "RIVN", "LCID"],
    "JPM": ["BAC", "WFC", "C", "GS"],
    "BAC": ["JPM", "WFC", "C", "MS"],
}

DEFAULT_PEERS = ["SPY", "QQQ"]
DEFAULT_RISK_FREE_RATE = 0.045
DEFAULT_TERMINAL_GROWTH_RATE = 0.025


@dataclass(frozen=True)
class FundamentalSnapshot:
    ticker: str
    company_name: str
    revenue: float
    net_income: float
    operating_cash_flow: float
    capital_expenditures: float
    free_cash_flow: float
    cash_and_equivalents: float
    total_debt: float
    shares_outstanding: float
    current_stock_price: float
    ebitda: float | None
    market_cap: float | None
    enterprise_value: float | None
    historical_fcf: list[float]


@dataclass(frozen=True)
class DCFResult:
    intrinsic_value_per_share: float
    projected_fcf_growth: float
    discount_rate: float
    terminal_growth_rate: float
    enterprise_value: float
    equity_value: float


@dataclass(frozen=True)
class RelativeValuationResult:
    implied_value_per_share: float | None
    peer_tickers: list[str]
    peer_median_pe: float | None
    peer_median_ps: float | None
    peer_median_ev_ebitda: float | None
    method_values: dict[str, float]


@dataclass(frozen=True)
class ReverseDCFResult:
    implied_growth_rate: float | None
    realistic_growth_rate: float
    verdict: str


@dataclass(frozen=True)
class ValuationResult:
    ticker: str
    valuation_view: str
    current_price: float
    intrinsic_value_per_share: float
    margin_of_safety: float
    dcf: DCFResult
    relative: RelativeValuationResult
    reverse_dcf: ReverseDCFResult
    snapshot: FundamentalSnapshot
    risk_free_rate: float


def build_valuation_context(ticker: str) -> str:
    """Fetch data, run deterministic valuation methods, and format for the LLM."""
    result = run_valuation(ticker)
    s = result.snapshot
    dcf = result.dcf
    rel = result.relative
    rev = result.reverse_dcf

    lines = [
        f"=== Valuation for {s.company_name} ({result.ticker}) ===",
        "",
        "--- Required Fundamentals ---",
        f"Revenue: {_fmt_money(s.revenue)}",
        f"Net income: {_fmt_money(s.net_income)}",
        f"Operating cash flow: {_fmt_money(s.operating_cash_flow)}",
        f"Capital expenditures: {_fmt_money(s.capital_expenditures)}",
        f"Free cash flow: {_fmt_money(s.free_cash_flow)}",
        f"Cash and cash equivalents: {_fmt_money(s.cash_and_equivalents)}",
        f"Total debt: {_fmt_money(s.total_debt)}",
        f"Shares outstanding: {_fmt_number(s.shares_outstanding)}",
        f"Current stock price: ${s.current_stock_price:.2f}",
        f"EBITDA: {_fmt_money(s.ebitda)}",
        "",
        "--- DCF ---",
        f"Projected FCF growth: {dcf.projected_fcf_growth:.1%}",
        f"Discount rate: {dcf.discount_rate:.1%}",
        f"Risk-free rate input: {result.risk_free_rate:.1%}",
        f"Terminal growth rate: {dcf.terminal_growth_rate:.1%}",
        f"DCF enterprise value: {_fmt_money(dcf.enterprise_value)}",
        f"DCF equity value: {_fmt_money(dcf.equity_value)}",
        f"DCF intrinsic value per share: ${dcf.intrinsic_value_per_share:.2f}",
        "",
        "--- Relative Valuation ---",
        f"Peers: {', '.join(rel.peer_tickers) or 'None available'}",
        f"Peer median P/E: {_fmt_multiple(rel.peer_median_pe)}",
        f"Peer median P/S: {_fmt_multiple(rel.peer_median_ps)}",
        f"Peer median EV/EBITDA: {_fmt_multiple(rel.peer_median_ev_ebitda)}",
        f"Method values: {_fmt_method_values(rel.method_values)}",
        f"Relative implied value per share: {_fmt_price(rel.implied_value_per_share)}",
        "",
        "--- Reverse DCF ---",
        f"Growth implied by current price: {_fmt_pct(rev.implied_growth_rate)}",
        f"Realistic growth estimate: {rev.realistic_growth_rate:.1%}",
        f"Reverse DCF verdict: {rev.verdict}",
        "",
        "--- Final Deterministic View ---",
        f"Blended intrinsic value per share: ${result.intrinsic_value_per_share:.2f}",
        f"Current price: ${result.current_price:.2f}",
        f"Margin of safety: {result.margin_of_safety:.1%}",
        f"Valuation view: {result.valuation_view}",
    ]
    return "\n".join(lines)


def run_valuation(ticker: str) -> ValuationResult:
    snapshot = fetch_fundamental_snapshot(ticker)
    risk_free_rate = fetch_risk_free_rate()
    growth_rate = estimate_fcf_growth(snapshot.historical_fcf)
    discount_rate = min(0.12, max(0.08, risk_free_rate + 0.055))

    dcf = calculate_dcf(
        snapshot=snapshot,
        projected_growth=growth_rate,
        discount_rate=discount_rate,
        terminal_growth_rate=DEFAULT_TERMINAL_GROWTH_RATE,
    )
    relative = calculate_relative_valuation(snapshot)
    reverse = calculate_reverse_dcf(
        snapshot=snapshot,
        discount_rate=discount_rate,
        terminal_growth_rate=DEFAULT_TERMINAL_GROWTH_RATE,
        realistic_growth_rate=growth_rate,
    )

    values = [dcf.intrinsic_value_per_share]
    if relative.implied_value_per_share is not None:
        values.append(relative.implied_value_per_share)
    intrinsic = sum(values) / len(values)
    margin = (intrinsic - snapshot.current_stock_price) / snapshot.current_stock_price
    view = classify_valuation(margin)

    return ValuationResult(
        ticker=snapshot.ticker,
        valuation_view=view,
        current_price=snapshot.current_stock_price,
        intrinsic_value_per_share=intrinsic,
        margin_of_safety=margin,
        dcf=dcf,
        relative=relative,
        reverse_dcf=reverse,
        snapshot=snapshot,
        risk_free_rate=risk_free_rate,
    )


def fetch_fundamental_snapshot(ticker: str) -> FundamentalSnapshot:
    t = yf.Ticker(ticker)
    info = t.info or {}
    income = t.financials
    cash_flow = t.cashflow
    balance = t.balance_sheet

    revenue = _latest_statement_value(income, ["Total Revenue", "Operating Revenue"])
    net_income = _latest_statement_value(income, ["Net Income", "Net Income Common Stockholders"])
    operating_cash_flow = _latest_statement_value(cash_flow, ["Operating Cash Flow", "Total Cash From Operating Activities"])
    capex = abs(_latest_statement_value(cash_flow, ["Capital Expenditure", "Capital Expenditures"]))
    free_cash_flow = operating_cash_flow - capex
    if free_cash_flow == 0:
        free_cash_flow = float(info.get("freeCashflow") or 0)

    cash = _latest_statement_value(
        balance,
        ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    )
    debt = _latest_statement_value(balance, ["Total Debt"])
    if debt == 0:
        debt = _latest_statement_value(balance, ["Long Term Debt"]) + _latest_statement_value(
            balance, ["Current Debt", "Short Long Term Debt"]
        )

    price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
    shares = float(info.get("sharesOutstanding") or 0)
    if price <= 0 or shares <= 0:
        raise ValueError(f"Missing current price or shares outstanding for {ticker.upper()}")
    if free_cash_flow <= 0:
        raise ValueError(f"Free cash flow is not positive for {ticker.upper()}; DCF unavailable")

    historical_fcf = _historical_fcf(cash_flow)
    if not historical_fcf:
        historical_fcf = [free_cash_flow]

    return FundamentalSnapshot(
        ticker=ticker.upper(),
        company_name=info.get("longName") or info.get("shortName") or ticker.upper(),
        revenue=revenue or float(info.get("totalRevenue") or 0),
        net_income=net_income or float(info.get("netIncomeToCommon") or 0),
        operating_cash_flow=operating_cash_flow,
        capital_expenditures=capex,
        free_cash_flow=free_cash_flow,
        cash_and_equivalents=cash,
        total_debt=debt,
        shares_outstanding=shares,
        current_stock_price=price,
        ebitda=float(info["ebitda"]) if info.get("ebitda") else None,
        market_cap=float(info["marketCap"]) if info.get("marketCap") else price * shares,
        enterprise_value=float(info["enterpriseValue"]) if info.get("enterpriseValue") else None,
        historical_fcf=historical_fcf,
    )


def calculate_dcf(
    snapshot: FundamentalSnapshot,
    projected_growth: float,
    discount_rate: float,
    terminal_growth_rate: float,
    years: int = 5,
) -> DCFResult:
    projected_fcfs = [
        snapshot.free_cash_flow * ((1 + projected_growth) ** year)
        for year in range(1, years + 1)
    ]
    discounted_fcfs = [
        fcf / ((1 + discount_rate) ** year)
        for year, fcf in enumerate(projected_fcfs, start=1)
    ]
    terminal_fcf = projected_fcfs[-1] * (1 + terminal_growth_rate)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth_rate)
    discounted_terminal_value = terminal_value / ((1 + discount_rate) ** years)
    enterprise_value = sum(discounted_fcfs) + discounted_terminal_value
    equity_value = enterprise_value + snapshot.cash_and_equivalents - snapshot.total_debt
    intrinsic = equity_value / snapshot.shares_outstanding

    return DCFResult(
        intrinsic_value_per_share=intrinsic,
        projected_fcf_growth=projected_growth,
        discount_rate=discount_rate,
        terminal_growth_rate=terminal_growth_rate,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
    )


def calculate_relative_valuation(snapshot: FundamentalSnapshot) -> RelativeValuationResult:
    peers = PEER_GROUPS.get(snapshot.ticker, DEFAULT_PEERS)
    pe_values: list[float] = []
    ps_values: list[float] = []
    ev_ebitda_values: list[float] = []
    usable_peers: list[str] = []

    for peer in peers:
        try:
            info = yf.Ticker(peer).info or {}
        except Exception:
            continue
        if info.get("trailingPE"):
            pe_values.append(float(info["trailingPE"]))
        if info.get("priceToSalesTrailing12Months"):
            ps_values.append(float(info["priceToSalesTrailing12Months"]))
        if info.get("enterpriseToEbitda"):
            ev_ebitda_values.append(float(info["enterpriseToEbitda"]))
        usable_peers.append(peer)

    median_pe = _median_or_none(pe_values)
    median_ps = _median_or_none(ps_values)
    median_ev_ebitda = _median_or_none(ev_ebitda_values)

    method_values: dict[str, float] = {}
    eps = snapshot.net_income / snapshot.shares_outstanding if snapshot.net_income else None
    sales_per_share = snapshot.revenue / snapshot.shares_outstanding if snapshot.revenue else None

    if median_pe is not None and eps and eps > 0:
        method_values["pe"] = median_pe * eps
    if median_ps is not None and sales_per_share and sales_per_share > 0:
        method_values["ps"] = median_ps * sales_per_share
    if median_ev_ebitda is not None and snapshot.ebitda and snapshot.ebitda > 0:
        implied_ev = median_ev_ebitda * snapshot.ebitda
        method_values["ev_ebitda"] = (
            implied_ev + snapshot.cash_and_equivalents - snapshot.total_debt
        ) / snapshot.shares_outstanding

    implied = sum(method_values.values()) / len(method_values) if method_values else None

    return RelativeValuationResult(
        implied_value_per_share=implied,
        peer_tickers=usable_peers,
        peer_median_pe=median_pe,
        peer_median_ps=median_ps,
        peer_median_ev_ebitda=median_ev_ebitda,
        method_values=method_values,
    )


def calculate_reverse_dcf(
    snapshot: FundamentalSnapshot,
    discount_rate: float,
    terminal_growth_rate: float,
    realistic_growth_rate: float,
) -> ReverseDCFResult:
    target_equity_value = snapshot.current_stock_price * snapshot.shares_outstanding
    target_enterprise_value = target_equity_value - snapshot.cash_and_equivalents + snapshot.total_debt

    low = -0.20
    high = 0.30
    for _ in range(80):
        mid = (low + high) / 2
        ev = _dcf_enterprise_value(snapshot.free_cash_flow, mid, discount_rate, terminal_growth_rate)
        if ev < target_enterprise_value:
            low = mid
        else:
            high = mid
    implied = (low + high) / 2

    if implied <= realistic_growth_rate:
        verdict = "conservative"
    elif implied <= realistic_growth_rate + 0.03:
        verdict = "reasonable"
    else:
        verdict = "aggressive"

    return ReverseDCFResult(
        implied_growth_rate=implied,
        realistic_growth_rate=realistic_growth_rate,
        verdict=verdict,
    )


def estimate_fcf_growth(historical_fcf: list[float]) -> float:
    positive = [v for v in historical_fcf if v > 0]
    if len(positive) < 2:
        return 0.04
    oldest = positive[-1]
    newest = positive[0]
    periods = len(positive) - 1
    growth = (newest / oldest) ** (1 / periods) - 1
    return min(0.15, max(-0.05, growth))


def classify_valuation(margin_of_safety: float) -> str:
    if margin_of_safety >= 0.15:
        return "undervalued"
    if margin_of_safety <= -0.15:
        return "overvalued"
    return "fairly_valued"


def fetch_risk_free_rate() -> float:
    """Fetch latest 10-year Treasury yield from FRED, falling back for offline use."""
    try:
        response = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
            timeout=5,
        )
        response.raise_for_status()
        for line in reversed(response.text.strip().splitlines()[1:]):
            _, value = line.split(",", 1)
            if value != ".":
                return float(value) / 100
    except Exception:
        return DEFAULT_RISK_FREE_RATE
    return DEFAULT_RISK_FREE_RATE


def _historical_fcf(cash_flow: pd.DataFrame) -> list[float]:
    ocf = _statement_series(cash_flow, ["Operating Cash Flow", "Total Cash From Operating Activities"])
    capex = _statement_series(cash_flow, ["Capital Expenditure", "Capital Expenditures"])
    if ocf is None or capex is None:
        return []
    values: list[float] = []
    for ocf_value, capex_value in zip(ocf, capex, strict=False):
        if pd.isna(ocf_value) or pd.isna(capex_value):
            continue
        values.append(float(ocf_value) - abs(float(capex_value)))
    return values


def _latest_statement_value(df: pd.DataFrame, labels: list[str]) -> float:
    series = _statement_series(df, labels)
    if series is None or series.empty:
        return 0.0
    value = series.dropna().iloc[0] if not series.dropna().empty else 0
    return float(value)


def _statement_series(df: pd.DataFrame, labels: list[str]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    for label in labels:
        if label in df.index:
            return df.loc[label]
    return None


def _dcf_enterprise_value(
    current_fcf: float,
    growth: float,
    discount_rate: float,
    terminal_growth_rate: float,
    years: int = 5,
) -> float:
    projected_fcfs = [current_fcf * ((1 + growth) ** year) for year in range(1, years + 1)]
    discounted_fcfs = [
        fcf / ((1 + discount_rate) ** year)
        for year, fcf in enumerate(projected_fcfs, start=1)
    ]
    terminal_value = projected_fcfs[-1] * (1 + terminal_growth_rate) / (
        discount_rate - terminal_growth_rate
    )
    return sum(discounted_fcfs) + terminal_value / ((1 + discount_rate) ** years)


def _median_or_none(values: list[float]) -> float | None:
    return median(values) if values else None


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "N/A"
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1e12:
        return f"{sign}${value / 1e12:.2f}T"
    if value >= 1e9:
        return f"{sign}${value / 1e9:.2f}B"
    if value >= 1e6:
        return f"{sign}${value / 1e6:.2f}M"
    return f"{sign}${value:,.0f}"


def _fmt_number(value: float) -> str:
    if value >= 1e9:
        return f"{value / 1e9:.2f}B"
    if value >= 1e6:
        return f"{value / 1e6:.2f}M"
    return f"{value:,.0f}"


def _fmt_multiple(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1f}x"


def _fmt_price(value: float | None) -> str:
    return "N/A" if value is None else f"${value:.2f}"


def _fmt_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1%}"


def _fmt_method_values(values: dict[str, float]) -> str:
    if not values:
        return "N/A"
    return ", ".join(f"{name}={_fmt_price(value)}" for name, value in values.items())
