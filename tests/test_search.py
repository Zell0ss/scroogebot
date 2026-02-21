from unittest.mock import patch, MagicMock

from src.data.models import SearchResult
from src.data.yahoo import YahooDataProvider


def test_search_result_in_basket():
    r = SearchResult(
        ticker="SAN.MC",
        name="Banco Santander",
        exchange="MCE",
        type="Equity",
        in_basket=True,
        basket_name="Cesta Conservadora",
    )
    assert r.ticker == "SAN.MC"
    assert r.in_basket is True
    assert r.basket_name == "Cesta Conservadora"


def test_search_result_not_in_basket():
    r = SearchResult(
        ticker="SAN",
        name="Banco Santander S.A.",
        exchange="NYSE",
        type="Equity",
        in_basket=False,
        basket_name=None,
    )
    assert r.in_basket is False
    assert r.basket_name is None


def _mock_quotes():
    return [
        {"symbol": "SAN", "shortname": "Banco Santander S.A.", "exchange": "NYQ", "typeDisp": "Equity"},
        {"symbol": "SAN.MC", "longname": "BANCO SANTANDER S.A.", "exchange": "MCE", "typeDisp": "Equity"},
        {"symbol": "BSBR", "shortname": "Banco Santander Brasil", "exchange": "NYQ", "typeDisp": "Equity"},
    ]


def test_search_yahoo_returns_search_results():
    provider = YahooDataProvider()
    mock_search = MagicMock()
    mock_search.quotes = _mock_quotes()
    with patch("yfinance.Search", return_value=mock_search):
        results = provider.search_yahoo("banco santander", max_results=5)
    assert len(results) == 3
    assert all(isinstance(r, SearchResult) for r in results)
    assert results[0].ticker == "SAN"
    assert results[0].in_basket is False
    assert results[0].basket_name is None


def test_search_yahoo_uses_shortname_with_fallback():
    provider = YahooDataProvider()
    mock_search = MagicMock()
    # Only longname available (no shortname)
    mock_search.quotes = [
        {"symbol": "BSAC", "longname": "Banco Santander Chile", "exchange": "NYQ", "typeDisp": "Equity"},
    ]
    with patch("yfinance.Search", return_value=mock_search):
        results = provider.search_yahoo("santander chile")
    assert results[0].name == "Banco Santander Chile"


def test_search_yahoo_skips_empty_symbols():
    provider = YahooDataProvider()
    mock_search = MagicMock()
    mock_search.quotes = [
        {"symbol": "", "shortname": "Bad entry", "exchange": "NYQ", "typeDisp": "Equity"},
        {"symbol": "SAN", "shortname": "Banco Santander S.A.", "exchange": "NYQ", "typeDisp": "Equity"},
    ]
    with patch("yfinance.Search", return_value=mock_search):
        results = provider.search_yahoo("santander")
    assert len(results) == 1
    assert results[0].ticker == "SAN"


def test_search_yahoo_returns_empty_on_error():
    provider = YahooDataProvider()
    with patch("yfinance.Search", side_effect=Exception("network error")):
        results = provider.search_yahoo("santander")
    assert results == []
