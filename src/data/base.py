from abc import ABC, abstractmethod
from decimal import Decimal
from src.data.models import Price, OHLCV


class DataProvider(ABC):
    @abstractmethod
    def get_current_price(self, ticker: str) -> Price: ...

    @abstractmethod
    def get_historical(self, ticker: str, period: str = "3mo", interval: str = "1d") -> OHLCV: ...

    @abstractmethod
    def get_atr(self, ticker: str, period: int = 14) -> Decimal: ...

    def get_fx_rate(self, from_currency: str, to_currency: str) -> Decimal:
        if from_currency == to_currency:
            return Decimal("1")
        fx_ticker = f"{from_currency}{to_currency}=X"
        return self.get_current_price(fx_ticker).price
