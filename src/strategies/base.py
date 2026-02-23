from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
import pandas as pd


@dataclass
class Signal:
    action: str        # BUY | SELL | HOLD
    ticker: str
    price: Decimal
    reason: str
    confidence: float = 1.0


class Strategy(ABC):
    @abstractmethod
    def evaluate(
        self,
        ticker: str,
        data: pd.DataFrame,
        current_price: Decimal,
        avg_price: Decimal | None = None,
    ) -> Signal | None:
        """Return a Signal or None (hold)."""
        ...
