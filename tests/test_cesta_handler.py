"""Tests for /cesta handler — stop_loss_pct display."""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.handlers.baskets import cmd_cesta


def _make_update():
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


def _make_context(args: list[str]):
    ctx = MagicMock()
    ctx.args = args
    return ctx


def _make_session(*execute_results):
    session = MagicMock()
    session.execute = AsyncMock(side_effect=list(execute_results))
    return session


def _exec_scalar(value=None):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _exec_scalars(values: list):
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    return r


def _exec_all(rows: list):
    r = MagicMock()
    r.all.return_value = rows
    return r


def _wrap(session):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# /cesta — shows stop_loss_pct when set
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cesta_shows_stop_loss_pct_when_set():
    """/cesta must include Stop-loss percentage in output when basket.stop_loss_pct is set."""
    basket = MagicMock(id=10, strategy="rsi", risk_profile="moderate",
                       cash=Decimal("10000"), stop_loss_pct=Decimal("8"))
    basket.name = "MiCesta"

    session = _make_session(
        _exec_scalar(basket),   # basket lookup
        _exec_scalars([]),       # basket_assets (BasketAsset — empty → personal basket)
        _exec_all([]),           # pos_pairs (Position — empty positions)
        _exec_all([]),           # members
    )

    update = _make_update()
    ctx = _make_context(["MiCesta"])

    with patch("src.bot.handlers.baskets.async_session_factory", return_value=_wrap(session)):
        await cmd_cesta(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    assert "8" in reply
    assert "stop" in reply.lower() or "Stop" in reply


@pytest.mark.asyncio
async def test_cesta_does_not_show_stop_loss_when_none():
    """/cesta must NOT show stop-loss line when basket.stop_loss_pct is None."""
    basket = MagicMock(id=10, strategy="rsi", risk_profile="moderate",
                       cash=Decimal("10000"), stop_loss_pct=None)
    basket.name = "MiCesta"

    session = _make_session(
        _exec_scalar(basket),
        _exec_scalars([]),       # basket_assets (empty → personal basket)
        _exec_all([]),           # pos_pairs (empty positions)
        _exec_all([]),           # members
    )

    update = _make_update()
    ctx = _make_context(["MiCesta"])

    with patch("src.bot.handlers.baskets.async_session_factory", return_value=_wrap(session)):
        await cmd_cesta(update, ctx)

    reply = update.message.reply_text.call_args[0][0]
    # No stop-loss line should appear when stop_loss_pct is None
    assert "stop" not in reply.lower()
