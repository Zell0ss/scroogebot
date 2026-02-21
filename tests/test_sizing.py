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


import math
from src.sizing.engine import calculate_sizing


def _mock_broker_engine(precio=10.0, atr=0.5, currency="EUR"):
    """Helper: mock broker that returns fixed price/atr, fixed €2 commission."""
    from unittest.mock import MagicMock
    from decimal import Decimal
    from src.sizing.models import CommissionStructure
    broker = MagicMock()
    price_obj = MagicMock()
    price_obj.price = Decimal(str(precio))
    price_obj.currency = currency
    broker.get_price.return_value = price_obj
    broker.get_atr.return_value = Decimal(str(atr))
    broker.get_fx_rate.return_value = Decimal("1")
    broker.commissions = CommissionStructure(comision_fija=2.0)
    broker.name = "degiro"
    return broker


def test_sizing_manual_stop_sets_tipo():
    broker = _mock_broker_engine(precio=10.0, atr=0.5)
    result = calculate_sizing("SAN.MC", stop_loss_manual=9.0, broker=broker)
    assert result.stop_tipo == "manual"
    assert result.stop_loss == pytest.approx(9.0)
    assert result.distancia == pytest.approx(1.0)


def test_sizing_auto_stop_uses_atr():
    broker = _mock_broker_engine(precio=10.0, atr=0.5)
    result = calculate_sizing("SAN.MC", stop_loss_manual=None, broker=broker)
    assert result.stop_tipo == "ATR×2"
    assert result.stop_loss == pytest.approx(9.0)  # 10.0 - 2*0.5


def test_sizing_limited_by_riesgo():
    # precio=10, stop=9, distancia=1
    # riesgo_max=150, com_c=2, com_v=2 → riesgo_disp=146
    # acciones_riesgo = floor(146/1) = 146
    # acciones_nominal = floor(4000/10) = 400
    # min(146, 400) = 146 → limited by riesgo
    broker = _mock_broker_engine(precio=10.0, atr=0.5)
    result = calculate_sizing("SAN.MC", stop_loss_manual=9.0, broker=broker)
    assert result.acciones == 146
    assert result.factor_limite == "riesgo"


def test_sizing_limited_by_nominal():
    # precio=100, stop=99, distancia=1
    # riesgo_max=150, com=4 → riesgo_disp=146 → acciones_riesgo=146
    # acciones_nominal = floor(4000/100) = 40
    # min(146, 40) = 40 → limited by nominal
    broker = _mock_broker_engine(precio=100.0, atr=1.0)
    result = calculate_sizing("AAPL", stop_loss_manual=99.0, broker=broker)
    assert result.acciones == 40
    assert result.factor_limite == "nominal"


def test_sizing_stop_muy_alejado_genera_aviso():
    # stop 20% below price → distancia_pct=20 > 15 threshold
    broker = _mock_broker_engine(precio=10.0, atr=0.5)
    result = calculate_sizing("SAN.MC", stop_loss_manual=8.0, broker=broker)
    assert result.aviso is not None
    assert "alejado" in result.aviso.lower()


def test_sizing_riesgo_real_no_excede_maximo():
    broker = _mock_broker_engine(precio=10.0, atr=0.5)
    result = calculate_sizing("SAN.MC", stop_loss_manual=9.0, broker=broker)
    # riesgo_real = acciones*distancia + com_compra + com_venta
    # = 146*1 + 2 + 2 = 150
    assert result.riesgo_real <= result.riesgo_maximo + 0.01


def test_sizing_pct_commission_iterative_convergence():
    """MyInvestor 0.12%, min 3, max 25: riesgo_real must not exceed riesgo_max."""
    from unittest.mock import MagicMock
    from decimal import Decimal
    from src.sizing.models import CommissionStructure
    broker = MagicMock()
    price_obj = MagicMock()
    price_obj.price = Decimal("50.0")
    price_obj.currency = "EUR"
    broker.get_price.return_value = price_obj
    broker.get_atr.return_value = Decimal("1.0")
    broker.get_fx_rate.return_value = Decimal("1")
    broker.commissions = CommissionStructure(comision_pct=0.12, comision_minima=3.0, comision_maxima=25.0)
    broker.name = "myinvestor"
    result = calculate_sizing("MSFT", stop_loss_manual=48.0, broker=broker)
    assert result.riesgo_real <= result.riesgo_maximo + 0.01
    assert result.acciones >= 0
