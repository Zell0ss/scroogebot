import logging
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import pandas as pd

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
