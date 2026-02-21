import logging
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


class BacktestEngine:
    def __init__(self):
        self.data = YahooDataProvider()

    def run(
        self,
        ticker: str,
        strategy: Strategy,
        strategy_name: str,
        period: str = "1y",
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

        pf = vbt.Portfolio.from_signals(close, entries, exits, init_cash=10_000)
        stats = pf.stats()

        bh_return = float((close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100)

        total_return = float(stats.get("Total Return [%]", 0))
        n_days = max(len(close), 1)
        annualized = ((1 + total_return / 100) ** (252 / n_days) - 1) * 100 if total_return > -100 else -100.0

        return BacktestResult(
            ticker=ticker,
            period=period,
            strategy_name=strategy_name,
            total_return_pct=total_return,
            annualized_return_pct=annualized,
            sharpe_ratio=float(stats.get("Sharpe Ratio", 0) or 0),
            max_drawdown_pct=float(stats.get("Max Drawdown [%]", 0)),
            n_trades=int(stats.get("Total Trades", 0)),
            win_rate_pct=float(stats.get("Win Rate [%]", 0) or 0),
            benchmark_return_pct=bh_return,
        )
