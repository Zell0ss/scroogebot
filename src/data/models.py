from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import pandas as pd


@dataclass
class Price:
    ticker: str
    price: Decimal
    currency: str


@dataclass
class OHLCV:
    ticker: str
    data: pd.DataFrame  # columns: Open, High, Low, Close, Volume; DatetimeIndex


@dataclass
class SearchResult:
    ticker:      str
    name:        str
    exchange:    str
    type:        str        # "Equity", "ETF", "Fund", etc.
    in_basket:   bool
    basket_name: str | None
