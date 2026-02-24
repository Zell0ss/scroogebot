from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd
import ta.momentum
import ta.volatility


@dataclass
class MarketContext:
    ticker: str
    price: Decimal
    # Technical indicators (computed from historical.data — no extra API calls)
    sma20: float | None
    sma50: float | None
    rsi14: float | None
    atr_pct: float | None   # ATR14 / price * 100
    trend: str              # "alcista" | "bajista" | "lateral"
    # Current position
    position_qty: Decimal
    avg_price: Decimal | None
    pnl_pct: float | None
    # Signal metadata
    confidence: float
    # Suggested trade size
    suggested_qty: Decimal  # BUY: 10% of cash; SELL: full position


def compute_market_context(
    ticker: str,
    data: pd.DataFrame,
    price: Decimal,
    pos,               # Position ORM object or None
    basket_cash: Decimal,
    signal_action: str,
    confidence: float = 1.0,
) -> MarketContext:
    """Compute market context from already-fetched OHLCV DataFrame.

    All indicator calculations use the `ta` library on `data` — zero extra
    network calls. Falls back gracefully (None) for insufficient history.
    """
    close = data["Close"]
    price_f = float(price)

    # SMA20 / SMA50
    sma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None

    # RSI14
    try:
        rsi_series = ta.momentum.RSIIndicator(close=close, window=14).rsi().dropna()
        rsi14 = float(rsi_series.iloc[-1]) if not rsi_series.empty else None
    except Exception:
        rsi14 = None

    # ATR14 as percentage of price
    try:
        atr_series = ta.volatility.AverageTrueRange(
            high=data["High"], low=data["Low"], close=close, window=14
        ).average_true_range().dropna()
        atr_pct = float(atr_series.iloc[-1]) / price_f * 100 if not atr_series.empty and price_f > 0 else None
    except Exception:
        atr_pct = None

    # Trend: strict price > SMA20 > SMA50 (or inverse)
    if sma20 is not None and sma50 is not None:
        if price_f > sma20 > sma50:
            trend = "alcista"
        elif price_f < sma20 < sma50:
            trend = "bajista"
        else:
            trend = "lateral"
    else:
        trend = "lateral"

    # Position data
    position_qty = pos.quantity if pos else Decimal("0")
    avg_p = pos.avg_price if pos else None
    if avg_p and avg_p > 0:
        pnl_pct = float((price - avg_p) / avg_p * 100)
    else:
        pnl_pct = None

    # Suggested trade size
    if signal_action == "BUY":
        suggested_qty = (basket_cash * Decimal("0.10") / price).quantize(Decimal("0.01"))
    else:
        suggested_qty = position_qty

    return MarketContext(
        ticker=ticker,
        price=price,
        sma20=sma20,
        sma50=sma50,
        rsi14=rsi14,
        atr_pct=atr_pct,
        trend=trend,
        position_qty=position_qty,
        avg_price=avg_p,
        pnl_pct=pnl_pct,
        confidence=float(confidence),
        suggested_qty=suggested_qty,
    )
