"""Integration tests — requires network access."""
import pytest
from decimal import Decimal
from src.data.yahoo import YahooDataProvider


@pytest.fixture
def provider():
    return YahooDataProvider()


def test_get_current_price(provider):
    price = provider.get_current_price("AAPL")
    assert price.ticker == "AAPL"
    assert price.price > Decimal("10")
    assert price.currency == "USD"


def test_get_historical(provider):
    ohlcv = provider.get_historical("AAPL", period="1mo", interval="1d")
    assert ohlcv.ticker == "AAPL"
    assert not ohlcv.data.empty
    assert "Close" in ohlcv.data.columns


def test_get_fx_rate(provider):
    rate = provider.get_fx_rate("EUR", "USD")
    assert Decimal("0.5") < rate < Decimal("2.0")
