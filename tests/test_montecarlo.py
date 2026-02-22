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


from src.backtest.montecarlo import AssetMonteCarloResult, _profile_line


def _make_result(**overrides) -> AssetMonteCarloResult:
    defaults = dict(
        ticker="TEST", n_simulations=100, horizon=90, strategy_name="stop_loss", seed=42,
        return_median=5.0, return_mean=4.5,
        return_p10=1.0, return_p90=9.0, return_p05=-2.0,
        prob_loss=0.15,
        max_dd_median=4.0, max_dd_p95=10.0,
        sharpe_median=1.1, win_rate_median=55.0,
        var_95=-2.0, cvar_95=-3.5,
    )
    defaults.update(overrides)
    return AssetMonteCarloResult(**defaults)


def test_profile_favorable():
    r = _make_result(prob_loss=0.10, sharpe_median=0.9)
    result = _profile_line(r).lower()
    assert "favorable" in result
    assert "desfavorable" not in result


def test_profile_desfavorable_high_prob_loss():
    r = _make_result(prob_loss=0.45, sharpe_median=0.9)
    assert "desfavorable" in _profile_line(r).lower()


def test_profile_desfavorable_low_sharpe():
    r = _make_result(prob_loss=0.10, sharpe_median=0.3)
    assert "desfavorable" in _profile_line(r).lower()


def test_profile_moderado():
    r = _make_result(prob_loss=0.25, sharpe_median=0.6)
    assert "moderado" in _profile_line(r).lower()


from src.backtest.montecarlo import MonteCarloAnalyzer
from src.strategies.stop_loss import StopLossStrategy


def test_run_asset_integration():
    """Integration test: StopLoss strategy on 5 simulations of 10 days."""
    hist_df = _make_hist_df(120)  # 120 bars, enough for warmup pool

    rng = np.random.default_rng(99)
    analyzer = MonteCarloAnalyzer()
    result = analyzer.run_asset(
        ticker="TEST",
        strategy=StopLossStrategy(),
        strategy_name="stop_loss",
        hist_df=hist_df,
        n_simulations=5,
        horizon=10,
        rng=rng,
        seed=99,
    )

    assert isinstance(result, AssetMonteCarloResult)
    assert result.ticker == "TEST"
    assert result.n_simulations == 5
    assert result.horizon == 10
    assert result.seed == 99
    assert 0.0 <= result.prob_loss <= 1.0
    assert result.var_95 <= result.return_median  # VaR is always <= median
    assert result.cvar_95 <= result.var_95        # CVaR <= VaR by definition


from src.bot.handlers.montecarlo import _parse_args, MonteCarloFormatter


def test_parse_args_name_only():
    name, n, h = _parse_args(["Cesta", "Agresiva"])
    assert name == "Cesta Agresiva"
    assert n == 100
    assert h == 90


def test_parse_args_with_n_sims():
    name, n, h = _parse_args(["Cesta", "Agresiva", "200"])
    assert name == "Cesta Agresiva"
    assert n == 200
    assert h == 90


def test_parse_args_with_n_and_horizon():
    name, n, h = _parse_args(["Cesta", "Agresiva", "200", "180"])
    assert name == "Cesta Agresiva"
    assert n == 200
    assert h == 180


def test_parse_args_caps_n_sims_at_500():
    name, n, h = _parse_args(["Cesta", "Agresiva", "9999"])
    assert n == 500


def test_parse_args_caps_horizon_at_365():
    name, n, h = _parse_args(["Cesta", "Agresiva", "100", "9999"])
    assert h == 365


def test_formatter_contains_ticker():
    fmt = MonteCarloFormatter()
    r = _make_result(ticker="AAPL")
    text = fmt.format_asset(r)
    assert "AAPL" in text


def test_formatter_contains_return_median():
    fmt = MonteCarloFormatter()
    r = _make_result(return_median=7.3)
    text = fmt.format_asset(r)
    assert "7.3" in text


def test_formatter_contains_profile():
    fmt = MonteCarloFormatter()
    r = _make_result(prob_loss=0.10, sharpe_median=0.9)
    text = fmt.format_asset(r)
    assert any(kw in text for kw in ["favorable", "moderado", "desfavorable"])
