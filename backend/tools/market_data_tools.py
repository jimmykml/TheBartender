from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

BENCHMARK_TICKER = "SPY"


@dataclass(frozen=True)
class PriceContext:
    ticker: str
    start_date: str
    end_date: str
    start_price: float
    end_price: float
    price_change_pct: float
    benchmark_ticker: str
    benchmark_change_pct: float
    excess_return: float
    rsi: float | None
    macd_signal: str
    sma_20: float | None
    sma_50: float | None
    above_sma_20: bool | None
    above_sma_50: bool | None
    volume_vs_avg: float | None


def build_price_driver_context(ticker: str, from_date: date, to_date: date) -> str:
    ctx = _compute_price_context(ticker, from_date, to_date)
    lines = [
        f"=== Price Movement: {ctx.ticker} ({ctx.start_date} → {ctx.end_date}) ===",
        f"Start: ${ctx.start_price:.2f}  |  End: ${ctx.end_price:.2f}",
        f"Ticker change: {ctx.price_change_pct:+.2%}",
        f"Benchmark ({ctx.benchmark_ticker}): {ctx.benchmark_change_pct:+.2%}",
        f"Excess return vs benchmark: {ctx.excess_return:+.2%}",
        "",
        "--- Technical Indicators (as of end date) ---",
        f"RSI(14): {ctx.rsi:.1f}" if ctx.rsi is not None else "RSI(14): N/A",
        f"MACD signal: {ctx.macd_signal}",
        f"20-day SMA: ${ctx.sma_20:.2f}" if ctx.sma_20 is not None else "20-day SMA: N/A",
        f"50-day SMA: ${ctx.sma_50:.2f}" if ctx.sma_50 is not None else "50-day SMA: N/A",
    ]
    if ctx.above_sma_20 is not None:
        lines.append(f"Price vs 20-day SMA: {'above' if ctx.above_sma_20 else 'below'}")
    if ctx.above_sma_50 is not None:
        lines.append(f"Price vs 50-day SMA: {'above' if ctx.above_sma_50 else 'below'}")
    if ctx.volume_vs_avg is not None:
        lines.append(f"Volume vs 30-day avg: {ctx.volume_vs_avg:.1f}x")
    return "\n".join(lines)


def has_recent_abnormal_move(ticker: str, lookback_days: int = 30) -> bool:
    """True if the stock had a >2 sigma daily return in the last lookback_days trading days."""
    try:
        end = date.today()
        start = end - timedelta(days=lookback_days + 20)
        hist = yf.Ticker(ticker).history(start=str(start), end=str(end))
        if hist.empty or len(hist) < 10:
            return False
        returns = hist["Close"].pct_change().dropna()
        std = returns.std()
        if std == 0:
            return False
        mean = returns.mean()
        recent = returns.tail(lookback_days)
        return bool((abs(recent - mean) > 2 * std).any())
    except Exception:
        return False


def had_earnings_near_date(ticker: str, target_date: date, window_days: int = 5) -> bool:
    """True if an earnings release was within window_days of target_date."""
    try:
        earnings = yf.Ticker(ticker).get_earnings_dates(limit=8)
        if earnings is None or earnings.empty:
            return False
        for ts in earnings.index:
            ed = ts.date() if hasattr(ts, "date") else ts
            if abs((ed - target_date).days) <= window_days:
                return True
        return False
    except Exception:
        return False


def _compute_price_context(ticker: str, from_date: date, to_date: date) -> PriceContext:
    history_start = from_date - timedelta(days=100)
    t = yf.Ticker(ticker)

    wide = t.history(start=str(history_start), end=str(to_date + timedelta(days=1)))

    # Narrow window: go back one extra trading day so we have a baseline close
    fetch_start = from_date - timedelta(days=5)
    narrow = t.history(start=str(fetch_start), end=str(to_date + timedelta(days=1)))
    pre = narrow[narrow.index.normalize() < pd.Timestamp(str(from_date))]
    window = narrow[narrow.index.normalize() >= pd.Timestamp(str(from_date))]

    if not window.empty:
        start_price = float(pre["Close"].iloc[-1]) if not pre.empty else float(window["Close"].iloc[0])
        end_price = float(window["Close"].iloc[-1])
        actual_start = str(window.index[0].date())
        actual_end = str(window.index[-1].date())
    else:
        start_price = end_price = 0.0
        actual_start, actual_end = str(from_date), str(to_date)

    price_change = (end_price - start_price) / start_price if start_price else 0.0

    bm = yf.Ticker(BENCHMARK_TICKER).history(
        start=str(fetch_start), end=str(to_date + timedelta(days=1))
    )
    bm_pre = bm[bm.index.normalize() < pd.Timestamp(str(from_date))]
    bm_win = bm[bm.index.normalize() >= pd.Timestamp(str(from_date))]
    if not bm_win.empty:
        bm_start = float(bm_pre["Close"].iloc[-1]) if not bm_pre.empty else float(bm_win["Close"].iloc[0])
        bm_end = float(bm_win["Close"].iloc[-1])
        bm_change = (bm_end - bm_start) / bm_start if bm_start else 0.0
    else:
        bm_change = 0.0

    close = wide["Close"]
    rsi = _compute_rsi(close)
    macd_signal = _compute_macd_signal(close)
    sma_20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    last_close = float(close.iloc[-1]) if not close.empty else 0.0

    avg_vol = float(wide["Volume"].tail(30).mean()) if "Volume" in wide.columns and len(wide) >= 5 else None
    last_vol = float(wide["Volume"].iloc[-1]) if "Volume" in wide.columns and not wide.empty else None
    volume_vs_avg = last_vol / avg_vol if (avg_vol and avg_vol > 0 and last_vol) else None

    return PriceContext(
        ticker=ticker.upper(),
        start_date=actual_start,
        end_date=actual_end,
        start_price=start_price,
        end_price=end_price,
        price_change_pct=price_change,
        benchmark_ticker=BENCHMARK_TICKER,
        benchmark_change_pct=bm_change,
        excess_return=price_change - bm_change,
        rsi=rsi,
        macd_signal=macd_signal,
        sma_20=sma_20,
        sma_50=sma_50,
        above_sma_20=(last_close > sma_20) if sma_20 else None,
        above_sma_50=(last_close > sma_50) if sma_50 else None,
        volume_vs_avg=volume_vs_avg,
    )


def _compute_rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    delta = close.diff().dropna()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    last_loss = loss.iloc[-1]
    if last_loss == 0:
        return 100.0
    rs = gain.iloc[-1] / last_loss
    return float(100 - (100 / (1 + rs)))


def _compute_macd_signal(close: pd.Series) -> str:
    if len(close) < 26:
        return "neutral"
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    if macd.iloc[-1] > signal.iloc[-1]:
        return "bullish"
    if macd.iloc[-1] < signal.iloc[-1]:
        return "bearish"
    return "neutral"
