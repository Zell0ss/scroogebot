"""Tests for AlertEngine stop-loss layer (position-based, independent of strategy)."""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.alerts.engine import AlertEngine
from src.strategies.base import Signal


def _make_basket(stop_loss_pct=None, strategy="rsi", basket_id=1, name="TestCesta"):
    b = MagicMock()
    b.id = basket_id
    b.name = name
    b.strategy = strategy
    b.stop_loss_pct = Decimal(str(stop_loss_pct)) if stop_loss_pct is not None else None
    b.active = True
    return b


def _make_position(avg_price: float, ticker="SAN.MC", asset_id=1):
    pos = MagicMock()
    pos.avg_price = Decimal(str(avg_price))
    pos.basket_id = 1
    pos.quantity = Decimal("10")
    asset = MagicMock()
    asset.id = asset_id
    asset.ticker = ticker
    asset.market = None   # skip market-hours check
    return pos, asset


def _make_session(position_pairs, has_pending_alert=False):
    """Build a session mock. First execute = positions, second = dedup check."""
    pos_result = MagicMock()
    pos_result.all.return_value = position_pairs

    dedup_result = MagicMock()
    dedup_result.scalar_one_or_none.return_value = MagicMock() if has_pending_alert else None

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[pos_result, dedup_result])
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _mock_strategy(return_value=None):
    """Return a STRATEGY_MAP-compatible dict with a strategy that returns given signal."""
    mock_instance = MagicMock()
    mock_instance.evaluate.return_value = return_value
    mock_cls = MagicMock(return_value=mock_instance)
    return mock_cls


# ---------------------------------------------------------------------------
# Stop-loss triggers when position is down >= threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stoploss_generates_sell_when_price_drops_below_threshold():
    """If position is down ≥ stop_loss_pct from avg_price, a SELL alert is created."""
    basket = _make_basket(stop_loss_pct=8.0, strategy="rsi")
    pos, asset = _make_position(avg_price=100.0)
    current_price = Decimal("91.0")   # down 9% — below 8% threshold

    session_cm = _make_session([(pos, asset)])

    price_mock = MagicMock()
    price_mock.price = current_price

    engine = AlertEngine(telegram_app=None)
    mock_cls = _mock_strategy(return_value=None)   # strategy returns no signal

    with (
        patch("src.alerts.engine.async_session_factory", return_value=session_cm),
        patch.object(engine.data, "get_current_price", return_value=price_mock),
        patch.object(engine.data, "get_historical", return_value=MagicMock(data=MagicMock())),
        patch("src.alerts.engine.is_market_open", return_value=True),
        patch.dict("src.alerts.engine.STRATEGY_MAP", {"rsi": mock_cls}),
    ):
        await engine._scan_basket(basket)

    session_cm.__aenter__.return_value.add.assert_called_once()
    alert_arg = session_cm.__aenter__.return_value.add.call_args[0][0]
    assert alert_arg.signal == "SELL"
    assert "Stop-loss" in alert_arg.reason
    assert "8" in alert_arg.reason


@pytest.mark.asyncio
async def test_stoploss_no_alert_when_price_above_threshold():
    """If position is down less than stop_loss_pct, no stop-loss alert."""
    basket = _make_basket(stop_loss_pct=8.0, strategy="rsi")
    pos, asset = _make_position(avg_price=100.0)
    current_price = Decimal("95.0")   # down only 5% — above 8% threshold

    session_cm = _make_session([(pos, asset)])

    price_mock = MagicMock()
    price_mock.price = current_price

    engine = AlertEngine(telegram_app=None)
    mock_cls = _mock_strategy(return_value=None)

    with (
        patch("src.alerts.engine.async_session_factory", return_value=session_cm),
        patch.object(engine.data, "get_current_price", return_value=price_mock),
        patch.object(engine.data, "get_historical", return_value=MagicMock(data=MagicMock())),
        patch("src.alerts.engine.is_market_open", return_value=True),
        patch.dict("src.alerts.engine.STRATEGY_MAP", {"rsi": mock_cls}),
    ):
        await engine._scan_basket(basket)

    session_cm.__aenter__.return_value.add.assert_not_called()


@pytest.mark.asyncio
async def test_stoploss_ignored_when_pct_is_none():
    """When basket.stop_loss_pct is None, no stop-loss check runs."""
    basket = _make_basket(stop_loss_pct=None, strategy="rsi")
    pos, asset = _make_position(avg_price=100.0)
    current_price = Decimal("50.0")   # down 50% — would trigger if configured

    session_cm = _make_session([(pos, asset)])

    price_mock = MagicMock()
    price_mock.price = current_price

    engine = AlertEngine(telegram_app=None)
    mock_cls = _mock_strategy(return_value=None)

    with (
        patch("src.alerts.engine.async_session_factory", return_value=session_cm),
        patch.object(engine.data, "get_current_price", return_value=price_mock),
        patch.object(engine.data, "get_historical", return_value=MagicMock(data=MagicMock())),
        patch("src.alerts.engine.is_market_open", return_value=True),
        patch.dict("src.alerts.engine.STRATEGY_MAP", {"rsi": mock_cls}),
    ):
        await engine._scan_basket(basket)

    session_cm.__aenter__.return_value.add.assert_not_called()


@pytest.mark.asyncio
async def test_stoploss_overrides_strategy_buy_signal():
    """Stop-loss overrides a BUY signal from the strategy when price drops >= threshold."""
    basket = _make_basket(stop_loss_pct=8.0, strategy="rsi")
    pos, asset = _make_position(avg_price=100.0)
    current_price = Decimal("88.0")   # down 12% — triggers stop_loss

    session_cm = _make_session([(pos, asset)])

    price_mock = MagicMock()
    price_mock.price = current_price

    buy_signal = Signal(action="BUY", ticker="SAN.MC", price=current_price,
                        reason="RSI oversold", confidence=0.8)

    engine = AlertEngine(telegram_app=None)
    mock_cls = _mock_strategy(return_value=buy_signal)   # strategy says BUY

    with (
        patch("src.alerts.engine.async_session_factory", return_value=session_cm),
        patch.object(engine.data, "get_current_price", return_value=price_mock),
        patch.object(engine.data, "get_historical", return_value=MagicMock(data=MagicMock())),
        patch("src.alerts.engine.is_market_open", return_value=True),
        patch.dict("src.alerts.engine.STRATEGY_MAP", {"rsi": mock_cls}),
    ):
        await engine._scan_basket(basket)

    # Alert must be SELL (stop-loss overrides the BUY)
    session_cm.__aenter__.return_value.add.assert_called_once()
    alert_arg = session_cm.__aenter__.return_value.add.call_args[0][0]
    assert alert_arg.signal == "SELL"
    assert "Stop-loss" in alert_arg.reason


@pytest.mark.asyncio
async def test_scan_passes_avg_price_to_strategy():
    """AlertEngine passes pos.avg_price as the 4th arg to strategy.evaluate()."""
    basket = _make_basket(stop_loss_pct=None, strategy="rsi")
    pos, asset = _make_position(avg_price=150.0)
    current_price = Decimal("160.0")

    session_cm = _make_session([(pos, asset)])
    price_mock = MagicMock()
    price_mock.price = current_price
    hist_mock = MagicMock(data=MagicMock())

    engine = AlertEngine(telegram_app=None)
    mock_cls = _mock_strategy(return_value=None)

    with (
        patch("src.alerts.engine.async_session_factory", return_value=session_cm),
        patch.object(engine.data, "get_current_price", return_value=price_mock),
        patch.object(engine.data, "get_historical", return_value=hist_mock),
        patch("src.alerts.engine.is_market_open", return_value=True),
        patch.dict("src.alerts.engine.STRATEGY_MAP", {"rsi": mock_cls}),
    ):
        await engine._scan_basket(basket)

    instance = mock_cls.return_value
    call_args = instance.evaluate.call_args
    # 4th positional arg (index 3) or keyword 'avg_price' must be pos.avg_price
    passed_avg_price = (
        call_args.kwargs.get("avg_price")
        or (call_args.args[3] if len(call_args.args) > 3 else None)
    )
    assert passed_avg_price == pos.avg_price
