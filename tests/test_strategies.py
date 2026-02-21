import pytest
import pandas as pd
from decimal import Decimal
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy
from src.strategies.rsi import RSIStrategy
from src.strategies.bollinger import BollingerStrategy
from src.strategies.safe_haven import SafeHavenStrategy


def make_df(prices: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(prices), freq="D")
    return pd.DataFrame({"Close": prices}, index=idx)


def test_stop_loss_triggers_sell():
    strategy = StopLossStrategy()
    df = make_df([100.0] * 61)
    signal = strategy.evaluate("AAPL", df, Decimal("88"))  # 12% drop > 8% threshold
    assert signal is not None
    assert signal.action == "SELL"
    assert "Stop-loss" in signal.reason


def test_take_profit_triggers_sell():
    strategy = StopLossStrategy()
    df = make_df([100.0] * 61)
    signal = strategy.evaluate("AAPL", df, Decimal("120"))  # 20% gain > 15% threshold
    assert signal is not None
    assert signal.action == "SELL"
    assert "Take-profit" in signal.reason


def test_no_signal_within_thresholds():
    strategy = StopLossStrategy()
    df = make_df([100.0] * 61)
    signal = strategy.evaluate("AAPL", df, Decimal("100"))
    assert signal is None


def test_ma_crossover_runs_without_error():
    strategy = MACrossoverStrategy()
    prices = [100.0 + i * 0.1 for i in range(80)]
    df = make_df(prices)
    signal = strategy.evaluate("AAPL", df, Decimal("108"))
    if signal:
        assert signal.action in ("BUY", "SELL")


def test_rsi_returns_signal_or_none():
    strategy = RSIStrategy()
    prices = [100.0 + i * 0.5 for i in range(30)]
    df = make_df(prices)
    signal = strategy.evaluate("MSFT", df, Decimal("115"))
    if signal:
        assert signal.action in ("BUY", "SELL")


def test_bollinger_returns_signal_or_none():
    strategy = BollingerStrategy()
    prices = [100.0] * 30
    df = make_df(prices)
    signal = strategy.evaluate("MSFT", df, Decimal("90"))  # well below band
    if signal:
        assert signal.action in ("BUY", "SELL")


def test_safe_haven_triggers_on_drawdown():
    strategy = SafeHavenStrategy()
    # Peak of 120, now at 100 — 16.7% drawdown > 8% threshold
    prices = [120.0] + [115.0] * 30 + [100.0]
    df = make_df(prices)
    signal = strategy.evaluate("AAPL", df, Decimal("100"))
    assert signal is not None
    assert signal.action == "SELL"


def test_safe_haven_skips_safe_assets():
    strategy = SafeHavenStrategy()
    prices = [100.0] + [50.0] * 30  # massive drop, but it's GLD
    df = make_df(prices)
    signal = strategy.evaluate("GLD", df, Decimal("50"))
    assert signal is None
