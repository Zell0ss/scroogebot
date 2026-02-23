from decimal import Decimal

import pandas as pd
import ta.momentum

from src.strategies.base import Strategy, Signal
from src.config import app_config


class RSIStrategy(Strategy):
    def __init__(self):
        cfg = app_config["strategies"]["rsi"]
        self.period = int(cfg["period"])
        self.oversold = float(cfg["oversold"])
        self.overbought = float(cfg["overbought"])

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal, avg_price: Decimal | None = None) -> Signal | None:
        if len(data) < self.period + 2:
            return None

        rsi = ta.momentum.RSIIndicator(close=data["Close"], window=self.period).rsi()
        if rsi is None or rsi.empty:
            return None

        last_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        if pd.isna(last_rsi) or pd.isna(prev_rsi):
            return None

        # Signal on crossover out of zone (not just being in zone)
        if prev_rsi <= self.oversold < last_rsi:
            return Signal(
                action="BUY",
                ticker=ticker,
                price=current_price,
                reason=f"RSI exiting oversold zone ({last_rsi:.1f})",
                confidence=0.7,
            )
        if prev_rsi >= self.overbought > last_rsi:
            return Signal(
                action="SELL",
                ticker=ticker,
                price=current_price,
                reason=f"RSI exiting overbought zone ({last_rsi:.1f})",
                confidence=0.7,
            )
        return None
