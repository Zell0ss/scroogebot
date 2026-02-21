from decimal import Decimal
import pandas as pd
from src.strategies.base import Strategy, Signal
from src.config import app_config


class MACrossoverStrategy(Strategy):
    def __init__(self):
        cfg = app_config["strategies"]["ma_crossover"]
        self.fast = cfg["fast_period"]
        self.slow = cfg["slow_period"]

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        if len(data) < self.slow + 1:
            return None
        close = data["Close"]
        fast_ma = close.rolling(self.fast).mean()
        slow_ma = close.rolling(self.slow).mean()

        if (fast_ma.iloc[-1] > slow_ma.iloc[-1]) and (fast_ma.iloc[-2] <= slow_ma.iloc[-2]):
            return Signal(
                action="BUY", ticker=ticker, price=current_price,
                reason=f"MA{self.fast} crossed above MA{self.slow}",
                confidence=0.75,
            )
        if (fast_ma.iloc[-1] < slow_ma.iloc[-1]) and (fast_ma.iloc[-2] >= slow_ma.iloc[-2]):
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"MA{self.fast} crossed below MA{self.slow}",
                confidence=0.75,
            )
        return None
