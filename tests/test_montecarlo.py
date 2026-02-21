import numpy as np
import pandas as pd

from src.backtest.montecarlo import MonteCarloSimulator


def _make_hist_df(n: int = 120) -> pd.DataFrame:
    """120 bars of synthetic OHLCV data."""
    prices = pd.Series(
        [100.0 + i * 0.5 for i in range(n)],
        index=pd.date_range("2023-01-01", periods=n, freq="B"),
    )
    return pd.DataFrame({
        "Open": prices * 0.999,
        "High": prices * 1.005,
        "Low":  prices * 0.995,
        "Close": prices,
        "Volume": 1_000_000,
    })


def test_generate_paths_returns_n_paths():
    rng = np.random.default_rng(42)
    sim = MonteCarloSimulator()
    hist_df = _make_hist_df()
    paths = sim.generate_paths(hist_df, n_simulations=10, horizon=20, rng=rng)
    assert len(paths) == 10


def test_generate_paths_each_has_horizon_bars():
    rng = np.random.default_rng(42)
    sim = MonteCarloSimulator()
    hist_df = _make_hist_df()
    paths = sim.generate_paths(hist_df, n_simulations=5, horizon=30, rng=rng)
    assert all(len(p) == 30 for p in paths)


def test_generate_paths_prices_are_positive():
    rng = np.random.default_rng(42)
    sim = MonteCarloSimulator()
    hist_df = _make_hist_df()
    paths = sim.generate_paths(hist_df, n_simulations=20, horizon=90, rng=rng)
    assert all((p > 0).all() for p in paths)


def test_generate_paths_starts_near_last_real_price():
    rng = np.random.default_rng(42)
    sim = MonteCarloSimulator()
    hist_df = _make_hist_df()
    last_price = float(hist_df["Close"].iloc[-1])
    paths = sim.generate_paths(hist_df, n_simulations=50, horizon=5, rng=rng)
    first_prices = [float(p.iloc[0]) for p in paths]
    # First simulated price should be within ±30% of last real price (generous bound)
    assert all(last_price * 0.7 < fp < last_price * 1.3 for fp in first_prices)


def test_generate_paths_have_datetime_index():
    rng = np.random.default_rng(42)
    sim = MonteCarloSimulator()
    hist_df = _make_hist_df()
    paths = sim.generate_paths(hist_df, n_simulations=3, horizon=10, rng=rng)
    for p in paths:
        assert isinstance(p.index, pd.DatetimeIndex)
