"""Tests for /compra and /vende handler basket resolution."""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.handlers.orders import cmd_compra, cmd_vende


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_update(tg_id: int = 100):
    update = MagicMock()
    update.effective_user.id = tg_id
    update.message.reply_text = AsyncMock()
    return update


def _make_context(args: list[str]):
    ctx = MagicMock()
    ctx.args = args
    return ctx


def _make_session(*execute_results):
    session = MagicMock()
    session.execute = AsyncMock(side_effect=list(execute_results))
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session


def _exec(value=None):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _wrap(session):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _mock_price(price: float = 150.0, currency: str = "USD"):
    p = MagicMock()
    p.price = Decimal(str(price))
    p.currency = currency
    return p


# ---------------------------------------------------------------------------
# /compra — uses active basket from user selection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compra_uses_active_basket():
    basket = MagicMock(id=10, name="Cesta Agresiva", cash=Decimal("10000"))
    asset = MagicMock(id=5, ticker="AAPL")
    caller = MagicMock(id=1, active_basket_id=10)

    session = _make_session(_exec(caller), _exec(asset), _exec(basket))

    update = _make_update()
    ctx = _make_context(["AAPL", "5"])

    mock_executor = AsyncMock()
    with patch("src.bot.handlers.orders.async_session_factory", return_value=_wrap(session)), \
         patch("src.bot.handlers.orders._provider") as mock_prov, \
         patch("src.bot.handlers.orders._executor", mock_executor):
        mock_prov.get_current_price.return_value = _mock_price(150.0)
        await cmd_compra(update, ctx)

    mock_executor.buy.assert_awaited_once()
    call_kwargs = mock_executor.buy.call_args
    assert call_kwargs[0][1] == 10  # basket_id


@pytest.mark.asyncio
async def test_compra_no_basket_selected_shows_error():
    caller = MagicMock(id=1, active_basket_id=None)
    asset = MagicMock(id=5, ticker="AAPL")
    session = _make_session(_exec(caller), _exec(asset))

    update = _make_update()
    ctx = _make_context(["AAPL", "5"])

    with patch("src.bot.handlers.orders.async_session_factory", return_value=_wrap(session)), \
         patch("src.bot.handlers.orders._provider") as mock_prov:
        mock_prov.get_current_price.return_value = _mock_price()
        await cmd_compra(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    assert "sel" in reply.lower() or "cesta" in reply.lower()


@pytest.mark.asyncio
async def test_compra_inline_override():
    """@CestaName override uses that basket instead of active_basket_id."""
    active_basket = MagicMock(id=99, name="Otra Cesta", cash=Decimal("5000"))
    override_basket = MagicMock(id=10, name="Cesta Agresiva", cash=Decimal("10000"))
    asset = MagicMock(id=5, ticker="AAPL")
    caller = MagicMock(id=1, active_basket_id=99)

    # execute calls: caller, asset, basket-by-name
    session = _make_session(_exec(caller), _exec(asset), _exec(override_basket))

    update = _make_update()
    ctx = _make_context(["AAPL", "5", "@Cesta", "Agresiva"])

    mock_executor = AsyncMock()
    with patch("src.bot.handlers.orders.async_session_factory", return_value=_wrap(session)), \
         patch("src.bot.handlers.orders._provider") as mock_prov, \
         patch("src.bot.handlers.orders._executor", mock_executor):
        mock_prov.get_current_price.return_value = _mock_price()
        await cmd_compra(update, ctx)

    mock_executor.buy.assert_awaited_once()
    assert mock_executor.buy.call_args[0][1] == 10  # override basket id


@pytest.mark.asyncio
async def test_compra_context_line_in_reply():
    """Confirmation message shows 🗂 basket context line."""
    basket = MagicMock(id=10, name="Cesta Agresiva", cash=Decimal("10000"))
    asset = MagicMock(id=5, ticker="AAPL")
    caller = MagicMock(id=1, active_basket_id=10)

    session = _make_session(_exec(caller), _exec(asset), _exec(basket))

    update = _make_update()
    ctx = _make_context(["AAPL", "5"])

    mock_executor = AsyncMock()
    with patch("src.bot.handlers.orders.async_session_factory", return_value=_wrap(session)), \
         patch("src.bot.handlers.orders._provider") as mock_prov, \
         patch("src.bot.handlers.orders._executor", mock_executor):
        mock_prov.get_current_price.return_value = _mock_price(150.0)
        await cmd_compra(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    assert "Cesta Agresiva" in reply


@pytest.mark.asyncio
async def test_vende_uses_active_basket():
    basket = MagicMock(id=10, name="Cesta Agresiva", cash=Decimal("10000"))
    asset = MagicMock(id=5, ticker="AAPL")
    caller = MagicMock(id=1, active_basket_id=10)

    session = _make_session(_exec(caller), _exec(asset), _exec(basket))

    update = _make_update()
    ctx = _make_context(["AAPL", "5"])

    mock_executor = AsyncMock()
    with patch("src.bot.handlers.orders.async_session_factory", return_value=_wrap(session)), \
         patch("src.bot.handlers.orders._provider") as mock_prov, \
         patch("src.bot.handlers.orders._executor", mock_executor):
        mock_prov.get_current_price.return_value = _mock_price(150.0)
        await cmd_vende(update, ctx)

    mock_executor.sell.assert_awaited_once()
    assert mock_executor.sell.call_args[0][1] == 10
