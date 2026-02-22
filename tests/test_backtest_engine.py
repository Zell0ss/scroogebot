"""Tests for BacktestEngine internals: always-invested fallback logic and sl_stop."""
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from src.backtest.engine import BacktestEngine, _make_entries_for_exit_only


def _series(values: list[bool], length: int | None = None) -> pd.Series:
    n = length or len(values)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    if len(values) < n:
        values = [False] * n
    return pd.Series(values, index=idx, dtype=bool)


# ---------------------------------------------------------------------------
# _make_entries_for_exit_only
# ---------------------------------------------------------------------------

def test_always_invested_enters_at_warmup():
    """Must set entries[warmup] = True on the initial warmup bar."""
    entries = _series([False] * 100)
    exits   = _series([False] * 100)
    result = _make_entries_for_exit_only(entries, exits, warmup=60)
    assert bool(result.iloc[60]) is True


def test_always_invested_does_not_enter_before_warmup():
    """No entry must be set before the warmup bar."""
    entries = _series([False] * 100)
    exits   = _series([False] * 100)
    result = _make_entries_for_exit_only(entries, exits, warmup=60)
    assert not result.iloc[:60].any(), "No entries expected before warmup"


def test_always_invested_reenters_one_bar_after_exit():
    """After each exit, an entry must be placed on the very next bar."""
    entries = _series([False] * 100)
    exits = _series([False] * 100)
    exits.iloc[70] = True   # exit at bar 70 → re-entry at 71
    exits.iloc[85] = True   # exit at bar 85 → re-entry at 86

    result = _make_entries_for_exit_only(entries, exits, warmup=60)

    assert result.iloc[71], "Entry expected at bar 71 (day after exit at 70)"
    assert result.iloc[86], "Entry expected at bar 86 (day after exit at 85)"


def test_always_invested_no_spurious_entries():
    """Without any exits, only the warmup entry should be set."""
    entries = _series([False] * 100)
    exits   = _series([False] * 100)
    result = _make_entries_for_exit_only(entries, exits, warmup=60)

    true_indices = result[result].index.tolist()
    assert len(true_indices) == 1, f"Expected exactly 1 entry (warmup), got {len(true_indices)}"


def test_always_invested_preserves_existing_entries():
    """If entries already had True values (entry strategy), they are kept."""
    entries = _series([False] * 100)
    entries.iloc[65] = True   # pre-existing BUY signal
    exits   = _series([False] * 100)
    result = _make_entries_for_exit_only(entries, exits, warmup=60)

    assert result.iloc[60], "Warmup entry must still be set"
    assert result.iloc[65], "Pre-existing entry at 65 must be preserved"


# ---------------------------------------------------------------------------
# BacktestEngine.run — sl_stop passed to vectorbt
# ---------------------------------------------------------------------------

def _make_ohlcv(n=200):
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    import numpy as np
    prices = pd.Series(100 + np.arange(n, dtype=float), index=idx)
    df = pd.DataFrame({"Close": prices, "Open": prices, "High": prices + 1,
                       "Low": prices - 1, "Volume": 1_000_000.0}, index=idx)
    ohlcv = MagicMock()
    ohlcv.data = df
    return ohlcv


def test_backtest_engine_passes_sl_stop_to_vectorbt():
    """When stop_loss_pct is provided, sl_stop=(pct/100) must be passed to vectorbt."""
    engine = BacktestEngine()
    strategy = MagicMock()
    strategy.evaluate.return_value = None   # always-invested mode

    ohlcv = _make_ohlcv()
    captured = {}

    def fake_from_signals(close, entries, exits, **kwargs):
        captured.update(kwargs)
        pf = MagicMock()
        pf.stats.return_value = {
            "Total Return [%]": 5.0, "Sharpe Ratio": 1.0,
            "Max Drawdown [%]": 5.0, "Total Trades": 3, "Win Rate [%]": 66.0,
        }
        return pf

    with (
        patch.object(engine.data, "get_historical", return_value=ohlcv),
        patch("vectorbt.Portfolio.from_signals", side_effect=fake_from_signals),
    ):
        engine.run("AAPL", strategy, "rsi", period="1y", stop_loss_pct=8.0)

    assert "sl_stop" in captured, "sl_stop must be passed to Portfolio.from_signals"
    assert abs(captured["sl_stop"] - 0.08) < 1e-9, f"sl_stop must be 0.08, got {captured['sl_stop']}"


def test_backtest_engine_no_sl_stop_when_pct_is_none():
    """When stop_loss_pct is None, sl_stop must NOT be passed to vectorbt."""
    engine = BacktestEngine()
    strategy = MagicMock()
    strategy.evaluate.return_value = None

    ohlcv = _make_ohlcv()
    captured = {}

    def fake_from_signals(close, entries, exits, **kwargs):
        captured.update(kwargs)
        pf = MagicMock()
        pf.stats.return_value = {
            "Total Return [%]": 5.0, "Sharpe Ratio": 1.0,
            "Max Drawdown [%]": 5.0, "Total Trades": 3, "Win Rate [%]": 66.0,
        }
        return pf

    with (
        patch.object(engine.data, "get_historical", return_value=ohlcv),
        patch("vectorbt.Portfolio.from_signals", side_effect=fake_from_signals),
    ):
        engine.run("AAPL", strategy, "rsi", period="1y", stop_loss_pct=None)

    assert "sl_stop" not in captured, f"sl_stop must NOT be passed when pct is None. Got: {captured}"
