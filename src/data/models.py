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
