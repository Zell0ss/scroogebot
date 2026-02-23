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


def _exec_all(pairs: list):
    """Build an execute-result mock whose .all() returns a list of tuples/pairs."""
    r = MagicMock()
    r.all.return_value = pairs
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
    # Note: MagicMock(name=...) sets mock display name, not .name attr — set separately
    basket = MagicMock(id=10, active=True)
    basket.name = "TechGrowth"
    owner_membership = MagicMock()
    session = _make_session(
        _exec(caller),
        _exec(basket),
        _exec(owner_membership),
        _exec_all([]),              # no open positions (Position, Asset) pairs
    )

    update = _make_update()
    ctx = _make_context(["TechGrowth"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_eliminarcesta(update, ctx)

    assert basket.active is False
    # Name must be mangled with #{id:x} so it cannot block future reuse
    assert basket.name != "TechGrowth", "Name must be mangled on deactivation"
    assert basket.name.startswith("TechGrowth#"), f"Expected mangled name, got: {basket.name}"
    session.commit.assert_awaited_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "TechGrowth" in reply


# ---------------------------------------------------------------------------
# /eliminarcesta — blocked by open positions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_eliminarcesta_with_positions():
    caller = MagicMock(id=1)
    basket = MagicMock(id=10, name="TechGrowth", active=True)
    owner_membership = MagicMock()
    pos_aapl  = MagicMock(); asset_aapl  = MagicMock(ticker="AAPL")
    pos_san   = MagicMock(); asset_san   = MagicMock(ticker="SAN.MC")
    session = _make_session(
        _exec(caller),
        _exec(basket),
        _exec(owner_membership),
        _exec_all([(pos_aapl, asset_aapl), (pos_san, asset_san)]),
    )

    update = _make_update()
    ctx = _make_context(["TechGrowth"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_eliminarcesta(update, ctx)

    assert basket.active is True  # unchanged
    session.commit.assert_not_awaited()
    reply = update.message.reply_text.call_args[0][0]
    assert "posiciones" in reply.lower()


@pytest.mark.asyncio
async def test_nuevacesta_underscores_not_mangled_by_markdown():
    """Basket names with underscores must survive Markdown rendering intact."""
    caller = MagicMock(id=1)
    session = _make_session(_exec(caller), _exec(None))
    session.flush = AsyncMock()
    session.add = MagicMock()

    update = _make_update()
    ctx = _make_context(["Mi_Ahorro_jmc", "stop_loss"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_nuevacesta(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    # Name must appear escaped or in backticks — plain underscores cause Markdown italics
    assert "`Mi_Ahorro_jmc`" in reply or "Mi\\_Ahorro\\_jmc" in reply


# ---------------------------------------------------------------------------
# /eliminarcesta — blocked for non-OWNER
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nuevacesta_reply_includes_capital():
    """Bot must confirm the €10.000 starting capital in its reply."""
    caller = MagicMock(id=1)
    session = _make_session(_exec(caller), _exec(None))
    session.flush = AsyncMock()
    session.add = MagicMock()

    update = _make_update()
    ctx = _make_context(["MiCesta", "stop_loss"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_nuevacesta(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    assert "10.000" in reply or "10000" in reply


@pytest.mark.asyncio
async def test_nuevacesta_dup_check_filters_by_active():
    """Duplicate-name check must only block if an ACTIVE basket with that name exists.
    Inactive baskets with the same name must be ignored so names can be reused."""
    caller = MagicMock(id=1)
    session = _make_session(_exec(caller), _exec(None))
    session.flush = AsyncMock()
    session.add = MagicMock()

    update = _make_update()
    ctx = _make_context(["Mi_Ahorro_jmc", "stop_loss"])

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_nuevacesta(update, ctx)

    # The second execute call is the dup-check query.
    dup_query = session.execute.call_args_list[1][0][0]
    query_str = str(dup_query)
    # "AND baskets.active" must appear in WHERE — not just in the SELECT column list
    assert "AND baskets.active" in query_str, (
        "Duplicate-name check must filter by active=True so inactive baskets "
        "don't block name reuse. Got query: " + query_str
    )


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


# ---------------------------------------------------------------------------
# /estrategia — stop_loss_pct parsing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_estrategia_changes_strategy_and_stop_loss_pct():
    """/estrategia MiCesta rsi 8 → changes strategy to rsi AND stop_loss_pct to 8."""
    update = _make_update()
    ctx = _make_context(["MiCesta", "rsi", "8"])

    caller = MagicMock(id=1)
    basket = MagicMock(id=10, strategy="stop_loss", stop_loss_pct=None, active=True)
    basket.name = "MiCesta"
    owner = MagicMock()

    session = _make_session(
        _exec(caller),
        _exec(basket),
        _exec(owner),
    )

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_estrategia(update, ctx)

    assert basket.strategy == "rsi"
    assert basket.stop_loss_pct == Decimal("8")


@pytest.mark.asyncio
async def test_estrategia_changes_only_stop_loss_pct():
    """/estrategia MiCesta 10 → keeps strategy, changes stop_loss_pct to 10."""
    update = _make_update()
    ctx = _make_context(["MiCesta", "10"])

    caller = MagicMock(id=1)
    basket = MagicMock(id=10, strategy="rsi", stop_loss_pct=None, active=True)
    basket.name = "MiCesta"
    owner = MagicMock()

    session = _make_session(
        _exec(caller),
        _exec(basket),
        _exec(owner),
    )

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_estrategia(update, ctx)

    assert basket.strategy == "rsi"   # unchanged
    assert basket.stop_loss_pct == Decimal("10")


@pytest.mark.asyncio
async def test_estrategia_zero_disables_stop_loss():
    """/estrategia MiCesta rsi 0 → disables stop_loss_pct (sets to None)."""
    update = _make_update()
    ctx = _make_context(["MiCesta", "rsi", "0"])

    caller = MagicMock(id=1)
    basket = MagicMock(id=10, strategy="stop_loss", stop_loss_pct=Decimal("8"), active=True)
    basket.name = "MiCesta"
    owner = MagicMock()

    session = _make_session(
        _exec(caller),
        _exec(basket),
        _exec(owner),
    )

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_estrategia(update, ctx)

    assert basket.stop_loss_pct is None


@pytest.mark.asyncio
async def test_estrategia_view_shows_stop_loss_pct():
    """/estrategia MiCesta (view mode) → response shows stop_loss_pct if set."""
    update = _make_update()
    ctx = _make_context(["MiCesta"])

    caller = MagicMock(id=1)
    basket = MagicMock(id=10, strategy="rsi", stop_loss_pct=Decimal("8"), active=True)
    basket.name = "MiCesta"

    session = _make_session(
        _exec(caller),
        _exec(basket),
    )

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_estrategia(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    assert "8" in reply
    assert "stop" in reply.lower() or "Stop" in reply


# ---------------------------------------------------------------------------
# /nuevacesta — stop_loss_pct optional parameter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nuevacesta_with_stop_loss_pct():
    """/nuevacesta MiCesta rsi 8 → basket created with stop_loss_pct=8."""
    update = _make_update()
    ctx = _make_context(["MiCesta", "rsi", "8"])

    caller = MagicMock(id=1)

    session = _make_session(
        _exec(caller),       # User lookup
        _exec(None),         # Basket name not taken
    )
    session.flush = AsyncMock()

    created_basket = None
    original_add = session.add

    def capture_add(obj):
        nonlocal created_basket
        from src.db.models import Basket
        if isinstance(obj, Basket):
            created_basket = obj
        original_add(obj)

    session.add = capture_add

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_nuevacesta(update, ctx)

    assert created_basket is not None, "A Basket must have been added to session"
    assert created_basket.strategy == "rsi"
    assert created_basket.stop_loss_pct == Decimal("8")


@pytest.mark.asyncio
async def test_nuevacesta_without_stop_loss_pct():
    """/nuevacesta MiCesta rsi → basket created with stop_loss_pct=None."""
    update = _make_update()
    ctx = _make_context(["MiCesta", "rsi"])

    caller = MagicMock(id=1)

    session = _make_session(
        _exec(caller),
        _exec(None),
    )
    session.flush = AsyncMock()

    created_basket = None
    original_add = session.add

    def capture_add(obj):
        nonlocal created_basket
        from src.db.models import Basket
        if isinstance(obj, Basket):
            created_basket = obj
        original_add(obj)

    session.add = capture_add

    with patch("src.bot.handlers.admin.async_session_factory", return_value=_wrap(session)):
        await cmd_nuevacesta(update, ctx)

    assert created_basket is not None
    assert created_basket.stop_loss_pct is None
