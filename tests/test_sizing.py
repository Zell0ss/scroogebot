import pytest
from src.sizing.models import CommissionStructure


def test_fixed_commission():
    c = CommissionStructure(comision_fija=2.0)
    assert c.calcular(500.0) == 2.0
    assert c.calcular(5000.0) == 2.0


def test_pct_commission_no_limits():
    c = CommissionStructure(comision_pct=0.12)
    assert c.calcular(1000.0) == pytest.approx(1.2)


def test_pct_commission_with_minimum():
    c = CommissionStructure(comision_pct=0.12, comision_minima=3.0)
    assert c.calcular(100.0) == 3.0      # 0.12 < 3.0 → floor applies
    assert c.calcular(5000.0) == pytest.approx(6.0)  # 6.0 > 3.0 → no floor


def test_pct_commission_with_maximum():
    c = CommissionStructure(comision_pct=0.12, comision_minima=3.0, comision_maxima=25.0)
    assert c.calcular(30_000.0) == 25.0  # 36.0 > 25.0 → ceiling applies


def test_zero_commission():
    c = CommissionStructure()
    assert c.calcular(10_000.0) == 0.0


from unittest.mock import MagicMock, patch
import pandas as pd
from decimal import Decimal
from src.data.yahoo import YahooDataProvider


def _make_ohlcv(n=30):
    """Synthetic OHLCV: flat price, H-L spread of 4."""
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "Open":   [100.0] * n,
        "High":   [102.0] * n,
        "Low":    [98.0]  * n,
        "Close":  [100.0] * n,
        "Volume": [1000]  * n,
    }, index=idx)


def test_get_atr_returns_decimal():
    provider = YahooDataProvider()
    with patch.object(provider, "get_historical") as mock_hist:
        mock_ohlcv = MagicMock()
        mock_ohlcv.data = _make_ohlcv(30)
        mock_hist.return_value = mock_ohlcv
        atr = provider.get_atr("AAPL")
    assert isinstance(atr, Decimal)
    assert atr > 0


def test_get_atr_flat_prices_gives_small_value():
    """Flat OHLCV (H-L always 4): ATR should be around 4."""
    provider = YahooDataProvider()
    with patch.object(provider, "get_historical") as mock_hist:
        mock_ohlcv = MagicMock()
        mock_ohlcv.data = _make_ohlcv(30)
        mock_hist.return_value = mock_ohlcv
        atr = provider.get_atr("AAPL")
    assert Decimal("1") <= atr <= Decimal("10")


from src.sizing.broker import BROKER_REGISTRY, Broker


def test_broker_registry_has_required_keys():
    assert "degiro" in BROKER_REGISTRY
    assert "myinvestor" in BROKER_REGISTRY
    assert "paper" in BROKER_REGISTRY


def test_degiro_commission_is_fixed_two_euros():
    broker = BROKER_REGISTRY["degiro"]
    assert broker.commissions.calcular(500.0) == 2.0
    assert broker.commissions.calcular(50_000.0) == 2.0


def test_myinvestor_commission_respects_min_max():
    broker = BROKER_REGISTRY["myinvestor"]
    assert broker.commissions.calcular(100.0) == 3.0      # min €3
    assert broker.commissions.calcular(30_000.0) == 25.0  # max €25


def test_paper_commission_same_as_degiro():
    paper = BROKER_REGISTRY["paper"]
    degiro = BROKER_REGISTRY["degiro"]
    assert paper.commissions.calcular(1000.0) == degiro.commissions.calcular(1000.0)


def test_broker_get_price_delegates_to_provider():
    from unittest.mock import MagicMock, patch
    from decimal import Decimal
    broker = BROKER_REGISTRY["degiro"]
    mock_price = MagicMock()
    mock_price.price = Decimal("100.0")
    mock_price.currency = "EUR"
    with patch.object(broker._provider, "get_current_price", return_value=mock_price):
        result = broker.get_price("SAN.MC")
    assert result.price == Decimal("100.0")
