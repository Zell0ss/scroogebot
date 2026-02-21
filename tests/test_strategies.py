import pytest
import pandas as pd
from decimal import Decimal
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy


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
