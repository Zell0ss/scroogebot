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


@dataclass
class PortfolioBacktestResult:
    period: str
    strategy_name: str
    # Aggregate portfolio stats (ticker="PORTFOLIO")
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    n_trades: int            # sum across all tickers
    benchmark_return_pct: float   # equal-weight B&H average
    # Per-asset breakdown
    per_asset: dict[str, BacktestResult]


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
        tickers: list[str],
        strategy: Strategy,
        strategy_name: str,
        period: str = "1y",
        stop_loss_pct: float | None = None,
    ) -> "PortfolioBacktestResult":
        import vectorbt as vbt

        # Step 1: Fetch OHLCV per ticker
        ohlcv_dict = {}
        for t in tickers:
            ohlcv_dict[t] = self.data.get_historical(t, period=period, interval="1d")

        # Step 2: Align close prices into one DataFrame
        close_df = pd.concat(
            {t: ohlcv_dict[t].data["Close"] for t in tickers}, axis=1
        ).ffill().dropna()

        # Drop any ticker column that is all-NaN after alignment (edge case)
        all_nan_cols = [col for col in close_df.columns if close_df[col].isna().all()]
        if all_nan_cols:
            logger.warning("Dropping tickers with all-NaN after alignment: %s", all_nan_cols)
            close_df = close_df.drop(columns=all_nan_cols)

        # Use only tickers that survived alignment
        active_tickers = list(close_df.columns)

        window = 60  # bars of lookback for each strategy evaluation

        # Step 3: Generate entries/exits per ticker using rolling-window approach
        entries_dict: dict[str, pd.Series] = {}
        exits_dict: dict[str, pd.Series] = {}

        for t in active_tickers:
            entries = pd.Series(False, index=close_df.index)
            exits = pd.Series(False, index=close_df.index)
            ticker_ohlcv = ohlcv_dict[t].data.reindex(close_df.index).ffill()

            for i in range(window, len(close_df)):
                window_data = ticker_ohlcv.iloc[i - window:i]
                current_price = Decimal(str(close_df[t].iloc[i]))
                try:
                    signal = strategy.evaluate(t, window_data, current_price)
                except Exception as e:
                    logger.warning(
                        "Strategy %s raised on bar %d for %s: %s",
                        strategy.__class__.__name__, i, t, e,
                    )
                    continue
                if signal:
                    if signal.action == "BUY":
                        entries.iloc[i] = True
                    elif signal.action == "SELL":
                        exits.iloc[i] = True

            entries_dict[t] = entries
            exits_dict[t] = exits

        # Step 4: Apply _make_entries_for_exit_only per ticker if no BUY entries
        for t in active_tickers:
            if not entries_dict[t].any():
                entries_dict[t] = _make_entries_for_exit_only(
                    entries_dict[t], exits_dict[t], warmup=window
                )

        # Step 5: Build 2D DataFrames aligned to close_df.index
        entries_df = pd.DataFrame(entries_dict).reindex(close_df.index).fillna(False)
        exits_df   = pd.DataFrame(exits_dict).reindex(close_df.index).fillna(False)

        # Step 6: Run vectorbt grouped portfolio (one call for aggregate stats)
        sl_kwargs = {"sl_stop": stop_loss_pct / 100} if stop_loss_pct else {}
        pf = vbt.Portfolio.from_signals(
            close_df, entries_df, exits_df,
            init_cash=10_000, freq="1D",
            group_by=True, cash_sharing=True,
            **sl_kwargs,
        )
        agg_stats = pf.stats()

        def _safe(val, default: float = 0.0) -> float:
            v = float(val) if val is not None else default
            return v if math.isfinite(v) else default

        # Step 7: Compute per-asset BacktestResult
        per_ticker_cash = 10_000 / len(active_tickers)
        per_asset: dict[str, BacktestResult] = {}
        for t in active_tickers:
            pf_single = vbt.Portfolio.from_signals(
                close_df[t], entries_df[t], exits_df[t],
                init_cash=per_ticker_cash, freq="1D",
                **sl_kwargs,
            )
            single_stats = pf_single.stats()

            bh_single = float(
                (close_df[t].iloc[-1] - close_df[t].iloc[0]) / close_df[t].iloc[0] * 100
            )
            single_return = _safe(single_stats.get("Total Return [%]"))
            n_days_single = max(len(close_df[t].dropna()), 1)
            annualized_single = (
                ((1 + single_return / 100) ** (252 / n_days_single) - 1) * 100
                if single_return > -100
                else -100.0
            )

            per_asset[t] = BacktestResult(
                ticker=t,
                period=period,
                strategy_name=strategy_name,
                total_return_pct=single_return,
                annualized_return_pct=annualized_single,
                sharpe_ratio=_safe(single_stats.get("Sharpe Ratio")),
                max_drawdown_pct=_safe(single_stats.get("Max Drawdown [%]")),
                n_trades=int(single_stats.get("Total Trades", 0)),
                win_rate_pct=_safe(single_stats.get("Win Rate [%]")),
                benchmark_return_pct=bh_single,
            )

        # Step 8: Compute benchmark = equal-weight average of per-ticker B&H returns
        bh_returns = [
            float((close_df[t].iloc[-1] - close_df[t].iloc[0]) / close_df[t].iloc[0] * 100)
            for t in active_tickers
        ]
        portfolio_bh = sum(bh_returns) / len(bh_returns)

        # Step 9: Compute aggregate annualized return
        total_return_agg = _safe(agg_stats.get("Total Return [%]"))
        n_days_agg = max(len(close_df), 1)
        annualized_agg = (
            ((1 + total_return_agg / 100) ** (252 / n_days_agg) - 1) * 100
            if total_return_agg > -100
            else -100.0
        )

        # Step 10: Return PortfolioBacktestResult with all fields populated
        return PortfolioBacktestResult(
            period=period,
            strategy_name=strategy_name,
            total_return_pct=total_return_agg,
            annualized_return_pct=annualized_agg,
            sharpe_ratio=_safe(agg_stats.get("Sharpe Ratio")),
            max_drawdown_pct=_safe(agg_stats.get("Max Drawdown [%]")),
            n_trades=sum(r.n_trades for r in per_asset.values()),
            benchmark_return_pct=portfolio_bh,
            per_asset=per_asset,
        )
