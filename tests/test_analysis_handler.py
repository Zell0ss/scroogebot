import pytest
import pandas as pd
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.handlers.analysis import cmd_analiza


def _make_update():
    update = MagicMock()
    msg = MagicMock()
    msg.edit_text = AsyncMock()
    update.message.reply_text = AsyncMock(return_value=msg)
    return update, msg


def _make_ohlcv(n=30, close=100.0, high=102.0, low=98.0):
    """Synthetic OHLCV. H-L spread of 4 → ATR ~4 → ATR% ~4% (alta)."""
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "Open":   [close] * n,
        "High":   [high]  * n,
        "Low":    [low]   * n,
        "Close":  [close] * n,
        "Volume": [1000]  * n,
    }, index=idx)


def _make_price(value=100.0, currency="EUR"):
    p = MagicMock()
    p.price = Decimal(str(value))
    p.currency = currency
    return p


def _make_ohlcv_result(n=30, close=100.0, high=102.0, low=98.0):
    r = MagicMock()
    r.data = _make_ohlcv(n, close, high, low)
    return r


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analiza_includes_atr_line():
    """Response must contain an ATR (volatilidad) line."""
    update, msg = _make_update()
    ctx = MagicMock()
    ctx.args = ["IBE.MC"]

    with patch("src.bot.handlers.analysis._provider") as prov:
        prov.get_current_price.return_value = _make_price(100.0, "EUR")
        prov.get_historical.return_value = _make_ohlcv_result()
        await cmd_analiza(update, ctx)

    text = msg.edit_text.call_args[0][0]
    assert "ATR" in text


@pytest.mark.asyncio
async def test_analiza_high_volatility_label():
    """H-L spread of 4 on price 100 → ATR% ~4% → label 'alta'."""
    update, msg = _make_update()
    ctx = MagicMock()
    ctx.args = ["NVDA"]

    with patch("src.bot.handlers.analysis._provider") as prov:
        prov.get_current_price.return_value = _make_price(100.0, "USD")
        prov.get_historical.return_value = _make_ohlcv_result(high=102.0, low=98.0)
        await cmd_analiza(update, ctx)

    text = msg.edit_text.call_args[0][0]
    assert "alta" in text.lower()


@pytest.mark.asyncio
async def test_analiza_low_volatility_label():
    """H-L spread of 0.5 on price 100 → ATR% ~0.5% → label 'baja'."""
    update, msg = _make_update()
    ctx = MagicMock()
    ctx.args = ["IBE.MC"]

    with patch("src.bot.handlers.analysis._provider") as prov:
        prov.get_current_price.return_value = _make_price(100.0, "EUR")
        prov.get_historical.return_value = _make_ohlcv_result(high=100.25, low=99.75)
        await cmd_analiza(update, ctx)

    text = msg.edit_text.call_args[0][0]
    assert "baja" in text.lower()
