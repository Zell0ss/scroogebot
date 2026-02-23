from decimal import Decimal

import pandas as pd

from src.strategies.base import Strategy, Signal
from src.config import app_config

# These tickers are safe-haven assets — never trigger SELL on them
SAFE_TICKERS = {"GLD", "BND", "TLT", "SHY", "VGSH"}


class SafeHavenStrategy(Strategy):
    """Sells risky assets when drawdown from peak exceeds threshold.

    Safe-haven tickers (GLD, BND, TLT, …) are never touched by this strategy.
    """

    def __init__(self):
        cfg = app_config["strategies"].get("safe_haven") or app_config["strategies"].get(
            "stop_loss", {}
        )
        self.drawdown_threshold = Decimal(str(cfg.get("drawdown_pct", cfg.get("stop_loss_pct", 8)))) / 100

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal, avg_price: Decimal | None = None) -> Signal | None:
        if ticker.upper() in SAFE_TICKERS:
            return None
        if len(data) < 2:
            return None

        peak = Decimal(str(data["Close"].max()))
        if peak == 0:
            return None

        drawdown = (peak - current_price) / peak
        if drawdown >= self.drawdown_threshold:
            return Signal(
                action="SELL",
                ticker=ticker,
                price=current_price,
                reason=f"Drawdown {float(drawdown) * 100:.1f}% from peak — rotating to safe haven",
                confidence=0.8,
            )
        return None
