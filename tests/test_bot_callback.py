"""Tests for handle_alert_callback in bot.py."""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.bot import handle_alert_callback


def _make_query(data="alert:confirm:1", from_user_id=999):
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.from_user = MagicMock()
    query.from_user.id = from_user_id
    return query


def _make_update(query):
    update = MagicMock()
    update.callback_query = query
    return update


def _make_alert(alert_id=1, status="PENDING", signal="SELL", asset_id=10, basket_id=5):
    alert = MagicMock()
    alert.id = alert_id
    alert.status = status
    alert.signal = signal
    alert.asset_id = asset_id
    alert.basket_id = basket_id
    return alert


def _make_asset(market="NYSE"):
    asset = MagicMock()
    asset.ticker = "AAPL"
    asset.market = market
    return asset


def _make_session_for_callback(alert, asset, basket, user, is_member=True):
    """Build a session mock for the confirm callback flow."""
    # session.get is called 3 times: Alert, Asset, Basket
    session = MagicMock()
    session.get = AsyncMock(side_effect=[alert, asset, basket])

    # session.execute is called twice: User lookup, BasketMember check
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user

    member_result = MagicMock()
    member_result.scalar_one_or_none.return_value = MagicMock() if is_member else None

    session.execute = AsyncMock(side_effect=[user_result, member_result])
    session.commit = AsyncMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, session


@pytest.mark.asyncio
async def test_confirm_blocked_when_market_closed():
    """If asset.market is closed, confirm returns error message and alert stays PENDING."""
    query = _make_query("alert:confirm:1")
    update = _make_update(query)
    context = MagicMock()

    alert = _make_alert()
    asset = _make_asset(market="NYSE")
    basket = MagicMock()
    basket.id = 5
    user = MagicMock()
    user.id = 1

    session_cm, session = _make_session_for_callback(alert, asset, basket, user)

    with (
        patch("src.bot.bot.async_session_factory", return_value=session_cm),
        patch("src.bot.bot.is_market_open", return_value=False),
    ):
        await handle_alert_callback(update, context)

    # Must tell user market is closed
    query.edit_message_text.assert_called_once()
    msg = query.edit_message_text.call_args[0][0]
    assert "cerrado" in msg.lower() or "closed" in msg.lower()

    # Alert must NOT be committed (stays PENDING)
    session.commit.assert_not_called()
    assert alert.status == "PENDING"
