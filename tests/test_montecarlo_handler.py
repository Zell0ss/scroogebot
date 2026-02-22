"""Tests for /montecarlo handler: position fallback for personal baskets."""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.handlers.montecarlo import cmd_montecarlo


def _make_update():
    update = MagicMock()
    update.effective_user.id = 100
    msg = MagicMock()
    msg.delete = AsyncMock()
    update.message.reply_text = AsyncMock(return_value=msg)
    return update, msg


def _make_context(args: list[str]):
    ctx = MagicMock()
    ctx.args = args
    return ctx


def _exec_scalar(value=None):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _exec_scalars(values: list):
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    return r


def _make_session(*execute_results):
    session = MagicMock()
    session.execute = AsyncMock(side_effect=list(execute_results))
    return session


def _wrap(session):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_basket(name="Mi_Apuesta", strategy="rsi", basket_id=1):
    b = MagicMock(id=basket_id, strategy=strategy, active=True)
    b.name = name
    b.stop_loss_pct = None
    return b


def _make_asset(ticker="NVDA"):
    a = MagicMock()
    a.ticker = ticker
    return a


# ---------------------------------------------------------------------------
# Position fallback: basket with no BasketAsset rows but open positions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_montecarlo_falls_back_to_positions_when_no_basket_assets():
    """/montecarlo must use open positions when BasketAsset list is empty (personal basket)."""
    update, msg = _make_update()
    ctx = _make_context(["Mi_Apuesta"])

    basket = _make_basket("Mi_Apuesta", "rsi", basket_id=12)
    asset = _make_asset("NVDA")

    session = _make_session(
        _exec_scalar(basket),       # basket lookup
        _exec_scalars([]),          # BasketAssets → empty
        _exec_scalars([asset]),     # positions fallback
    )

    fake_ohlcv = MagicMock()
    fake_ohlcv.data = MagicMock()

    fake_mc_result = MagicMock()
    fake_mc_result.ticker = "NVDA"
    fake_mc_result.return_median = 5.0
    fake_mc_result.return_p10 = -2.0
    fake_mc_result.return_p90 = 12.0
    fake_mc_result.return_p05 = -5.0
    fake_mc_result.prob_loss = 0.3
    fake_mc_result.var_95 = -8.0
    fake_mc_result.cvar_95 = -12.0
    fake_mc_result.max_dd_median = -10.0
    fake_mc_result.max_dd_p95 = -20.0
    fake_mc_result.sharpe_median = 1.2
    fake_mc_result.win_rate_median = 60.0

    with (
        patch("src.bot.handlers.montecarlo.async_session_factory", return_value=_wrap(session)),
        patch("src.bot.handlers.montecarlo.YahooDataProvider") as MockProvider,
        patch("src.bot.handlers.montecarlo.MonteCarloAnalyzer") as MockAnalyzer,
        patch("src.backtest.montecarlo._profile_line", return_value="🟡 Moderado"),
    ):
        MockProvider.return_value.get_historical.return_value = fake_ohlcv
        MockAnalyzer.return_value.run_asset.return_value = fake_mc_result

        await cmd_montecarlo(update, ctx)

    # Must NOT have sent the "sin activos activos" error
    calls = [c[0][0] for c in update.message.reply_text.call_args_list]
    assert not any("sin activos" in c for c in calls), (
        f"Should not show 'sin activos' when positions exist. Replies: {calls}"
    )
    # Must have sent something with NVDA
    combined = " ".join(calls)
    assert "NVDA" in combined, f"Expected NVDA in output. Got: {combined}"


@pytest.mark.asyncio
async def test_montecarlo_shows_error_when_no_assets_and_no_positions():
    """/montecarlo shows error when basket has neither BasketAssets nor open positions."""
    update, msg = _make_update()
    ctx = _make_context(["Mi_Apuesta"])

    basket = _make_basket("Mi_Apuesta", "rsi", basket_id=12)

    session = _make_session(
        _exec_scalar(basket),    # basket lookup
        _exec_scalars([]),       # BasketAssets → empty
        _exec_scalars([]),       # positions → also empty
    )

    with patch("src.bot.handlers.montecarlo.async_session_factory", return_value=_wrap(session)):
        await cmd_montecarlo(update, ctx)

    calls = [c[0][0] for c in update.message.reply_text.call_args_list]
    assert any("sin activos" in c for c in calls), (
        f"Should show 'sin activos' when no positions either. Got: {calls}"
    )
