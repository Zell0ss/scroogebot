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

    engine._anthropic_client.messages.create = AsyncMock(return_value=mock_response)
    result = await engine._build_explanation("rsi", "SELL", "RSI saliendo...", ctx)

    assert result == "El RSI ha tocado sobrecompra..."


@pytest.mark.asyncio
async def test_build_explanation_returns_none_on_api_failure():
    """If Haiku call fails, returns None (alert is still sent without explanation)."""
    engine = AlertEngine()
    ctx = _make_ctx()

    engine._anthropic_client.messages.create = AsyncMock(side_effect=Exception("timeout"))
    result = await engine._build_explanation("rsi", "SELL", "RSI saliendo...", ctx)

    assert result is None


@pytest.mark.asyncio
async def test_notify_advanced_mode_does_not_call_anthropic():
    """When user.advanced_mode=True, _notify must NOT call AsyncAnthropic."""
    from src.db.models import BasketMember, User

    engine = AlertEngine()

    # Spy on the already-created client's messages.create
    engine._anthropic_client.messages.create = AsyncMock()

    # Give engine a mock app with a bot
    mock_app = MagicMock()
    mock_app.bot.send_message = AsyncMock()
    engine.app = mock_app

    # Build a minimal Alert mock
    alert = MagicMock()
    alert.id = 42
    alert.basket_id = 1
    alert.signal = "SELL"
    alert.strategy = "rsi"
    alert.reason = "RSI saliendo de zona de sobrecompra (72.1)"
    alert.price = Decimal("4.18")

    ctx = _make_ctx(confidence=0.7)

    # User with advanced_mode=True
    advanced_user = MagicMock(spec=User)
    advanced_user.tg_id = 999
    advanced_user.advanced_mode = True

    member = MagicMock(spec=BasketMember)

    # Mock the session to return the advanced user
    mock_result = MagicMock()
    mock_result.all.return_value = [(member, advanced_user)]
    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("src.alerts.engine.async_session_factory", return_value=mock_cm):
        await engine._notify(alert, "MiCesta", "SAN.MC", ctx)

    # messages.create should never have been called for an advanced_mode user
    engine._anthropic_client.messages.create.assert_not_called()
    # But the message should still have been sent
    mock_app.bot.send_message.assert_called_once()
