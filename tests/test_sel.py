import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.handlers.baskets import cmd_sel


# ---------------------------------------------------------------------------
# Helpers (same pattern as test_basket_admin.py)
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


# ---------------------------------------------------------------------------
# /sel — show current (no args)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sel_no_args_shows_current():
    basket = MagicMock(name="Cesta Agresiva")
    basket.name = "Cesta Agresiva"
    caller = MagicMock(id=1, active_basket_id=10)
    session = _make_session(_exec(caller), _exec(basket))

    update = _make_update()
    ctx = _make_context([])

    with patch("src.bot.handlers.baskets.async_session_factory", return_value=_wrap(session)):
        await cmd_sel(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    assert "Cesta Agresiva" in reply


@pytest.mark.asyncio
async def test_sel_no_args_none_selected():
    caller = MagicMock(id=1, active_basket_id=None)
    session = _make_session(_exec(caller))

    update = _make_update()
    ctx = _make_context([])

    with patch("src.bot.handlers.baskets.async_session_factory", return_value=_wrap(session)):
        await cmd_sel(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    assert "ninguna" in reply.lower() or "seleccionada" in reply.lower() or "none" in reply.lower()


# ---------------------------------------------------------------------------
# /sel <nombre> — select basket
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sel_selects_basket():
    caller = MagicMock(id=1, active_basket_id=None)
    basket = MagicMock(id=10)
    basket.name = "Cesta Agresiva"
    session = _make_session(_exec(caller), _exec(basket))

    update = _make_update()
    ctx = _make_context(["Cesta", "Agresiva"])

    with patch("src.bot.handlers.baskets.async_session_factory", return_value=_wrap(session)):
        await cmd_sel(update, ctx)

    assert caller.active_basket_id == 10
    session.commit.assert_awaited_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "Cesta Agresiva" in reply


@pytest.mark.asyncio
async def test_sel_basket_not_found():
    caller = MagicMock(id=1, active_basket_id=None)
    session = _make_session(_exec(caller), _exec(None))

    update = _make_update()
    ctx = _make_context(["NoExiste"])

    with patch("src.bot.handlers.baskets.async_session_factory", return_value=_wrap(session)):
        await cmd_sel(update, ctx)

    assert caller.active_basket_id is None
    reply = update.message.reply_text.call_args[0][0]
    assert "no encontrada" in reply or "NoExiste" in reply


@pytest.mark.asyncio
async def test_sel_unregistered_user():
    session = _make_session(_exec(None))

    update = _make_update()
    ctx = _make_context(["Cesta", "Agresiva"])

    with patch("src.bot.handlers.baskets.async_session_factory", return_value=_wrap(session)):
        await cmd_sel(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    assert "start" in reply.lower()
