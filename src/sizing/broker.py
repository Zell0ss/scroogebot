from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal

from src.data.yahoo import YahooDataProvider
from src.data.models import Price
from src.sizing.models import CommissionStructure


@dataclass
class Broker:
    name: str
    _provider: YahooDataProvider
    commissions: CommissionStructure

    def get_price(self, ticker: str) -> Price:
        return self._provider.get_current_price(ticker)

    def get_atr(self, ticker: str, period: int = 14) -> Decimal:
        return self._provider.get_atr(ticker, period)

    def get_fx_rate(self, from_currency: str, to_currency: str) -> Decimal:
        return self._provider.get_fx_rate(from_currency, to_currency)


_yahoo = YahooDataProvider()

DEGIRO_FEES = CommissionStructure(comision_fija=2.0)
MYINVESTOR_FEES = CommissionStructure(
    comision_pct=0.12,
    comision_minima=3.0,
    comision_maxima=25.0,
)

BROKER_REGISTRY: dict[str, Broker] = {
    "degiro":     Broker(name="degiro",     _provider=_yahoo, commissions=DEGIRO_FEES),
    "myinvestor": Broker(name="myinvestor", _provider=_yahoo, commissions=MYINVESTOR_FEES),
    "paper":      Broker(name="paper",      _provider=_yahoo, commissions=DEGIRO_FEES),
}
