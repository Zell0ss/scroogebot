import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.handlers.admin import cmd_estrategia, cmd_nuevacesta, cmd_eliminarcesta


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
    """Mock session with execute returning given results in sequence."""
    session = MagicMock()
    session.execute = AsyncMock(side_effect=list(execute_results))
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


def _exec(value=None):
    """Build a single execute-result mock with scalar_one_or_none."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _exec_scalars(values: list):
    """Build an execute-result mock whose .scalars().all() returns a list."""
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    return r


def _wrap(session):
    """Wrap a session in an async context manager mock."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# /estrategia — read (no second arg)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_estrategia_read():
    caller = MagicMock(id=1)
    basket = MagicMock(id=10, name="MiCesta", strategy="ma_crossover")
    session = _make_session(_exec(caller), _exec(basket))

    update = _make_update()
    ctx = _make_context(["MiCesta"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_estrategia(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    assert "ma_crossover" in reply
    assert "MiCesta" in reply


# ---------------------------------------------------------------------------
# /estrategia — change (OWNER)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_estrategia_change_ok():
    caller = MagicMock(id=1)
    basket = MagicMock(id=10, name="MiCesta", strategy="ma_crossover")
    owner_membership = MagicMock()
    session = _make_session(_exec(caller), _exec(basket), _exec(owner_membership))

    update = _make_update()
    ctx = _make_context(["MiCesta", "rsi"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_estrategia(update, ctx)

    assert basket.strategy == "rsi"
    session.commit.assert_awaited_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "rsi" in reply


# ---------------------------------------------------------------------------
# /estrategia — invalid strategy name
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_estrategia_invalid():
    update = _make_update()
    ctx = _make_context(["MiCesta", "badstrat"])

    # No DB calls expected — validation fails before DB
    session = _make_session()
    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_estrategia(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    assert "no válida" in reply or "Disponibles" in reply


# ---------------------------------------------------------------------------
# /estrategia — change blocked for non-OWNER
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_estrategia_not_owner():
    caller = MagicMock(id=2)
    basket = MagicMock(id=10, name="MiCesta", strategy="ma_crossover")
    # owner_check returns None → not an OWNER
    session = _make_session(_exec(caller), _exec(basket), _exec(None))

    update = _make_update()
    ctx = _make_context(["MiCesta", "rsi"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_estrategia(update, ctx)

    assert basket.strategy == "ma_crossover"  # unchanged
    reply = update.message.reply_text.call_args[0][0]
    assert "OWNER" in reply


# ---------------------------------------------------------------------------
# /estrategia — basket not found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_estrategia_basket_not_found():
    caller = MagicMock(id=1)
    session = _make_session(_exec(caller), _exec(None))

    update = _make_update()
    ctx = _make_context(["NoExiste"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_estrategia(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    assert "no encontrada" in reply or "NoExiste" in reply


# ---------------------------------------------------------------------------
# /nuevacesta — success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nuevacesta_ok():
    caller = MagicMock(id=1)
    # dup check returns None (no duplicate)
    session = _make_session(_exec(caller), _exec(None))
    session.flush = AsyncMock()

    # Capture added objects
    added = []
    session.add = MagicMock(side_effect=added.append)

    update = _make_update()
    ctx = _make_context(["TechGrowth", "rsi"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_nuevacesta(update, ctx)

    session.commit.assert_awaited_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "TechGrowth" in reply
    assert "rsi" in reply
    assert "OWNER" in reply


# ---------------------------------------------------------------------------
# /nuevacesta — duplicate name
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nuevacesta_duplicate():
    caller = MagicMock(id=1)
    existing_basket = MagicMock(name="TechGrowth")
    session = _make_session(_exec(caller), _exec(existing_basket))

    update = _make_update()
    ctx = _make_context(["TechGrowth", "rsi"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_nuevacesta(update, ctx)

    session.add.assert_not_called()
    reply = update.message.reply_text.call_args[0][0]
    assert "ya existe" in reply.lower() or "TechGrowth" in reply


# ---------------------------------------------------------------------------
# /nuevacesta — invalid strategy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nuevacesta_invalid_strategy():
    update = _make_update()
    ctx = _make_context(["TechGrowth", "badstrat"])

    session = _make_session()
    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_nuevacesta(update, ctx)

    # Should fail before touching DB
    session.add.assert_not_called()
    reply = update.message.reply_text.call_args[0][0]
    assert "no válida" in reply or "Disponibles" in reply


# ---------------------------------------------------------------------------
# /eliminarcesta — success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_eliminarcesta_ok():
    caller = MagicMock(id=1)
    basket = MagicMock(id=10, name="TechGrowth", active=True)
    owner_membership = MagicMock()
    session = _make_session(
        _exec(caller),
        _exec(basket),
        _exec(owner_membership),
        _exec_scalars([]),          # no open positions
    )

    update = _make_update()
    ctx = _make_context(["TechGrowth"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_eliminarcesta(update, ctx)

    assert basket.active is False
    session.commit.assert_awaited_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "desactivada" in reply or "TechGrowth" in reply


# ---------------------------------------------------------------------------
# /eliminarcesta — blocked by open positions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_eliminarcesta_with_positions():
    caller = MagicMock(id=1)
    basket = MagicMock(id=10, name="TechGrowth", active=True)
    owner_membership = MagicMock()
    open_pos = [MagicMock(ticker="AAPL"), MagicMock(ticker="SAN.MC")]
    session = _make_session(
        _exec(caller),
        _exec(basket),
        _exec(owner_membership),
        _exec_scalars(open_pos),
    )

    update = _make_update()
    ctx = _make_context(["TechGrowth"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_eliminarcesta(update, ctx)

    assert basket.active is True  # unchanged
    session.commit.assert_not_awaited()
    reply = update.message.reply_text.call_args[0][0]
    assert "posiciones" in reply.lower()


# ---------------------------------------------------------------------------
# /eliminarcesta — blocked for non-OWNER
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_eliminarcesta_not_owner():
    caller = MagicMock(id=2)
    basket = MagicMock(id=10, name="TechGrowth", active=True)
    session = _make_session(
        _exec(caller),
        _exec(basket),
        _exec(None),               # not an OWNER
    )

    update = _make_update()
    ctx = _make_context(["TechGrowth"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_eliminarcesta(update, ctx)

    assert basket.active is True  # unchanged
    reply = update.message.reply_text.call_args[0][0]
    assert "OWNER" in reply
