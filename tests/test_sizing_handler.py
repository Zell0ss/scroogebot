"""Tests for /sizing handler: basket resolution and capital display."""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.handlers.sizing import cmd_sizing


def _make_update(tg_id: int = 100):
    update = MagicMock()
    update.effective_user.id = tg_id
    msg = MagicMock()
    msg.edit_text = AsyncMock()
    update.message.reply_text = AsyncMock(return_value=msg)
    return update, msg


def _make_context(args: list[str]):
    ctx = MagicMock()
    ctx.args = args
    return ctx


def _make_session(*execute_results):
    session = MagicMock()
    session.execute = AsyncMock(side_effect=list(execute_results))
    return session


def _exec(value=None):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _exec_all(values: list):
    r = MagicMock()
    r.all.return_value = values
    return r


def _wrap(session):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# /sizing — basket name appears in output when user has active basket
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sizing_shows_active_basket_in_output():
    """When user has an active basket, its name must appear in the sizing output."""
    update, msg = _make_update()
    ctx = _make_context(["SAN.MC"])

    user = MagicMock()
    user.active_basket_id = 7
    basket = MagicMock(id=7, cash=Decimal("8000"), broker="paper")
    basket.name = "Mi Ahorro"

    # Session: 1=ticker-basket lookup, 2=user lookup, 3=basket-by-id lookup
    session = _make_session(
        _exec_all([]),          # no basket contains SAN.MC
        _exec(user),
        _exec(basket),
    )

    from src.sizing.engine import calculate_sizing
    from src.sizing.models import SizingResult

    fake_result = MagicMock(spec=SizingResult)
    fake_result.ticker = "SAN.MC"
    fake_result.company_name = "Banco Santander"
    fake_result.precio = 4.5
    fake_result.stop_loss = 4.0
    fake_result.stop_tipo = "ATR×2"
    fake_result.atr = 0.25
    fake_result.distancia = 0.5
    fake_result.distancia_pct = 11.1
    fake_result.acciones = 10
    fake_result.factor_limite = "riesgo"
    fake_result.nominal = 45.0
    fake_result.pct_cartera = 0.56
    fake_result.riesgo_maximo = 60.0
    fake_result.riesgo_real = 5.0
    fake_result.com_compra = 2.0
    fake_result.com_venta = 2.0
    fake_result.broker_nombre = "paper"
    fake_result.capital_total = 8000.0
    fake_result.aviso = None

    with (
        patch("src.bot.handlers.sizing.async_session_factory", return_value=_wrap(session)),
        patch("src.bot.handlers.sizing.calculate_sizing", return_value=fake_result),
    ):
        await cmd_sizing(update, ctx)

    text = msg.edit_text.call_args[0][0]
    assert "Mi Ahorro" in text, f"Basket name must appear in output. Got:\n{text}"


@pytest.mark.asyncio
async def test_sizing_uses_basket_cash_as_capital():
    """calculate_sizing must be called with capital_total = basket.cash."""
    update, msg = _make_update()
    ctx = _make_context(["SAN.MC"])

    user = MagicMock()
    user.active_basket_id = 7
    basket = MagicMock(id=7, cash=Decimal("6500"), broker="paper")
    basket.name = "Mi Ahorro"

    session = _make_session(
        _exec_all([]),
        _exec(user),
        _exec(basket),
    )

    with (
        patch("src.bot.handlers.sizing.async_session_factory", return_value=_wrap(session)),
        patch("src.bot.handlers.sizing.calculate_sizing") as mock_calc,
    ):
        mock_result = MagicMock()
        mock_result.ticker = "SAN.MC"
        mock_result.company_name = "SAN.MC"
        mock_result.precio = 4.5
        mock_result.stop_loss = 4.0
        mock_result.stop_tipo = "ATR×2"
        mock_result.atr = 0.25
        mock_result.distancia = 0.5
        mock_result.distancia_pct = 11.1
        mock_result.acciones = 10
        mock_result.factor_limite = "riesgo"
        mock_result.nominal = 45.0
        mock_result.pct_cartera = 0.56
        mock_result.riesgo_maximo = 48.75
        mock_result.riesgo_real = 5.0
        mock_result.com_compra = 2.0
        mock_result.com_venta = 2.0
        mock_result.broker_nombre = "paper"
        mock_result.capital_total = 6500.0
        mock_result.aviso = None
        mock_calc.return_value = mock_result

        await cmd_sizing(update, ctx)

    call_kwargs = mock_calc.call_args
    capital_passed = call_kwargs.kwargs.get("capital_total") or call_kwargs[1].get("capital_total")
    assert capital_passed == pytest.approx(6500.0), (
        f"capital_total passed to calculate_sizing must equal basket.cash=6500. Got: {capital_passed}"
    )
