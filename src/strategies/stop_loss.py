from decimal import Decimal
import pandas as pd
from src.strategies.base import Strategy, Signal
from src.config import app_config


class StopLossStrategy(Strategy):
    def __init__(self):
        cfg = app_config["strategies"]["stop_loss"]
        self.stop_loss_pct = Decimal(str(cfg["stop_loss_pct"])) / 100
        self.take_profit_pct = Decimal(str(cfg["take_profit_pct"])) / 100

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        if len(data) < 2:
            return None
        open_price = Decimal(str(data["Close"].iloc[0]))
        if open_price == 0:
            return None
        change = (current_price - open_price) / open_price

        if change <= -self.stop_loss_pct:
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"Stop-loss triggered: {change*100:.1f}% drop",
                confidence=0.95,
            )
        if change >= self.take_profit_pct:
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"Take-profit triggered: {change*100:.1f}% gain",
                confidence=0.9,
            )
        return None
