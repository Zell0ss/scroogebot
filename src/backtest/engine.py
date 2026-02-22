import logging
import math
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from src.data.yahoo import YahooDataProvider
from src.strategies.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    ticker: str
    period: str
    strategy_name: str
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    n_trades: int
    win_rate_pct: float
    benchmark_return_pct: float  # buy-and-hold


def _make_entries_for_exit_only(
    entries: pd.Series,
    exits: pd.Series,
    warmup: int,
) -> pd.Series:
    """Build an always-invested entries series for exit-only strategies.

    Enter at bar `warmup`, then re-enter one bar after each exit signal.
    Any pre-existing True values in `entries` are preserved.
    """
    result = entries.copy()
    result.iloc[warmup] = True
    for i in range(warmup + 1, len(result)):
        if exits.iloc[i - 1]:
            result.iloc[i] = True
    return result


class BacktestEngine:
    def __init__(self):
        self.data = YahooDataProvider()

    def run(
        self,
        ticker: str,
        strategy: Strategy,
        strategy_name: str,
        period: str = "1y",
        stop_loss_pct: float | None = None,
    ) -> BacktestResult:
        import vectorbt as vbt

        ohlcv = self.data.get_historical(ticker, period=period, interval="1d")
        close = ohlcv.data["Close"]

        # Generate entry/exit signals via rolling strategy evaluation
        entries = pd.Series(False, index=close.index)
        exits = pd.Series(False, index=close.index)
        window = 60  # bars of lookback for each strategy evaluation

        for i in range(window, len(close)):
            window_data = ohlcv.data.iloc[i - window:i]
            current_price = Decimal(str(close.iloc[i]))
            try:
                signal = strategy.evaluate(ticker, window_data, current_price)
            except Exception as e:
                logger.warning("Strategy %s raised on bar %d for %s: %s",
                               strategy.__class__.__name__, i, ticker, e)
                continue
            if signal:
                if signal.action == "BUY":
                    entries.iloc[i] = True
                elif signal.action == "SELL":
                    exits.iloc[i] = True

        if not entries.any():
            entries = _make_entries_for_exit_only(entries, exits, warmup=window)

        sl_kwargs = {"sl_stop": stop_loss_pct / 100} if stop_loss_pct else {}
        pf = vbt.Portfolio.from_signals(close, entries, exits, init_cash=10_000, freq="1D", **sl_kwargs)
        stats = pf.stats()

        bh_return = float((close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100)

        def _safe(val, default: float = 0.0) -> float:
            v = float(val) if val is not None else default
            return v if math.isfinite(v) else default

        total_return = _safe(stats.get("Total Return [%]"))
        n_days = max(len(close), 1)
        annualized = ((1 + total_return / 100) ** (252 / n_days) - 1) * 100 if total_return > -100 else -100.0

        return BacktestResult(
            ticker=ticker,
            period=period,
            strategy_name=strategy_name,
            total_return_pct=total_return,
            annualized_return_pct=annualized,
            sharpe_ratio=_safe(stats.get("Sharpe Ratio")),
            max_drawdown_pct=_safe(stats.get("Max Drawdown [%]")),
            n_trades=int(stats.get("Total Trades", 0)),
            win_rate_pct=_safe(stats.get("Win Rate [%]")),
            benchmark_return_pct=bh_return,
        )
