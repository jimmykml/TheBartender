from __future__ import annotations

from models.outputs import ScoreComponent


def compute_recommendation_scores(
    valuation: dict | None,
    fiscal: dict | None,
    news: dict | None,
) -> tuple[list[ScoreComponent], float]:
    """
    Deterministic scoring layer.
    Returns (scores, composite) where composite is a weighted sum in [-1, +1].
    """
    v = valuation or {}
    f = fiscal or {}
    n = news or {}

    val_score, val_note = _score_valuation(v)
    fiscal_score, fiscal_note = _score_fiscal(f)
    news_score, news_note = _score_news(n)
    rev_score, rev_note = _score_reverse_dcf(v)

    scores = [
        ScoreComponent(component="valuation",      score=val_score,    weight=0.35, note=val_note),
        ScoreComponent(component="fundamentals",   score=fiscal_score, weight=0.25, note=fiscal_note),
        ScoreComponent(component="news_sentiment", score=news_score,   weight=0.20, note=news_note),
        ScoreComponent(component="reverse_dcf",    score=rev_score,    weight=0.20, note=rev_note),
    ]
    composite = round(sum(s.score * s.weight for s in scores), 4)
    return scores, composite


def build_recommendation_context(
    ticker: str,
    news: dict | None,
    fiscal: dict | None,
    valuation: dict | None,
    driver: dict | None,
    scores: list[ScoreComponent],
    composite_score: float,
) -> str:
    lines = [f"=== Recommendation Context: {ticker} ===", ""]

    if valuation:
        mos = valuation.get("margin_of_safety", 0)
        lines += [
            "--- Valuation ---",
            f"View: {valuation.get('valuation_view', 'N/A')}",
            f"Current price: ${valuation.get('current_price', 0):.2f}  |  "
            f"Intrinsic value: ${valuation.get('intrinsic_value_per_share', 0):.2f}  |  "
            f"Margin of safety: {mos:.1%}",
            f"Summary: {valuation.get('summary', '')}",
        ]
        rev = valuation.get("reverse_dcf") or {}
        if rev.get("verdict"):
            lines.append(
                f"Reverse DCF: implied growth {rev.get('implied_growth_rate', 0):.1%} "
                f"vs realistic {rev.get('realistic_growth_rate', 0):.1%} — verdict: {rev['verdict']}"
            )
        lines.append("")

    if fiscal:
        lines += [
            "--- Fundamentals ---",
            f"Period: {fiscal.get('period', 'N/A')}",
            f"Summary: {fiscal.get('summary', '')}",
            f"Highlights: {'; '.join(fiscal.get('highlights', [])) or 'None'}",
            f"Concerns: {'; '.join(fiscal.get('concerns', [])) or 'None'}",
            "",
        ]

    if news:
        conf = news.get("confidence", 0)
        lines += [
            "--- News ---",
            f"Sentiment: {news.get('sentiment', 'N/A')} (confidence: {conf:.0%})",
            f"Summary: {news.get('summary', '')}",
            f"Key risks: {'; '.join(news.get('key_risks', [])) or 'None'}",
            f"Key opportunities: {'; '.join(news.get('key_opportunities', [])) or 'None'}",
            "",
        ]

    if driver:
        lines += [
            "--- Recent Price Driver ---",
            f"Period: {driver.get('period', 'N/A')}  |  "
            f"Change: {driver.get('price_change_pct', 0):+.2%}",
            f"Primary driver: {driver.get('primary_driver', 'N/A')}",
            f"Summary: {driver.get('summary', '')}",
            "",
        ]

    lines += [
        "--- Deterministic Scores ---",
        f"Composite: {composite_score:+.3f}  (range −1 to +1, positive = bullish)",
    ]
    for s in scores:
        lines.append(f"  {s.component:18s} {s.score:+.2f}  weight {s.weight:.0%}  — {s.note}")

    lines += ["", f"Preliminary action from scores: {action_from_score(composite_score).upper()}"]
    return "\n".join(lines)


def action_from_score(score: float) -> str:
    if score >= 0.30:
        return "buy"
    if score <= -0.20:
        return "sell"
    return "hold"


# ── Component scorers ─────────────────────────────────────────────────────────

def _score_valuation(v: dict) -> tuple[float, str]:
    mos = v.get("margin_of_safety")
    if mos is None:
        return 0.0, "Valuation data unavailable"
    if mos >= 0.30:
        return 1.0,  f"Deeply undervalued (MoS {mos:.0%})"
    if mos >= 0.15:
        return 0.5,  f"Moderately undervalued (MoS {mos:.0%})"
    if mos >= -0.15:
        return 0.0,  f"Fairly valued (MoS {mos:.0%})"
    if mos >= -0.30:
        return -0.5, f"Moderately overvalued (MoS {mos:.0%})"
    return -1.0, f"Deeply overvalued (MoS {mos:.0%})"


def _score_fiscal(f: dict) -> tuple[float, str]:
    highlights = len(f.get("highlights", []))
    concerns = len(f.get("concerns", []))
    total = highlights + concerns
    if total == 0:
        return 0.0, "Insufficient fiscal data"
    ratio = (highlights - concerns) / total
    return round(ratio * 0.8, 3), f"{highlights} highlights vs {concerns} concerns"


def _score_news(n: dict) -> tuple[float, str]:
    sentiment = n.get("sentiment", "neutral")
    confidence = float(n.get("confidence", 0.5))
    if sentiment == "bullish":
        return round(confidence * 0.8, 3), f"Bullish news (confidence {confidence:.0%})"
    if sentiment == "bearish":
        return round(-confidence * 0.8, 3), f"Bearish news (confidence {confidence:.0%})"
    return 0.0, "Neutral news sentiment"


def _score_reverse_dcf(v: dict) -> tuple[float, str]:
    rev = v.get("reverse_dcf") or {}
    verdict = rev.get("verdict", "unavailable")
    if verdict == "conservative":
        return 0.5,  "Market pricing in conservative growth (upside potential)"
    if verdict == "reasonable":
        return 0.0,  "Market pricing in reasonable growth"
    if verdict == "aggressive":
        return -0.5, "Market pricing in aggressive growth (limited upside)"
    return 0.0, "Reverse DCF data unavailable"
