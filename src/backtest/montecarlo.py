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
