import logging
from decimal import Decimal

import yfinance as yf
import pandas as pd
import ta.volatility

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

    def get_atr(self, ticker: str, period: int = 14) -> Decimal:
        ohlcv = self.get_historical(ticker, period="3mo", interval="1d")
        df = ohlcv.data
        atr_series = ta.volatility.AverageTrueRange(
            high=df["High"], low=df["Low"], close=df["Close"], window=period
        ).average_true_range()
        last = atr_series.dropna().iloc[-1]
        return Decimal(str(round(float(last), 4)))

    def search_yahoo(self, query: str, max_results: int = 8) -> list:
        """Search Yahoo Finance by name or ticker. Returns list[SearchResult]."""
        from src.data.models import SearchResult
        try:
            quotes = yf.Search(query, max_results=max_results).quotes
        except Exception as e:
            logger.warning("yf.Search failed for %r: %s", query, e)
            return []
        results = []
        for q in quotes:
            ticker = q.get("symbol", "")
            if not ticker:
                continue
            name = q.get("shortname") or q.get("longname") or ticker
            results.append(SearchResult(
                ticker=ticker,
                name=name,
                exchange=q.get("exchange", ""),
                type=q.get("typeDisp", "Equity"),
                in_basket=False,
                basket_name=None,
            ))
        return results
