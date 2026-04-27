import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

API_BASE = os.getenv("BARTENDER_API_BASE", "http://localhost:8000")

STOP_TICKERS = {
    "A",
    "AN",
    "ANY",
    "ARE",
    "AS",
    "BUY",
    "CEO",
    "DCF",
    "DID",
    "EPS",
    "ETF",
    "FCF",
    "FOR",
    "GDP",
    "HOLD",
    "HOW",
    "IPO",
    "IS",
    "IT",
    "NEWS",
    "ON",
    "OR",
    "PE",
    "PS",
    "Q",
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "ROE",
    "SEC",
    "SELL",
    "THE",
    "TO",
    "US",
    "USD",
    "WHAT",
    "WHY",
}

EXAMPLE_PROMPTS = [
    "Should I buy NVDA?",
    "Is AAPL undervalued?",
    "Any recent news about AVGO this week?",
    "Summarize TSLA latest fiscal report.",
]


st.set_page_config(page_title="The Bartender", page_icon="🍸", layout="wide")


def _init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Ask me about a stock by ticker, like `Should I buy NVDA?` "
                    "or choose a ticker in the sidebar and ask naturally."
                ),
            }
        ]
    st.session_state.setdefault("active_ticker", "")
    st.session_state.setdefault("active_horizon", "both")
    st.session_state.setdefault("active_from_date", str(date.today() - timedelta(days=7)))
    st.session_state.setdefault("active_to_date", str(date.today()))
    st.session_state.setdefault("last_workflow_context", "")


def _date_range_from_preset(preset: str) -> tuple[date, date]:
    today = date.today()
    if preset == "Today":
        return today, today
    if preset == "Last 14 days":
        return today - timedelta(days=14), today
    if preset == "Last 30 days":
        return today - timedelta(days=30), today
    return today - timedelta(days=7), today


def _extract_ticker(text: str, fallback: str = "") -> str:
    for raw in re.findall(r"\b\$?[A-Za-z]{2,5}(?:\.[A-Za-z])?\b", text):
        ticker = raw.replace("$", "").upper()
        if ticker not in STOP_TICKERS and not ticker.startswith("Q"):
            return ticker
    return fallback.upper().strip()


def _show_usage(usage: Any) -> None:
    if not usage:
        return
    if isinstance(usage, list):
        total_tokens = sum(item.get("total_tokens", 0) for item in usage)
        total_cost = sum(item.get("cost_usd", 0) for item in usage)
        st.caption(f"{len(usage)} LLM calls · {total_tokens:,} tokens · **${total_cost:.4f}**")
        return
    model = usage.get("model", "")
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    total = usage.get("total_tokens", 0)
    cost = usage.get("cost_display", "?")
    known = usage.get("pricing_known", False)
    cost_str = cost if known else f"{cost} (model pricing unknown)"
    st.caption(f"`{model}` · {inp:,} in / {out:,} out · {total:,} tokens · **{cost_str}**")


def _sentiment_marker(sentiment: str) -> str:
    return {"bullish": "Bullish", "bearish": "Bearish", "neutral": "Neutral"}.get(
        sentiment, "Mixed"
    )


def _format_news_result(data: dict, from_d: date, to_d: date) -> str:
    sentiment = data.get("sentiment", "neutral")
    confidence = data.get("confidence", 0)
    lines = [
        f"### News: {data.get('ticker', '')} · {_sentiment_marker(sentiment)}",
        f"**Confidence:** {confidence:.0%}  |  **Period:** {from_d} to {to_d}",
        "",
        data.get("summary", ""),
    ]
    risks = data.get("key_risks", [])
    if risks:
        lines += ["", "**Risks**"] + [f"- {r}" for r in risks]
    opportunities = data.get("key_opportunities", [])
    if opportunities:
        lines += ["", "**Opportunities**"] + [f"- {o}" for o in opportunities]
    articles = data.get("key_articles", [])
    if articles:
        lines += ["", "**Key Articles**"]
        for article in articles:
            lines.append(
                f"- [{article.get('headline', '')}]({article.get('url', '')})"
                f" · {article.get('source', '')}"
            )
    return "\n".join(lines)


def _format_fiscal_result(data: dict) -> str:
    lines = [
        f"### Fiscal: {data.get('ticker', '')}",
        f"**Period:** {data.get('period', '')}",
        "",
        data.get("summary", ""),
    ]
    metrics = data.get("key_metrics", [])
    if metrics:
        lines += ["", "**Key Metrics**"]
        for metric in metrics:
            change = f" ({metric['change']})" if metric.get("change") else ""
            note = f" · {metric['note']}" if metric.get("note") else ""
            lines.append(f"- **{metric['name']}**: {metric['value']}{change}{note}")
    highlights = data.get("highlights", [])
    if highlights:
        lines += ["", "**Highlights**"] + [f"- {h}" for h in highlights]
    concerns = data.get("concerns", [])
    if concerns:
        lines += ["", "**Concerns**"] + [f"- {c}" for c in concerns]
    return "\n".join(lines)


def _pct(v: float | None) -> str:
    return "N/A" if v is None else f"{v:.1%}"


def _price(v: float | None) -> str:
    return "N/A" if v is None else f"${v:.2f}"


def _fmt_large(v: float | None) -> str:
    if v is None:
        return "N/A"
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1e12:
        return f"{sign}${v / 1e12:.2f}T"
    if v >= 1e9:
        return f"{sign}${v / 1e9:.2f}B"
    if v >= 1e6:
        return f"{sign}${v / 1e6:.2f}M"
    return f"{sign}${v:,.0f}"


def _format_valuation_result(data: dict) -> str:
    view = data.get("valuation_view", "fairly_valued").replace("_", " ")
    lines = [
        f"### Valuation: {data.get('ticker', '')} · {view.title()}",
        f"**Current price:** {_price(data.get('current_price'))}  |  "
        f"**Intrinsic value:** {_price(data.get('intrinsic_value_per_share'))}  |  "
        f"**Margin of safety:** {data.get('margin_of_safety', 0):.0%}",
        "",
        data.get("summary", ""),
    ]

    dcf = data.get("dcf") or {}
    if dcf:
        lines += [
            "",
            "**DCF Model**",
            "| Parameter | Value |",
            "|---|---|",
            f"| FCF growth assumption | {_pct(dcf.get('projected_fcf_growth'))} |",
            f"| Discount rate | {_pct(dcf.get('discount_rate'))} |",
            f"| Terminal growth rate | {_pct(dcf.get('terminal_growth_rate'))} |",
            f"| DCF enterprise value | {_fmt_large(dcf.get('enterprise_value'))} |",
            f"| DCF equity value | {_fmt_large(dcf.get('equity_value'))} |",
            f"| DCF intrinsic value/share | {_price(dcf.get('intrinsic_value_per_share'))} |",
        ]

    rel = data.get("relative") or {}
    if rel:
        method_values = rel.get("method_values") or {}
        pe = f"{rel['peer_median_pe']:.1f}x" if rel.get("peer_median_pe") else "N/A"
        ps = f"{rel['peer_median_ps']:.1f}x" if rel.get("peer_median_ps") else "N/A"
        ev_ebitda = f"{rel['peer_median_ev_ebitda']:.1f}x" if rel.get("peer_median_ev_ebitda") else "N/A"
        lines += [
            "",
            "**Relative Valuation**",
            "| Metric | Value |",
            "|---|---|",
            f"| Peers | {', '.join(rel.get('peer_tickers') or []) or 'N/A'} |",
            f"| Peer median P/E | {pe} |",
            f"| Peer median P/S | {ps} |",
            f"| Peer median EV/EBITDA | {ev_ebitda} |",
        ]
        for method, val in method_values.items():
            lines.append(f"| Implied value ({method.upper()}) | {_price(val)} |")
        if rel.get("implied_value_per_share") is not None:
            lines.append(f"| **Blended relative value/share** | **{_price(rel.get('implied_value_per_share'))}** |")

    rev = data.get("reverse_dcf") or {}
    if rev:
        lines += [
            "",
            "**Reverse DCF**",
            "| Metric | Value |",
            "|---|---|",
            f"| Growth implied by current price | {_pct(rev.get('implied_growth_rate'))} |",
            f"| Realistic growth estimate | {_pct(rev.get('realistic_growth_rate'))} |",
            f"| Verdict | {rev.get('verdict', 'N/A').title()} |",
        ]

    assumptions = data.get("key_assumptions", [])
    if assumptions:
        lines += ["", "**Key Assumptions**"] + [f"- {a}" for a in assumptions]
    risks = data.get("key_risks", [])
    if risks:
        lines += ["", "**Valuation Risks**"] + [f"- {r}" for r in risks]
    return "\n".join(lines)


def _format_driver_result(data: dict) -> str:
    change = data.get("price_change_pct", 0)
    conf = data.get("confidence", 0)
    lines = [
        f"### Price Driver: {data.get('ticker', '')} · {data.get('period', '')}",
        f"**Price change:** {change:+.2%}  |  **Confidence:** {conf:.0%}",
        f"**Primary driver:** {data.get('primary_driver', 'N/A')}",
        "",
        data.get("summary", ""),
    ]
    fundamental = data.get("fundamental_factors", [])
    if fundamental:
        lines += ["", "**Fundamental Factors**"] + [f"- {f}" for f in fundamental]
    technical = data.get("technical_factors", [])
    if technical:
        lines += ["", "**Technical Factors**"] + [f"- {t}" for t in technical]
    macro = data.get("macro_factors", [])
    if macro:
        lines += ["", "**Macro / Market Factors**"] + [f"- {m}" for m in macro]
    return "\n".join(lines)


def _format_recommendation_result(data: dict) -> str:
    action = data.get("action", "hold").upper()
    st = data.get("short_term_verdict", "hold").upper()
    lt = data.get("long_term_verdict", "hold").upper()
    conf = data.get("confidence", 0)
    score = data.get("composite_score", 0)
    lines = [
        f"### Recommendation: {data.get('ticker', '')} · **{action}**",
        f"**Short-term:** {st}  |  **Long-term:** {lt}  |  "
        f"**Confidence:** {conf:.0%}  |  **Composite score:** {score:+.3f}",
        "",
        data.get("rationale", ""),
    ]
    scores = data.get("scores", [])
    if scores:
        lines += ["", "**Component Scores**", "| Factor | Score | Weight | Note |", "|---|---|---|---|"]
        for s in scores:
            lines.append(
                f"| {s['component']} | {s['score']:+.2f} | {s['weight']:.0%} | {s['note']} |"
            )
    bull = data.get("bull_case", [])
    if bull:
        lines += ["", "**Bull Case**"] + [f"- {b}" for b in bull]
    bear = data.get("bear_case", [])
    if bear:
        lines += ["", "**Bear Case**"] + [f"- {b}" for b in bear]
    catalysts = data.get("key_catalysts", [])
    if catalysts:
        lines += ["", "**Key Catalysts**"] + [f"- {c}" for c in catalysts]
    risks = data.get("risk_factors", [])
    if risks:
        lines += ["", "**Risk Factors**"] + [f"- {r}" for r in risks]
    return "\n".join(lines)


def _format_workflow_result(data: dict, from_d: date, to_d: date) -> str:
    workflow = data.get("workflow_name", "workflow").replace("_", " ").title()
    status = data.get("execution_status", "")
    intent = data.get("user_intent", "")
    agents = ", ".join(data.get("selected_agents", [])) or "none"
    lines = [
        f"## {data.get('ticker', '')} · {workflow}",
        f"**Intent:** {intent}  |  **Status:** {status}  |  **Agents:** {agents}",
        f"**Confidence:** {data.get('confidence_summary', '')}",
    ]

    warnings = data.get("missing_data_warnings", [])
    if warnings:
        lines += ["", "**Limitations**"] + [f"- {warning}" for warning in warnings]

    for item in data.get("agent_outputs", []):
        agent_name = item.get("agent")
        if not item.get("success"):
            lines += ["", f"### {agent_name} unavailable", item.get("error", "Unknown error")]
            continue
        output = item.get("output", {})
        if agent_name == "news":
            lines += ["", _format_news_result(output, from_d, to_d)]
        elif agent_name == "fiscal":
            lines += ["", _format_fiscal_result(output)]
        elif agent_name == "valuation":
            lines += ["", _format_valuation_result(output)]
        elif agent_name == "driver":
            lines += ["", _format_driver_result(output)]
        elif agent_name == "recommendation":
            lines += ["", _format_recommendation_result(output)]
        else:
            lines += ["", f"### {agent_name}", "```text", str(output), "```"]

    return "\n".join(lines)


def _build_context(data: dict) -> str:
    lines = [
        f"Ticker: {data.get('ticker', '')}",
        f"Workflow: {data.get('workflow_name', '')}",
        f"Intent: {data.get('user_intent', '')}",
        f"Status: {data.get('execution_status', '')}",
        f"Confidence: {data.get('confidence_summary', '')}",
    ]
    warnings = data.get("missing_data_warnings", [])
    if warnings:
        lines.append(f"Warnings: {warnings}")
    for item in data.get("agent_outputs", []):
        lines.append(f"[{item.get('agent')}] success={item.get('success')}")
        lines.append(str(item.get("output") or item.get("error") or ""))
    return "\n\n".join(lines)


def _call_analyze(question: str, ticker: str, horizon: str, from_d: date, to_d: date) -> tuple[str, Any]:
    response = httpx.post(
        f"{API_BASE}/api/v1/analyze",
        json={
            "question": question,
            "ticker": ticker,
            "time_horizon": horizon,
            "from_date": str(from_d),
            "to_date": str(to_d),
            "focus": question,
        },
        timeout=180,
    )
    response.raise_for_status()
    body = response.json()
    data = body["data"]
    st.session_state.active_ticker = data.get("ticker", ticker)
    st.session_state.active_horizon = horizon
    st.session_state.active_from_date = str(from_d)
    st.session_state.active_to_date = str(to_d)
    st.session_state.last_workflow_context = _build_context(data)
    return _format_workflow_result(data, from_d, to_d), body.get("usage")


def _submit(question: str, sidebar_ticker: str, horizon: str, from_d: date, to_d: date) -> None:
    # Pass sidebar/active ticker only as a hint; the supervisor extracts the real ticker from the question.
    ticker_hint = sidebar_ticker or st.session_state.active_ticker
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing your question..."):
            try:
                answer, usage = _call_analyze(question, ticker_hint, horizon, from_d, to_d)
            except httpx.ConnectError:
                answer = (
                    "I could not connect to the backend. Start it with:\n\n"
                    "```bash\nuv run uvicorn app.main:app --reload\n```"
                )
                usage = None
            except httpx.HTTPStatusError as exc:
                try:
                    detail = exc.response.json().get("detail", str(exc))
                except Exception:
                    detail = str(exc)
                answer = f"API error {exc.response.status_code}: {detail}"
                usage = None
            except Exception as exc:
                answer = f"Unexpected error: {exc}"
                usage = None

        st.markdown(answer)
        _show_usage(usage)
    st.session_state.messages.append({"role": "assistant", "content": answer})


_init_state()

st.title("The Bartender")
st.caption("Chat-first stock analysis with fixed supervisor workflows.")

with st.sidebar:
    st.header("Context")
    sidebar_ticker = st.text_input(
        "Ticker",
        value=st.session_state.active_ticker,
        placeholder="NVDA",
        max_chars=10,
    ).upper().strip()
    if sidebar_ticker:
        st.session_state.active_ticker = sidebar_ticker

    horizon = st.selectbox(
        "Horizon",
        ["both", "short_term", "long_term"],
        index=["both", "short_term", "long_term"].index(st.session_state.active_horizon),
        format_func=lambda value: {
            "both": "Both",
            "short_term": "Short term",
            "long_term": "Long term",
        }[value],
    )

    preset = st.selectbox("News window", ["Last 7 days", "Today", "Last 14 days", "Last 30 days", "Custom"])
    if preset == "Custom":
        default_from = date.fromisoformat(st.session_state.active_from_date)
        default_to = date.fromisoformat(st.session_state.active_to_date)
        col1, col2 = st.columns(2)
        from_date = col1.date_input("From", default_from)
        to_date = col2.date_input("To", default_to)
    else:
        from_date, to_date = _date_range_from_preset(preset)

    st.session_state.active_horizon = horizon
    st.session_state.active_from_date = str(from_date)
    st.session_state.active_to_date = str(to_date)

    st.divider()
    st.caption("Try one")
    for idx, prompt in enumerate(EXAMPLE_PROMPTS):
        if st.button(prompt, key=f"example_{idx}", use_container_width=True):
            st.session_state.pending_prompt = prompt

    st.divider()
    if st.button("Clear conversation", use_container_width=True):
        for key in ["messages", "last_workflow_context", "pending_prompt"]:
            st.session_state.pop(key, None)
        st.rerun()

active = st.session_state.active_ticker or "No ticker selected"
st.markdown(f"**Active context:** `{active}` · `{horizon}` · `{from_date}` to `{to_date}`")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_prompt = st.session_state.pop("pending_prompt", None)
chat_prompt = st.chat_input("Ask about a stock, e.g. Should I buy NVDA?")
prompt = user_prompt or chat_prompt

if prompt:
    _submit(prompt, sidebar_ticker, horizon, from_date, to_date)
