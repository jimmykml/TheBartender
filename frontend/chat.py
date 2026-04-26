import sys
from datetime import date, timedelta
from pathlib import Path

import httpx
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="The Bartender", page_icon="🍸", layout="wide")
st.title("🍸 The Bartender")
st.caption("Your AI-powered stock analysis assistant")

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Analysis Settings")

    mode = st.radio("Mode", ["News", "Fiscal"], horizontal=True)

    ticker = st.text_input("Ticker", placeholder="e.g. NVDA", max_chars=10).upper().strip()

    if mode == "News":
        date_preset = st.selectbox(
            "Date range",
            ["Today", "Last 7 days", "Last 14 days", "Last 30 days", "Custom"],
        )

        today = date.today()
        if date_preset == "Today":
            from_date, to_date = today, today
        elif date_preset == "Last 7 days":
            from_date, to_date = today - timedelta(days=7), today
        elif date_preset == "Last 14 days":
            from_date, to_date = today - timedelta(days=14), today
        elif date_preset == "Last 30 days":
            from_date, to_date = today - timedelta(days=30), today
        else:
            col1, col2 = st.columns(2)
            from_date = col1.date_input("From", today - timedelta(days=7))
            to_date = col2.date_input("To", today)

    run = st.button("Analyze", type="primary", disabled=not ticker)

    st.divider()
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.session_state.report_context = ""
        st.rerun()

# ── Session state ──────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hey! Enter a ticker in the sidebar and hit **Analyze** to get started.",
        }
    ]

if "report_context" not in st.session_state:
    st.session_state.report_context = ""

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Formatters ─────────────────────────────────────────────────────────────────

def _show_usage(usage: dict | None) -> None:
    if not usage:
        return
    model = usage.get("model", "")
    total = usage.get("total_tokens", 0)
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cost = usage.get("cost_display", "?")
    known = usage.get("pricing_known", False)
    cost_str = cost if known else f"{cost} (unknown model pricing)"
    st.caption(f"`{model}` · {inp:,} in / {out:,} out · {total:,} tokens · **{cost_str}**")


def _sentiment_emoji(sentiment: str) -> str:
    return {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}.get(sentiment, "⚪")


def _format_news_result(data: dict) -> str:
    sentiment = data.get("sentiment", "neutral")
    confidence = data.get("confidence", 0)
    summary = data.get("summary", "")
    risks = data.get("key_risks", [])
    opps = data.get("key_opportunities", [])

    lines = [
        f"### {_sentiment_emoji(sentiment)} {data['ticker']} — {sentiment.capitalize()}",
        f"**Confidence:** {confidence:.0%}  |  **Period:** {from_date} → {to_date}",
        "",
        "**Summary**",
        summary,
    ]

    if risks:
        lines += ["", "**Risks**"] + [f"- {r}" for r in risks]
    if opps:
        lines += ["", "**Opportunities**"] + [f"- {o}" for o in opps]

    articles = data.get("key_articles", [])
    if articles:
        lines += ["", "**Key Articles**"]
        for a in articles:
            source = a.get("source", "")
            headline = a.get("headline", "")
            url = a.get("url", "")
            lines.append(f"- [{headline}]({url}) — *{source}*")

    return "\n".join(lines)


def _format_fiscal_result(data: dict) -> str:
    lines = [
        f"### 📊 {data['ticker']} — Fiscal Analysis",
        f"**Period:** {data.get('period', '')}",
        "",
        "**Summary**",
        data.get("summary", ""),
    ]

    metrics = data.get("key_metrics", [])
    if metrics:
        lines += ["", "**Key Metrics**"]
        for m in metrics:
            change = f" *(YoY: {m['change']})*" if m.get("change") else ""
            note = f" — {m['note']}" if m.get("note") else ""
            lines.append(f"- **{m['name']}**: {m['value']}{change}{note}")

    highlights = data.get("highlights", [])
    if highlights:
        lines += ["", "**Highlights ✅**"] + [f"- {h}" for h in highlights]

    concerns = data.get("concerns", [])
    if concerns:
        lines += ["", "**Concerns ⚠️**"] + [f"- {c}" for c in concerns]

    lines += ["", "*Ask me anything about this report below.*"]
    return "\n".join(lines)


# ── Run analysis ───────────────────────────────────────────────────────────────

if run and ticker:
    if mode == "News":
        user_msg = f"Analyze **{ticker}** news from {from_date} to {to_date}"
        st.session_state.messages.append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.markdown(user_msg)

        with st.chat_message("assistant"):
            with st.spinner(f"Fetching and analyzing {ticker} news…"):
                try:
                    response = httpx.post(
                        f"{API_BASE}/api/v1/news",
                        json={
                            "ticker": ticker,
                            "from_date": str(from_date),
                            "to_date": str(to_date),
                        },
                        timeout=120,
                    )
                    response.raise_for_status()
                    body = response.json()
                    result = _format_news_result(body["data"])
                    usage = body.get("usage")
                except httpx.ConnectError:
                    result = "⚠️ Could not connect to the backend. Is the server running?\n```\nuv run uvicorn app.main:app --reload\n```"
                    usage = None
                except httpx.HTTPStatusError as e:
                    result = f"⚠️ API error {e.response.status_code}: {e.response.json().get('detail', str(e))}"
                    usage = None
                except Exception as e:
                    result = f"⚠️ Unexpected error: {e}"
                    usage = None

            st.markdown(result)
            _show_usage(usage)
        st.session_state.messages.append({"role": "assistant", "content": result})

    else:  # Fiscal mode
        user_msg = f"Retrieve and analyze the latest fiscal report for **{ticker}**"
        st.session_state.messages.append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.markdown(user_msg)

        with st.chat_message("assistant"):
            with st.spinner(f"Retrieving financial statements for {ticker}…"):
                try:
                    response = httpx.post(
                        f"{API_BASE}/api/v1/fiscal",
                        json={"ticker": ticker},
                        timeout=120,
                    )
                    response.raise_for_status()
                    body = response.json()
                    data = body["data"]
                    st.session_state.report_context = data.get("report_context", "")
                    result = _format_fiscal_result(data)
                    usage = body.get("usage")
                except httpx.ConnectError:
                    result = "⚠️ Could not connect to the backend. Is the server running?\n```\nuv run uvicorn app.main:app --reload\n```"
                    st.session_state.report_context = ""
                    usage = None
                except httpx.HTTPStatusError as e:
                    result = f"⚠️ API error {e.response.status_code}: {e.response.json().get('detail', str(e))}"
                    st.session_state.report_context = ""
                    usage = None
                except Exception as e:
                    result = f"⚠️ Unexpected error: {e}"
                    st.session_state.report_context = ""
                    usage = None

            st.markdown(result)
            _show_usage(usage)
        st.session_state.messages.append({"role": "assistant", "content": result})

# ── Fiscal Q&A ─────────────────────────────────────────────────────────────────

if mode == "Fiscal" and st.session_state.report_context:
    if question := st.chat_input("Ask a question about the report…"):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                try:
                    response = httpx.post(
                        f"{API_BASE}/api/v1/fiscal/ask",
                        json={
                            "question": question,
                            "report_context": st.session_state.report_context,
                        },
                        timeout=60,
                    )
                    response.raise_for_status()
                    body = response.json()
                    answer = body.get("answer", "")
                    usage = body.get("usage")
                except httpx.HTTPStatusError as e:
                    answer = f"⚠️ API error {e.response.status_code}: {e.response.json().get('detail', str(e))}"
                    usage = None
                except Exception as e:
                    answer = f"⚠️ Unexpected error: {e}"
                    usage = None

            st.markdown(answer)
            _show_usage(usage)
        st.session_state.messages.append({"role": "assistant", "content": answer})
