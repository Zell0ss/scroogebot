import logging
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import pandas as pd

from src.strategies.base import Strategy

logger = logging.getLogger(__name__)

LOOKBACK = 60          # bars of real history used as warmup context per simulation
HIST_PERIOD = "2y"     # how much history to fetch for the returns pool


class MonteCarloSimulator:
    def generate_paths(
        self,
        hist_df: pd.DataFrame,
        n_simulations: int,
        horizon: int,
        rng: np.random.Generator,
    ) -> list[pd.Series]:
        """Bootstrap N synthetic Close price series of length `horizon`.

        Samples log returns with replacement from the historical pool and
        reconstructs price series starting from the last real Close price.
        Synthetic index uses business-day frequency after the last real date.
        """
        close = hist_df["Close"]
        log_returns = np.log(close / close.shift(1)).dropna().values
        last_price = float(close.iloc[-1])
        last_date = close.index[-1]

        future_dates = pd.bdate_range(
            start=last_date + pd.Timedelta(days=1), periods=horizon
        )

        paths = []
        for _ in range(n_simulations):
            sampled = rng.choice(log_returns, size=horizon, replace=True)
            prices = last_price * np.exp(np.cumsum(sampled))
            path = pd.Series(prices, index=future_dates, name="Close")
            paths.append(path)
        return paths


# Thresholds for profile classification — adjust as needed
_PROB_LOSS_LOW = 0.20
_PROB_LOSS_HIGH = 0.40
_SHARPE_GOOD = 0.8
_SHARPE_LOW = 0.4


@dataclass
class AssetMonteCarloResult:
    ticker: str
    n_simulations: int
    horizon: int
    strategy_name: str
    seed: int
    # Return distribution
    return_median: float
    return_mean: float
    return_p10: float
    return_p90: float
    return_p05: float
    prob_loss: float          # fraction of simulations with negative return
    # Drawdown
    max_dd_median: float
    max_dd_p95: float         # 95th percentile worst drawdown
    # Quality
    sharpe_median: float
    win_rate_median: float
    # Tail risk
    var_95: float             # Value at Risk (5th percentile of returns)
    cvar_95: float            # Conditional VaR / Expected Shortfall


def _profile_line(r: AssetMonteCarloResult) -> str:
    """Single-line risk profile summary with emoji."""
    if r.prob_loss < _PROB_LOSS_LOW and r.sharpe_median > _SHARPE_GOOD:
        return "✅ Perfil favorable"
    if r.prob_loss > _PROB_LOSS_HIGH or r.sharpe_median < _SHARPE_LOW:
        return "🔴 Perfil desfavorable, considerar ajustes"
    return "⚠️ Perfil moderado, revisar riesgo"


class MonteCarloAnalyzer:
    """Runs a strategy over N bootstrapped price paths and aggregates metrics."""

    def __init__(self):
        self.simulator = MonteCarloSimulator()

    def run_asset(
        self,
        ticker: str,
        strategy: Strategy,
        strategy_name: str,
        hist_df: pd.DataFrame,
        n_simulations: int,
        horizon: int,
        rng: np.random.Generator,
        seed: int,
    ) -> AssetMonteCarloResult:
        import vectorbt as vbt

        warmup_df = hist_df.tail(LOOKBACK).copy()
        paths = self.simulator.generate_paths(hist_df, n_simulations, horizon, rng)

        returns: list[float] = []
        max_dds: list[float] = []
        sharpes: list[float] = []
        win_rates: list[float] = []

        for path in paths:
            path_df = path.to_frame("Close")

            entries = pd.Series(False, index=path.index)
            exits = pd.Series(False, index=path.index)

            for i in range(len(path)):
                current_price = Decimal(str(path.iloc[i]))

                # Build context: warmup tail + synthetic bars up to current
                if i < LOOKBACK:
                    ctx = pd.concat([warmup_df.iloc[-(LOOKBACK - i):], path_df.iloc[:i]])
                else:
                    ctx = path_df.iloc[i - LOOKBACK:i]

                if len(ctx) < 2:
                    continue

                try:
                    signal = strategy.evaluate(ticker, ctx, current_price)
                except Exception as exc:
                    logger.debug("Strategy raised on bar %d for %s: %s", i, ticker, exc)
                    continue

                if signal:
                    if signal.action == "BUY":
                        entries.iloc[i] = True
                    elif signal.action == "SELL":
                        exits.iloc[i] = True

            pf = vbt.Portfolio.from_signals(
                path, entries, exits, init_cash=10_000, freq="1D"
            )
            stats = pf.stats()

            returns.append(float(stats.get("Total Return [%]", 0) or 0))
            max_dds.append(float(stats.get("Max Drawdown [%]", 0) or 0))
            sharpes.append(float(stats.get("Sharpe Ratio", 0) or 0))
            win_rates.append(float(stats.get("Win Rate [%]", 0) or 0))

        arr = np.array(returns)
        var_95 = float(np.percentile(arr, 5))
        tail = arr[arr <= var_95]
        cvar_95 = float(np.mean(tail)) if len(tail) > 0 else var_95

        return AssetMonteCarloResult(
            ticker=ticker,
            n_simulations=n_simulations,
            horizon=horizon,
            strategy_name=strategy_name,
            seed=seed,
            return_median=float(np.percentile(arr, 50)),
            return_mean=float(np.mean(arr)),
            return_p10=float(np.percentile(arr, 10)),
            return_p90=float(np.percentile(arr, 90)),
            return_p05=float(np.percentile(arr, 5)),
            prob_loss=float(np.mean(arr < 0)),
            max_dd_median=float(np.percentile(max_dds, 50)),
            max_dd_p95=float(np.percentile(max_dds, 95)),
            sharpe_median=float(np.percentile(sharpes, 50)),
            win_rate_median=float(np.percentile(win_rates, 50)),
            var_95=var_95,
            cvar_95=cvar_95,
        )
