import yfinance as yf
import pandas as pd


def fetch_financial_data(ticker: str) -> str:
    """
    Fetch and format the latest financial statements for a ticker.
    Returns a structured text block suitable for LLM analysis.
    """
    t = yf.Ticker(ticker)
    info = t.info or {}
    company_name = info.get("longName", ticker)

    sections = [f"=== {company_name} ({ticker}) — Financial Statements ==="]

    # ── Key metrics ────────────────────────────────────────────────────────────
    _METRIC_KEYS = [
        ("Market Cap",            "marketCap",          "dollar"),
        ("Revenue (TTM)",         "totalRevenue",       "dollar"),
        ("Gross Profit",          "grossProfits",       "dollar"),
        ("EBITDA",                "ebitda",             "dollar"),
        ("Net Income (TTM)",      "netIncomeToCommon",  "dollar"),
        ("Free Cash Flow",        "freeCashflow",       "dollar"),
        ("EPS (TTM)",             "trailingEps",        "plain"),
        ("PE Ratio (TTM)",        "trailingPE",         "plain"),
        ("Forward PE",            "forwardPE",          "plain"),
        ("Revenue Growth (YoY)",  "revenueGrowth",      "pct"),
        ("Earnings Growth (YoY)", "earningsGrowth",     "pct"),
        ("Profit Margin",         "profitMargins",      "pct"),
        ("Operating Margin",      "operatingMargins",   "pct"),
        ("Return on Equity",      "returnOnEquity",     "pct"),
        ("Return on Assets",      "returnOnAssets",     "pct"),
        ("Debt/Equity",           "debtToEquity",       "plain"),
        ("Current Ratio",         "currentRatio",       "plain"),
        ("Cash Per Share",        "totalCashPerShare",  "plain"),
    ]

    km_lines = ["--- Key Metrics ---"]
    for label, key, fmt in _METRIC_KEYS:
        v = info.get(key)
        if v is None:
            continue
        if fmt == "pct":
            km_lines.append(f"{label}: {v:.1%}")
        elif fmt == "dollar":
            if abs(v) >= 1e9:
                km_lines.append(f"{label}: ${v / 1e9:.2f}B")
            else:
                km_lines.append(f"{label}: ${v / 1e6:.2f}M")
        else:
            km_lines.append(f"{label}: {v:.2f}" if isinstance(v, float) else f"{label}: {v}")
    sections.append("\n".join(km_lines))

    # ── Financial statements ───────────────────────────────────────────────────
    _stmts = [
        ("Annual Income Statement",                 lambda: t.income_stmt,             4),
        ("Quarterly Income Statement (last 4Q)",    lambda: t.quarterly_income_stmt,   4),
        ("Annual Balance Sheet",                    lambda: t.balance_sheet,           4),
        ("Annual Cash Flow Statement",              lambda: t.cash_flow,               4),
    ]
    for title, getter, max_cols in _stmts:
        try:
            df = getter()
            sections.append(_format_df(df, title, max_cols))
        except Exception as e:
            sections.append(f"--- {title}: unavailable ({e}) ---")

    return "\n\n".join(sections)


def _format_df(df: pd.DataFrame, title: str, max_cols: int = 4) -> str:
    if df is None or df.empty:
        return f"--- {title}: No data available ---"

    df = df.iloc[:, :max_cols]
    cols = [str(c)[:10] for c in df.columns]

    lines = [f"--- {title} ---", "Metric | " + " | ".join(cols), "-" * 80]
    for row_label, row in df.iterrows():
        values = []
        for v in row.values:
            if pd.isna(v):
                values.append("N/A")
            elif isinstance(v, (int, float)):
                a = abs(v)
                if a >= 1e9:
                    values.append(f"{v / 1e9:.2f}B")
                elif a >= 1e6:
                    values.append(f"{v / 1e6:.2f}M")
                else:
                    values.append(f"{v:.2f}")
            else:
                values.append(str(v))
        lines.append(f"{row_label} | " + " | ".join(values))
    return "\n".join(lines)
