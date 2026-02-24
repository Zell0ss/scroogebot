import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.alerts.engine import AlertEngine
from src.alerts.market_context import MarketContext


def _make_ctx(confidence: float = 0.7) -> MarketContext:
    return MarketContext(
        ticker="SAN.MC",
        price=Decimal("4.18"),
        sma20=4.25,
        sma50=4.10,
        rsi14=71.3,
        atr_pct=1.9,
        trend="lateral",
        position_qty=Decimal("20"),
        avg_price=Decimal("4.32"),
        pnl_pct=-3.2,
        confidence=confidence,
        suggested_qty=Decimal("20"),
    )


@pytest.mark.asyncio
async def test_build_explanation_returns_text():
    """_build_explanation returns the text from Haiku response."""
    engine = AlertEngine()
    ctx = _make_ctx()

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="El RSI ha tocado sobrecompra...")]

    with patch("src.alerts.engine.AsyncAnthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        result = await engine._build_explanation("rsi", "SELL", "RSI saliendo...", ctx)

    assert result == "El RSI ha tocado sobrecompra..."


@pytest.mark.asyncio
async def test_build_explanation_returns_none_on_api_failure():
    """If Haiku call fails, returns None (alert is still sent without explanation)."""
    engine = AlertEngine()
    ctx = _make_ctx()

    with patch("src.alerts.engine.AsyncAnthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("timeout"))
        mock_cls.return_value = mock_client
        result = await engine._build_explanation("rsi", "SELL", "RSI saliendo...", ctx)

    assert result is None
