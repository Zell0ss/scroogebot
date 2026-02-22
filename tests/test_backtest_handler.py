"""Tests for /backtest handler: basket resolution, period parsing, display safety."""
import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.handlers.backtest import cmd_backtest


def _make_update(tg_id: int = 100):
    update = MagicMock()
    update.effective_user.id = tg_id
    msg = MagicMock()
    msg.edit_text = AsyncMock()
    msg.delete = AsyncMock()
    update.message.reply_text = AsyncMock(return_value=msg)
    return update, msg


def _make_context(args: list[str]):
    ctx = MagicMock()
    ctx.args = args
    return ctx


def _exec(value=None):
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


def _make_basket(name="CestaAgresiva", strategy="stop_loss", basket_id=1):
    b = MagicMock(id=basket_id, strategy=strategy, active=True)
    b.name = name
    return b


def _make_user(active_basket_id=1):
    u = MagicMock()
    u.active_basket_id = active_basket_id
    return u


def _make_asset(ticker="SAN.MC"):
    a = MagicMock()
    a.ticker = ticker
    return a


# ---------------------------------------------------------------------------
# Active basket resolution (no args)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_uses_active_basket_when_no_args():
    """With no args /backtest must use the user's active basket, not all baskets."""
    update, msg = _make_update()
    ctx = _make_context([])

    user = _make_user(active_basket_id=5)
    basket = _make_basket("CestaAgresiva", "stop_loss", basket_id=5)
    asset = _make_asset("SAN.MC")

    session = _make_session(
        _exec(user),                    # User lookup
        _exec(basket),                  # Basket by active_basket_id
        _exec_scalars([asset]),         # Assets
    )

    fake_result = MagicMock()
    fake_result.total_return_pct = 5.0
    fake_result.benchmark_return_pct = 3.0
    fake_result.sharpe_ratio = 1.2
    fake_result.max_drawdown_pct = 10.0
    fake_result.n_trades = 4
    fake_result.win_rate_pct = 75.0

    with (
        patch("src.bot.handlers.backtest.async_session_factory", return_value=_wrap(session)),
        patch("src.bot.handlers.backtest.BacktestEngine") as MockEngine,
    ):
        MockEngine.return_value.run.return_value = fake_result
        await cmd_backtest(update, ctx)

    # Must send exactly one reply with CestaAgresiva's name
    reply_calls = update.message.reply_text.call_args_list
    texts = [c[0][0] for c in reply_calls]
    combined = " ".join(texts)
    assert "CestaAgresiva" in combined, f"Basket name must appear. Got: {combined}"


@pytest.mark.asyncio
async def test_backtest_no_active_basket_no_args_shows_error():
    """When user has no active basket and gives no args, show a helpful error."""
    update, msg = _make_update()
    ctx = _make_context([])

    user = _make_user(active_basket_id=None)

    session = _make_session(
        _exec(user),    # User lookup
    )

    with patch("src.bot.handlers.backtest.async_session_factory", return_value=_wrap(session)):
        await cmd_backtest(update, ctx)

    text = update.message.reply_text.call_args[0][0]
    assert "/sel" in text or "cesta activa" in text.lower(), (
        f"Should mention /sel or 'cesta activa'. Got: {text}"
    )


@pytest.mark.asyncio
async def test_backtest_no_user_no_args_shows_error():
    """User not registered → show error."""
    update, msg = _make_update()
    ctx = _make_context([])

    session = _make_session(
        _exec(None),    # User not found
    )

    with patch("src.bot.handlers.backtest.async_session_factory", return_value=_wrap(session)):
        await cmd_backtest(update, ctx)

    text = update.message.reply_text.call_args[0][0]
    assert "/sel" in text or "cesta activa" in text.lower()


# ---------------------------------------------------------------------------
# Named basket argument
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_with_named_basket():
    """/backtest CestaAgresiva must look up that specific basket."""
    update, msg = _make_update()
    ctx = _make_context(["CestaAgresiva"])

    basket = _make_basket("CestaAgresiva", "stop_loss", basket_id=1)
    asset = _make_asset("SAN.MC")

    session = _make_session(
        _exec(basket),          # Basket by name
        _exec_scalars([asset]), # Assets
    )

    fake_result = MagicMock()
    fake_result.total_return_pct = 5.0
    fake_result.benchmark_return_pct = 3.0
    fake_result.sharpe_ratio = 1.2
    fake_result.max_drawdown_pct = 10.0
    fake_result.n_trades = 4
    fake_result.win_rate_pct = 75.0

    with (
        patch("src.bot.handlers.backtest.async_session_factory", return_value=_wrap(session)),
        patch("src.bot.handlers.backtest.BacktestEngine") as MockEngine,
    ):
        MockEngine.return_value.run.return_value = fake_result
        await cmd_backtest(update, ctx)

    texts = " ".join(c[0][0] for c in update.message.reply_text.call_args_list)
    assert "CestaAgresiva" in texts


@pytest.mark.asyncio
async def test_backtest_named_basket_not_found_shows_error():
    """/backtest DesconocidaCesta → clear 'not found' error."""
    update, msg = _make_update()
    ctx = _make_context(["DesconocidaCesta"])

    session = _make_session(
        _exec(None),    # Basket not found
    )

    with patch("src.bot.handlers.backtest.async_session_factory", return_value=_wrap(session)):
        await cmd_backtest(update, ctx)

    text = update.message.reply_text.call_args[0][0]
    assert "DesconocidaCesta" in text or "no encontrada" in text.lower()


# ---------------------------------------------------------------------------
# Period parsing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_period_uppercase_accepted():
    """/backtest 1Y (uppercase) must be treated same as 1y."""
    update, msg = _make_update()
    ctx = _make_context(["1Y"])

    user = _make_user(active_basket_id=5)
    basket = _make_basket("CestaAgresiva", "stop_loss", basket_id=5)
    asset = _make_asset("SAN.MC")

    session = _make_session(
        _exec(user),
        _exec(basket),
        _exec_scalars([asset]),
    )

    fake_result = MagicMock()
    fake_result.total_return_pct = 5.0
    fake_result.benchmark_return_pct = 3.0
    fake_result.sharpe_ratio = 1.2
    fake_result.max_drawdown_pct = 10.0
    fake_result.n_trades = 4
    fake_result.win_rate_pct = 75.0

    with (
        patch("src.bot.handlers.backtest.async_session_factory", return_value=_wrap(session)),
        patch("src.bot.handlers.backtest.BacktestEngine") as MockEngine,
    ):
        MockEngine.return_value.run.return_value = fake_result
        await cmd_backtest(update, ctx)

    # Should succeed (period normalized) — not show an error
    # Check engine.run was called with period="1y"
    run_call = MockEngine.return_value.run.call_args
    period_arg = run_call[0][3] if run_call[0] else run_call[1].get("period", "")
    assert period_arg == "1y", f"Period must be normalized to lowercase. Got: {period_arg}"


@pytest.mark.asyncio
async def test_backtest_named_basket_with_period():
    """/backtest CestaConservadora 6mo — both name and period parsed correctly."""
    update, msg = _make_update()
    ctx = _make_context(["CestaConservadora", "6mo"])

    basket = _make_basket("CestaConservadora", "ma_crossover", basket_id=2)
    asset = _make_asset("BRK-B")

    session = _make_session(
        _exec(basket),
        _exec_scalars([asset]),
    )

    fake_result = MagicMock()
    fake_result.total_return_pct = 2.0
    fake_result.benchmark_return_pct = 3.0
    fake_result.sharpe_ratio = 0.8
    fake_result.max_drawdown_pct = 5.0
    fake_result.n_trades = 2
    fake_result.win_rate_pct = 50.0

    with (
        patch("src.bot.handlers.backtest.async_session_factory", return_value=_wrap(session)),
        patch("src.bot.handlers.backtest.BacktestEngine") as MockEngine,
    ):
        MockEngine.return_value.run.return_value = fake_result
        await cmd_backtest(update, ctx)

    run_call = MockEngine.return_value.run.call_args
    period_arg = run_call[0][3] if run_call[0] else run_call[1].get("period", "")
    assert period_arg == "6mo"


# ---------------------------------------------------------------------------
# Personal basket: fallback to active positions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_personal_basket_falls_back_to_positions():
    """When BasketAsset is empty, /backtest must run on active Position tickers."""
    update, msg = _make_update()
    ctx = _make_context(["Mi_Ahorro_jmc"])

    basket = _make_basket("Mi_Ahorro_jmc", "stop_loss", basket_id=10)
    asset = _make_asset("SAN.MC")

    session = _make_session(
        _exec(basket),              # basket by name
        _exec_scalars([]),          # BasketAsset empty
        _exec_scalars([asset]),     # Position fallback → SAN.MC
    )

    fake_result = MagicMock()
    fake_result.total_return_pct = 3.0
    fake_result.benchmark_return_pct = 2.0
    fake_result.sharpe_ratio = 0.9
    fake_result.max_drawdown_pct = 8.0
    fake_result.n_trades = 3
    fake_result.win_rate_pct = 66.0

    with (
        patch("src.bot.handlers.backtest.async_session_factory", return_value=_wrap(session)),
        patch("src.bot.handlers.backtest.BacktestEngine") as MockEngine,
    ):
        MockEngine.return_value.run.return_value = fake_result
        await cmd_backtest(update, ctx)

    # Engine must have been called — position fallback worked
    assert MockEngine.return_value.run.called, "BacktestEngine.run must be called when positions exist"
    texts = " ".join(c[0][0] for c in update.message.reply_text.call_args_list)
    assert "SAN.MC" in texts or "Mi_Ahorro_jmc" in texts


@pytest.mark.asyncio
async def test_backtest_personal_basket_no_positions_shows_error():
    """Personal basket with no BasketAsset AND no active positions → clear error."""
    update, msg = _make_update()
    ctx = _make_context(["Mi_Ahorro_jmc"])

    basket = _make_basket("Mi_Ahorro_jmc", "stop_loss", basket_id=10)

    session = _make_session(
        _exec(basket),
        _exec_scalars([]),      # BasketAsset empty
        _exec_scalars([]),      # Position fallback also empty
    )

    with patch("src.bot.handlers.backtest.async_session_factory", return_value=_wrap(session)):
        await cmd_backtest(update, ctx)

    text = update.message.reply_text.call_args[0][0]
    assert "activos" in text.lower() or "/compra" in text, (
        f"Should mention 'activos' or '/compra'. Got: {text}"
    )


# ---------------------------------------------------------------------------
# Display safety: NaN / inf must not appear raw in output
# ---------------------------------------------------------------------------

def _make_fake_result_zero_trades():
    r = MagicMock()
    r.total_return_pct = 0.0
    r.benchmark_return_pct = 55.0
    r.sharpe_ratio = float("inf")
    r.max_drawdown_pct = float("nan")
    r.n_trades = 0
    r.win_rate_pct = float("nan")
    return r


@pytest.mark.asyncio
async def test_backtest_inf_sharpe_not_shown_raw():
    """'inf' must not appear literally in output when Sharpe is infinite."""
    update, msg = _make_update()
    ctx = _make_context(["CestaAgresiva"])

    basket = _make_basket("CestaAgresiva", "stop_loss", basket_id=1)
    asset = _make_asset("SAN.MC")

    session = _make_session(
        _exec(basket),
        _exec_scalars([asset]),
    )

    with (
        patch("src.bot.handlers.backtest.async_session_factory", return_value=_wrap(session)),
        patch("src.bot.handlers.backtest.BacktestEngine") as MockEngine,
    ):
        MockEngine.return_value.run.return_value = _make_fake_result_zero_trades()
        await cmd_backtest(update, ctx)

    text = msg.edit_text.call_args[0][0]
    assert "inf" not in text.lower(), f"'inf' must not appear raw. Got:\n{text}"


@pytest.mark.asyncio
async def test_backtest_nan_metrics_not_shown_raw():
    """'nan' must not appear literally in output when metrics are NaN."""
    update, msg = _make_update()
    ctx = _make_context(["CestaAgresiva"])

    basket = _make_basket("CestaAgresiva", "stop_loss", basket_id=1)
    asset = _make_asset("SAN.MC")

    session = _make_session(
        _exec(basket),
        _exec_scalars([asset]),
    )

    with (
        patch("src.bot.handlers.backtest.async_session_factory", return_value=_wrap(session)),
        patch("src.bot.handlers.backtest.BacktestEngine") as MockEngine,
    ):
        MockEngine.return_value.run.return_value = _make_fake_result_zero_trades()
        await cmd_backtest(update, ctx)

    text = msg.edit_text.call_args[0][0]
    assert "nan" not in text.lower(), f"'nan' must not appear raw. Got:\n{text}"


# ---------------------------------------------------------------------------
# Max drawdown display sign
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_max_dd_shown_as_negative():
    """Max drawdown must be displayed as a negative value (it represents a loss)."""
    update, msg = _make_update()
    ctx = _make_context(["CestaAgresiva"])

    basket = _make_basket("CestaAgresiva", "stop_loss", basket_id=1)
    asset = _make_asset("SAN.MC")

    session = _make_session(
        _exec(basket),
        _exec_scalars([asset]),
    )

    fake_result = MagicMock()
    fake_result.total_return_pct = 5.0
    fake_result.benchmark_return_pct = 3.0
    fake_result.sharpe_ratio = 1.2
    fake_result.max_drawdown_pct = 7.5   # vectorbt returns positive magnitude
    fake_result.n_trades = 4
    fake_result.win_rate_pct = 75.0

    with (
        patch("src.bot.handlers.backtest.async_session_factory", return_value=_wrap(session)),
        patch("src.bot.handlers.backtest.BacktestEngine") as MockEngine,
    ):
        MockEngine.return_value.run.return_value = fake_result
        await cmd_backtest(update, ctx)

    text = msg.edit_text.call_args[0][0]
    assert "-7.5%" in text, f"Max DD must be shown as negative. Got:\n{text}"
    assert "+7.5%" not in text, f"Max DD must NOT appear as positive. Got:\n{text}"


# ---------------------------------------------------------------------------
# Strategy name visible in output
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_shows_strategy_name_in_output():
    """Strategy name must appear in the /backtest result text."""
    update, msg = _make_update()
    ctx = _make_context(["CestaAgresiva"])

    basket = _make_basket("CestaAgresiva", "stop_loss", basket_id=1)
    asset = _make_asset("SAN.MC")

    session = _make_session(
        _exec(basket),
        _exec_scalars([asset]),
    )

    fake_result = MagicMock()
    fake_result.total_return_pct = 5.0
    fake_result.benchmark_return_pct = 3.0
    fake_result.sharpe_ratio = 1.2
    fake_result.max_drawdown_pct = 10.0
    fake_result.n_trades = 4
    fake_result.win_rate_pct = 75.0

    with (
        patch("src.bot.handlers.backtest.async_session_factory", return_value=_wrap(session)),
        patch("src.bot.handlers.backtest.BacktestEngine") as MockEngine,
    ):
        MockEngine.return_value.run.return_value = fake_result
        await cmd_backtest(update, ctx)

    text = msg.edit_text.call_args[0][0]
    assert "stop_loss" in text, f"Strategy name must appear in output. Got:\n{text}"
