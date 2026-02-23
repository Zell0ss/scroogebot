from decimal import Decimal

import pandas as pd
import ta.volatility

from src.strategies.base import Strategy, Signal
from src.config import app_config


class BollingerStrategy(Strategy):
    def __init__(self):
        cfg = app_config["strategies"]["bollinger"]
        self.period = int(cfg["period"])
        self.std_dev = float(cfg["std_dev"])

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal, avg_price: Decimal | None = None) -> Signal | None:
        if len(data) < self.period:
            return None

        bb = ta.volatility.BollingerBands(
            close=data["Close"], window=self.period, window_dev=self.std_dev
        )
        lower = bb.bollinger_lband().iloc[-1]
        upper = bb.bollinger_hband().iloc[-1]

        if pd.isna(lower) or pd.isna(upper):
            return None

        lower_d = Decimal(str(lower))
        upper_d = Decimal(str(upper))

        if current_price <= lower_d:
            return Signal(
                action="BUY",
                ticker=ticker,
                price=current_price,
                reason=f"Price at/below lower Bollinger band ({float(lower):.2f})",
                confidence=0.65,
            )
        if current_price >= upper_d:
            return Signal(
                action="SELL",
                ticker=ticker,
                price=current_price,
                reason=f"Price at/above upper Bollinger band ({float(upper):.2f})",
                confidence=0.65,
            )
        return None
