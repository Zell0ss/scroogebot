from src.data.models import SearchResult


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
