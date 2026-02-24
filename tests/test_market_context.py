import pytest
import pandas as pd
from decimal import Decimal
from unittest.mock import MagicMock

from src.alerts.market_context import compute_market_context, MarketContext


def _make_ohlcv(prices: list[float]) -> pd.DataFrame:
    """Synthetic OHLCV DataFrame: High=price*1.01, Low=price*0.99."""
    return pd.DataFrame({
        "Open":   prices,
        "High":   [p * 1.01 for p in prices],
        "Low":    [p * 0.99 for p in prices],
        "Close":  prices,
        "Volume": [1000] * len(prices),
    })


def _make_pos(qty: float, avg: float):
    pos = MagicMock()
    pos.quantity = Decimal(str(qty))
    pos.avg_price = Decimal(str(avg))
    return pos


# --- Trend detection ---

def test_trend_alcista():
    # Monotonically increasing: price > SMA20 > SMA50
    prices = list(range(1, 61))  # [1, 2, ..., 60], 60 bars
    data = _make_ohlcv(prices)
    ctx = compute_market_context("AAPL", data, Decimal("60"), None, Decimal("10000"), "SELL")
    assert ctx.trend == "alcista"


def test_trend_bajista():
    # Monotonically decreasing: price < SMA20 < SMA50
    prices = list(range(60, 0, -1))  # [60, 59, ..., 1], 60 bars
    data = _make_ohlcv(prices)
    ctx = compute_market_context("AAPL", data, Decimal("1"), None, Decimal("10000"), "SELL")
    assert ctx.trend == "bajista"


def test_trend_lateral():
    # Flat prices: SMA20 == SMA50 == price → lateral
    prices = [10.0] * 60
    data = _make_ohlcv(prices)
    ctx = compute_market_context("AAPL", data, Decimal("10"), None, Decimal("10000"), "BUY")
    assert ctx.trend == "lateral"


# --- P&L ---

def test_pnl_positive():
    data = _make_ohlcv([10.0] * 60)
    pos = _make_pos(qty=20, avg=4.0)
    ctx = compute_market_context("SAN.MC", data, Decimal("4.40"), pos, Decimal("8000"), "SELL")
    assert ctx.pnl_pct == pytest.approx(10.0, rel=1e-3)


def test_pnl_negative():
    data = _make_ohlcv([10.0] * 60)
    pos = _make_pos(qty=20, avg=5.0)
    ctx = compute_market_context("SAN.MC", data, Decimal("4.00"), pos, Decimal("8000"), "SELL")
    assert ctx.pnl_pct == pytest.approx(-20.0, rel=1e-3)


def test_pnl_none_when_no_position():
    data = _make_ohlcv([10.0] * 60)
    ctx = compute_market_context("AAPL", data, Decimal("10"), None, Decimal("10000"), "BUY")
    assert ctx.pnl_pct is None


# --- suggested_qty ---

def test_suggested_qty_buy_is_10pct_of_cash():
    data = _make_ohlcv([10.0] * 60)
    # cash=1000, price=10 → 10% = 100€ / 10 = 10 shares
    ctx = compute_market_context("AAPL", data, Decimal("10"), None, Decimal("1000"), "BUY")
    assert ctx.suggested_qty == Decimal("10.00")


def test_suggested_qty_sell_is_full_position():
    data = _make_ohlcv([10.0] * 60)
    pos = _make_pos(qty=25, avg=9.0)
    ctx = compute_market_context("AAPL", data, Decimal("10"), pos, Decimal("1000"), "SELL")
    assert ctx.suggested_qty == Decimal("25")


# --- ATR% ---

def test_atr_pct_is_none_for_insufficient_data():
    data = _make_ohlcv([10.0] * 5)  # only 5 bars, ATR needs 14
    ctx = compute_market_context("AAPL", data, Decimal("10"), None, Decimal("1000"), "BUY")
    assert ctx.atr_pct is None


def test_atr_pct_is_positive_for_volatile_data():
    prices = [10 + (i % 3) for i in range(60)]  # oscillating
    data = _make_ohlcv(prices)
    ctx = compute_market_context("AAPL", data, Decimal("10"), None, Decimal("1000"), "BUY")
    assert ctx.atr_pct is not None
    assert ctx.atr_pct > 0
