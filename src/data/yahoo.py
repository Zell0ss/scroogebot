import logging
from decimal import Decimal

import yfinance as yf
import pandas as pd

from src.data.base import DataProvider
from src.data.models import Price, OHLCV

logger = logging.getLogger(__name__)


class YahooDataProvider(DataProvider):
    def get_current_price(self, ticker: str) -> Price:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = Decimal(str(info.last_price))
        currency = getattr(info, "currency", "USD") or "USD"
        return Price(ticker=ticker, price=price, currency=currency)

    def get_historical(self, ticker: str, period: str = "3mo", interval: str = "1d") -> OHLCV:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            raise ValueError(f"No data for {ticker}")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return OHLCV(ticker=ticker, data=df)
