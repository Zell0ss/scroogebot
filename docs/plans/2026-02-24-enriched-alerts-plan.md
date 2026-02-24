# Enriched Alerts + Sonnet Explanation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enrich Telegram alert notifications with position data, technical indicators, and optional Haiku-generated explanations for learning users.

**Architecture:** A new `MarketContext` dataclass is computed in `_scan_basket` from already-fetched `historical.data` (zero extra API calls). It flows through `new_alerts` to `_notify()`, which builds an enriched message and optionally calls `AsyncAnthropic` for non-advanced users. A new `/modo` command toggles `User.advanced_mode` (DB field).

**Tech Stack:** Python 3.11, `ta==0.11.0`, `anthropic>=0.40` (new), SQLAlchemy 2.0, Alembic, python-telegram-bot v20+

---

## Task 1: Install anthropic SDK

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add dependency to pyproject.toml**

In `pyproject.toml`, add `"anthropic>=0.40",` to the `dependencies` list, after `prometheus-client`.

**Step 2: Install in venv**

```bash
.venv/bin/pip install "anthropic>=0.40"
```

Expected: `Successfully installed anthropic-...`

**Step 3: Verify**

```bash
.venv/bin/python -c "import anthropic; print(anthropic.__version__)"
```

Expected: prints version like `0.4x.x`

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add anthropic SDK dependency"
```

---

## Task 2: MarketContext dataclass + compute_market_context()

**Files:**
- Create: `src/alerts/market_context.py`
- Create: `tests/test_market_context.py`

**Step 1: Write the failing tests**

Create `tests/test_market_context.py`:

```python
import pytest
import pandas as pd
from decimal import Decimal
from unittest.mock import MagicMock

from src.alerts.market_context import compute_market_context, MarketContext


def _make_ohlcv(prices: list[float]) -> pd.DataFrame:
    """Synthetic OHLCV DataFrame: High=price*1.01, Low=price*0.99."""
    return pd.DataFrame({
        "Open":   prices,
        "High":   [p * 1.01 for p in prices],
        "Low":    [p * 0.99 for p in prices],
        "Close":  prices,
        "Volume": [1000] * len(prices),
    })


def _make_pos(qty: float, avg: float):
    pos = MagicMock()
    pos.quantity = Decimal(str(qty))
    pos.avg_price = Decimal(str(avg))
    return pos


# --- Trend detection ---

def test_trend_alcista():
    # Monotonically increasing: price > SMA20 > SMA50
    prices = list(range(1, 61))  # [1, 2, ..., 60], 60 bars
    data = _make_ohlcv(prices)
    ctx = compute_market_context("AAPL", data, Decimal("60"), None, Decimal("10000"), "SELL")
    assert ctx.trend == "alcista"


def test_trend_bajista():
    # Monotonically decreasing: price < SMA20 < SMA50
    prices = list(range(60, 0, -1))  # [60, 59, ..., 1], 60 bars
    data = _make_ohlcv(prices)
    ctx = compute_market_context("AAPL", data, Decimal("1"), None, Decimal("10000"), "SELL")
    assert ctx.trend == "bajista"


def test_trend_lateral():
    # Flat prices: SMA20 == SMA50 == price → lateral
    prices = [10.0] * 60
    data = _make_ohlcv(prices)
    ctx = compute_market_context("AAPL", data, Decimal("10"), None, Decimal("10000"), "BUY")
    assert ctx.trend == "lateral"


# --- P&L ---

def test_pnl_positive():
    data = _make_ohlcv([10.0] * 60)
    pos = _make_pos(qty=20, avg=4.0)
    ctx = compute_market_context("SAN.MC", data, Decimal("4.40"), pos, Decimal("8000"), "SELL")
    assert ctx.pnl_pct == pytest.approx(10.0, rel=1e-3)


def test_pnl_negative():
    data = _make_ohlcv([10.0] * 60)
    pos = _make_pos(qty=20, avg=5.0)
    ctx = compute_market_context("SAN.MC", data, Decimal("4.00"), pos, Decimal("8000"), "SELL")
    assert ctx.pnl_pct == pytest.approx(-20.0, rel=1e-3)


def test_pnl_none_when_no_position():
    data = _make_ohlcv([10.0] * 60)
    ctx = compute_market_context("AAPL", data, Decimal("10"), None, Decimal("10000"), "BUY")
    assert ctx.pnl_pct is None


# --- suggested_qty ---

def test_suggested_qty_buy_is_10pct_of_cash():
    data = _make_ohlcv([10.0] * 60)
    # cash=1000, price=10 → 10% = 100€ / 10 = 10 shares
    ctx = compute_market_context("AAPL", data, Decimal("10"), None, Decimal("1000"), "BUY")
    assert ctx.suggested_qty == Decimal("10.00")


def test_suggested_qty_sell_is_full_position():
    data = _make_ohlcv([10.0] * 60)
    pos = _make_pos(qty=25, avg=9.0)
    ctx = compute_market_context("AAPL", data, Decimal("10"), pos, Decimal("1000"), "SELL")
    assert ctx.suggested_qty == Decimal("25")


# --- ATR% ---

def test_atr_pct_is_none_for_insufficient_data():
    data = _make_ohlcv([10.0] * 5)  # only 5 bars, ATR needs 14
    ctx = compute_market_context("AAPL", data, Decimal("10"), None, Decimal("1000"), "BUY")
    assert ctx.atr_pct is None


def test_atr_pct_is_positive_for_volatile_data():
    prices = [10 + (i % 3) for i in range(60)]  # oscillating
    data = _make_ohlcv(prices)
    ctx = compute_market_context("AAPL", data, Decimal("10"), None, Decimal("1000"), "BUY")
    assert ctx.atr_pct is not None
    assert ctx.atr_pct > 0
```

**Step 2: Run tests to confirm they fail**

```bash
.venv/bin/pytest tests/test_market_context.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.alerts.market_context'`

**Step 3: Create `src/alerts/market_context.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd
import ta.momentum
import ta.volatility


@dataclass
class MarketContext:
    ticker: str
    price: Decimal
    # Technical indicators (computed from historical.data — no extra API calls)
    sma20: float | None
    sma50: float | None
    rsi14: float | None
    atr_pct: float | None   # ATR14 / price * 100
    trend: str              # "alcista" | "bajista" | "lateral"
    # Current position
    position_qty: Decimal
    avg_price: Decimal | None
    pnl_pct: float | None
    # Signal metadata
    confidence: float
    # Suggested trade size
    suggested_qty: Decimal  # BUY: 10% of cash; SELL: full position


def compute_market_context(
    ticker: str,
    data: pd.DataFrame,
    price: Decimal,
    pos,               # Position ORM object or None
    basket_cash: Decimal,
    signal_action: str,
    confidence: float = 1.0,
) -> MarketContext:
    """Compute market context from already-fetched OHLCV DataFrame.

    All indicator calculations use the `ta` library on `data` — zero extra
    network calls. Falls back gracefully (None) for insufficient history.
    """
    close = data["Close"]
    price_f = float(price)

    # SMA20 / SMA50
    sma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None

    # RSI14
    try:
        rsi_series = ta.momentum.RSIIndicator(close=close, window=14).rsi().dropna()
        rsi14 = float(rsi_series.iloc[-1]) if not rsi_series.empty else None
    except Exception:
        rsi14 = None

    # ATR14 as percentage of price
    try:
        atr_series = ta.volatility.AverageTrueRange(
            high=data["High"], low=data["Low"], close=close, window=14
        ).average_true_range().dropna()
        atr_pct = float(atr_series.iloc[-1]) / price_f * 100 if not atr_series.empty and price_f > 0 else None
    except Exception:
        atr_pct = None

    # Trend: strict price > SMA20 > SMA50 (or inverse)
    if sma20 is not None and sma50 is not None:
        if price_f > sma20 > sma50:
            trend = "alcista"
        elif price_f < sma20 < sma50:
            trend = "bajista"
        else:
            trend = "lateral"
    else:
        trend = "lateral"

    # Position data
    position_qty = pos.quantity if pos else Decimal("0")
    avg_p = pos.avg_price if pos else None
    if avg_p and avg_p > 0:
        pnl_pct = float((price - avg_p) / avg_p * 100)
    else:
        pnl_pct = None

    # Suggested trade size
    if signal_action == "BUY":
        suggested_qty = (basket_cash * Decimal("0.10") / price).quantize(Decimal("0.01"))
    else:
        suggested_qty = position_qty

    return MarketContext(
        ticker=ticker,
        price=price,
        sma20=sma20,
        sma50=sma50,
        rsi14=rsi14,
        atr_pct=atr_pct,
        trend=trend,
        position_qty=position_qty,
        avg_price=avg_p,
        pnl_pct=pnl_pct,
        confidence=float(confidence),
        suggested_qty=suggested_qty,
    )
```

**Step 4: Run tests to confirm they pass**

```bash
.venv/bin/pytest tests/test_market_context.py -v
```

Expected: all 10 tests PASS.

**Step 5: Run full suite**

```bash
.venv/bin/pytest tests/ -q
```

Expected: all existing tests still pass.

**Step 6: Commit**

```bash
git add src/alerts/market_context.py tests/test_market_context.py
git commit -m "feat(alerts): MarketContext dataclass with indicator computation"
```

---

## Task 3: User.advanced_mode DB field + migration

**Files:**
- Modify: `src/db/models.py` (line 21, after `active_basket_id`)
- Run: Alembic migration

**Step 1: Add field to User model**

In `src/db/models.py`, in the `User` class, add after the `active_basket_id` line:

```python
advanced_mode: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
```

The class should look like:
```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(100))
    first_name: Mapped[str | None] = mapped_column(String(100))
    active_basket_id: Mapped[int | None] = mapped_column(ForeignKey("baskets.id"), nullable=True)
    advanced_mode: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    memberships: Mapped[list[BasketMember]] = relationship(back_populates="user")
```

**Step 2: Generate Alembic migration**

```bash
.venv/bin/alembic revision --autogenerate -m "add_user_advanced_mode"
```

Expected: creates a new file in `src/db/migrations/versions/`.

**Step 3: Apply migration**

```bash
.venv/bin/alembic upgrade head
```

Expected: `Running upgrade ... -> <hash>, add_user_advanced_mode`

**Step 4: Run full suite**

```bash
.venv/bin/pytest tests/ -q
```

Expected: all tests pass.

**Step 5: Commit**

```bash
git add src/db/models.py src/db/migrations/
git commit -m "feat(db): add User.advanced_mode field (default=False)"
```

---

## Task 4: Translate strategy reason strings to Spanish

**Files:**
- Modify: `src/strategies/rsi.py`
- Modify: `src/strategies/ma_crossover.py`
- Modify: `src/strategies/bollinger.py`
- Modify: `src/strategies/stop_loss.py`
- Modify: `src/strategies/safe_haven.py`
- Modify: `src/alerts/engine.py` (stop-loss layer, line ~97)

**Step 1: rsi.py** — two strings to change:

```python
# Line 36: oversold BUY
reason=f"RSI saliendo de zona de sobreventa ({last_rsi:.1f})",

# Line 44: overbought SELL
reason=f"RSI saliendo de zona de sobrecompra ({last_rsi:.1f})",
```

**Step 2: ma_crossover.py** — two strings:

```python
# BUY
reason=f"MA{self.fast} cruzó al alza MA{self.slow}",

# SELL
reason=f"MA{self.fast} cruzó a la baja MA{self.slow}",
```

**Step 3: bollinger.py** — two strings:

```python
# BUY (lower band)
reason=f"Precio en/bajo banda inferior Bollinger ({float(lower):.2f})",

# SELL (upper band)
reason=f"Precio en/sobre banda superior Bollinger ({float(upper):.2f})",
```

**Step 4: stop_loss.py** — two strings:

```python
# SELL stop-loss
reason=f"Stop-loss activado: caída del {abs(float(change)*100):.1f}%",

# SELL take-profit
reason=f"Take-profit activado: subida del {float(change)*100:.1f}%",
```

**Step 5: safe_haven.py** — one string:

```python
reason=f"Drawdown {float(drawdown) * 100:.1f}% desde máximo — rotando a activo refugio",
```

**Step 6: engine.py stop-loss layer** (around line 97) — already partially in Spanish, update for consistency:

```python
reason=(
    f"Stop-loss de cesta {basket.stop_loss_pct}% activado"
    f" (entrada: {pos.avg_price:.2f})"
),
```

**Step 7: Run full suite**

```bash
.venv/bin/pytest tests/ -q
```

Expected: all tests pass (reason strings are only tested for presence/content in a few tests — check if any break).

**Step 8: Commit**

```bash
git add src/strategies/ src/alerts/engine.py
git commit -m "i18n(strategies): translate all signal reason strings to Spanish"
```

---

## Task 5: AlertEngine — integrate MarketContext into _scan_basket

**Files:**
- Modify: `src/alerts/engine.py`

**Step 1: Add import at top of engine.py**

After the existing imports, add:
```python
from src.alerts.market_context import MarketContext, compute_market_context
```

**Step 2: Change `new_alerts` type annotation**

Find the line (around line 76):
```python
new_alerts: list[tuple[Alert, str]] = []
```

Replace with:
```python
new_alerts: list[tuple[Alert, str, MarketContext]] = []
```

**Step 3: Compute MarketContext and append to new_alerts**

Find the block where the alert is created and appended (around line 123-130):

```python
alert = Alert(
    basket_id=basket.id, asset_id=asset.id,
    strategy=basket.strategy, signal=signal.action,
    price=signal.price, reason=signal.reason,
    status="PENDING",
)
session.add(alert)
new_alerts.append((alert, asset.ticker))
```

Replace with:

```python
alert = Alert(
    basket_id=basket.id, asset_id=asset.id,
    strategy=basket.strategy, signal=signal.action,
    price=signal.price, reason=signal.reason,
    status="PENDING",
)
session.add(alert)
market_ctx = compute_market_context(
    asset.ticker, historical.data, price_obj.price,
    pos, basket.cash, signal.action, signal.confidence,
)
new_alerts.append((alert, asset.ticker, market_ctx))
```

**Step 4: Update the notification loop**

Find the loop (around line 138-141):
```python
if new_alerts:
    await session.flush()  # assign IDs before notify
    for alert, ticker in new_alerts:
        await self._notify(alert, basket.name, ticker)
```

Replace with:
```python
if new_alerts:
    await session.flush()  # assign IDs before notify
    for alert, ticker, market_ctx in new_alerts:
        await self._notify(alert, basket.name, ticker, market_ctx)
```

**Step 5: Run full suite**

```bash
.venv/bin/pytest tests/ -q
```

Expected: all tests pass (existing alert engine tests use mocks; _notify signature change caught here if tests check it).

**Step 6: Commit**

```bash
git add src/alerts/engine.py
git commit -m "feat(alerts): compute MarketContext in _scan_basket and pass to _notify"
```

---

## Task 6: Enriched _notify() + _build_explanation() + tests

**Files:**
- Modify: `src/alerts/engine.py`
- Create: `tests/test_alert_explanation.py`

**Step 1: Write the failing tests first**

Create `tests/test_alert_explanation.py`:

```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.alerts.engine import AlertEngine
from src.alerts.market_context import MarketContext


def _make_ctx(confidence: float = 0.7) -> MarketContext:
    return MarketContext(
        ticker="SAN.MC",
        price=Decimal("4.18"),
        sma20=4.25,
        sma50=4.10,
        rsi14=71.3,
        atr_pct=1.9,
        trend="lateral",
        position_qty=Decimal("20"),
        avg_price=Decimal("4.32"),
        pnl_pct=-3.2,
        confidence=confidence,
        suggested_qty=Decimal("20"),
    )


@pytest.mark.asyncio
async def test_build_explanation_returns_text():
    """_build_explanation returns the text from Haiku response."""
    engine = AlertEngine()
    ctx = _make_ctx()

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="El RSI ha tocado sobrecompra...")]

    with patch("src.alerts.engine.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(return_value=mock_response)
        result = await engine._build_explanation("rsi", "SELL", "RSI saliendo...", ctx)

    assert result == "El RSI ha tocado sobrecompra..."


@pytest.mark.asyncio
async def test_build_explanation_returns_none_on_api_failure():
    """If Haiku call fails, returns None (alert is still sent without explanation)."""
    engine = AlertEngine()
    ctx = _make_ctx()

    with patch("src.alerts.engine.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(side_effect=Exception("timeout"))
        result = await engine._build_explanation("rsi", "SELL", "RSI saliendo...", ctx)

    assert result is None
```

**Step 2: Run to confirm they fail**

```bash
.venv/bin/pytest tests/test_alert_explanation.py -v
```

Expected: `AttributeError: 'AlertEngine' object has no attribute '_build_explanation'`

**Step 3: Update `_notify()` signature and body in engine.py**

Replace the entire `_notify` method with:

```python
async def _notify(
    self,
    alert: Alert,
    basket_name: str,
    ticker: str,
    ctx: MarketContext,
) -> None:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from src.db.models import BasketMember, User

    if not self.app:
        logger.warning("No telegram app set — cannot send notifications")
        return

    async with async_session_factory() as session:
        result = await session.execute(
            select(BasketMember, User)
            .join(User, BasketMember.user_id == User.id)
            .where(BasketMember.basket_id == alert.basket_id)
        )
        members = result.all()

    icon = "⚠️" if alert.signal == "SELL" else "💡"
    verb = "VENTA" if alert.signal == "SELL" else "COMPRA"
    color = "🔴" if alert.signal == "SELL" else "🟢"

    conf_str = f" | Confianza: {int(ctx.confidence * 100)}%"

    # Position line
    if ctx.position_qty > 0 and ctx.avg_price:
        pnl_str = f" (P&L: {ctx.pnl_pct:+.1f}%)" if ctx.pnl_pct is not None else ""
        pos_line = f"Posición: {ctx.position_qty} acc @ {ctx.avg_price:.2f} €{pnl_str}"
    else:
        pos_line = "Posición: sin entrada previa"

    # Indicators
    sma20_s = f"{ctx.sma20:.2f}" if ctx.sma20 else "N/D"
    sma50_s = f"{ctx.sma50:.2f}" if ctx.sma50 else "N/D"
    rsi_s   = f"{ctx.rsi14:.1f}" if ctx.rsi14 else "N/D"
    atr_s   = f"{ctx.atr_pct:.1f}%" if ctx.atr_pct else "N/D"

    lines = [
        f"{icon} *{basket_name}* — {alert.strategy}",
        "",
        f"{color} {verb}: *{ticker}*",
        f"Precio: {alert.price:.2f} €{conf_str}",
        pos_line,
        f"Cantidad sugerida: {ctx.suggested_qty} acc",
        f"Razón: {alert.reason}",
        f"SMA20: {sma20_s} | SMA50: {sma50_s} | RSI: {rsi_s} | ATR: {atr_s}",
        f"Tendencia: {ctx.trend}",
    ]

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ejecutar", callback_data=f"alert:confirm:{alert.id}"),
        InlineKeyboardButton("❌ Rechazar", callback_data=f"alert:reject:{alert.id}"),
    ]])

    for _, user in members:
        try:
            text = "\n".join(lines)
            if not user.advanced_mode:
                explanation = await self._build_explanation(
                    alert.strategy, alert.signal, alert.reason, ctx
                )
                if explanation:
                    text += f"\n\n💬 _{explanation}_"
            text += f"\n\n¿Ejecutar {verb.lower()}?"
            await self.app.bot.send_message(
                chat_id=user.tg_id, text=text,
                parse_mode="Markdown", reply_markup=keyboard,
            )
        except Exception as e:
            logger.error(f"Cannot notify tg_id={user.tg_id}: {e}")


async def _build_explanation(
    self,
    strategy: str,
    signal: str,
    reason: str,
    ctx: MarketContext,
) -> str | None:
    """Call Claude Haiku to generate a 2-3 sentence educational explanation.

    Returns None if the API call fails so the alert is still sent without it.
    """
    try:
        client = AsyncAnthropic()
        sma20_s = f"{ctx.sma20:.2f}" if ctx.sma20 else "N/D"
        sma50_s = f"{ctx.sma50:.2f}" if ctx.sma50 else "N/D"
        rsi_s   = f"{ctx.rsi14:.1f}" if ctx.rsi14 else "N/D"
        atr_s   = f"{ctx.atr_pct:.1f}%" if ctx.atr_pct else "N/D"

        prompt = (
            f"Eres un asesor financiero educativo para un inversor principiante que practica paper trading.\n"
            f"Se ha generado una señal de {signal} para {ctx.ticker}.\n\n"
            f"Estrategia: {strategy}\n"
            f"Razón técnica: {reason}\n"
            f"Precio actual: {ctx.price:.2f}\n"
            f"SMA20: {sma20_s} | SMA50: {sma50_s}\n"
            f"RSI(14): {rsi_s} | ATR: {atr_s}\n"
            f"Tendencia: {ctx.trend}\n"
        )
        if ctx.avg_price and ctx.pnl_pct is not None:
            prompt += f"Posición: entrada a {ctx.avg_price:.2f}, P&L actual: {ctx.pnl_pct:+.1f}%\n"

        prompt += (
            "\nExplica en 2-3 frases cortas y en español:\n"
            "1. Qué significa esta señal técnicamente.\n"
            "2. Por qué es relevante ahora según los indicadores.\n"
            "3. Un recordatorio breve de que es paper trading (sin dinero real).\n"
            "Sé conciso y no uses markdown."
        )

        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as e:
        logger.warning("Haiku explanation failed for %s: %s", ctx.ticker, e)
        return None
```

**Step 4: Add AsyncAnthropic import at the top of engine.py**

After the existing imports, add:
```python
from anthropic import AsyncAnthropic
```

**Step 5: Run explanation tests**

```bash
.venv/bin/pytest tests/test_alert_explanation.py -v
```

Expected: both tests PASS.

**Step 6: Run full suite**

```bash
.venv/bin/pytest tests/ -q
```

Expected: all tests pass.

**Step 7: Commit**

```bash
git add src/alerts/engine.py tests/test_alert_explanation.py
git commit -m "feat(alerts): enriched _notify with position/indicators + Haiku explanation"
```

---

## Task 7: /modo command + registration

**Files:**
- Modify: `src/bot/handlers/admin.py`
- Modify: `src/bot/bot.py`
- Modify: `src/bot/handlers/help.py`

**Step 1: Add cmd_modo to admin.py**

Add at the end of `admin.py`, before `get_handlers()`:

```python
async def cmd_modo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage:
      /modo           — show current mode
      /modo avanzado  — enable advanced mode (concise technical alerts)
      /modo basico    — enable basic mode (alerts with Haiku explanation)
    """
    if not update.message:
        return
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.tg_id == update.effective_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await update.message.reply_text("Usa /start primero.")
            return

        if not context.args:
            mode = "avanzado (solo datos técnicos)" if user.advanced_mode else "básico (datos + explicación)"
            await update.message.reply_text(
                f"Modo actual: *{mode}*\n\n"
                "Cambia con `/modo avanzado` o `/modo basico`.",
                parse_mode="Markdown",
            )
            return

        arg = context.args[0].lower()
        if arg == "avanzado":
            user.advanced_mode = True
            await session.commit()
            await update.message.reply_text("✅ Modo *avanzado* activado: recibirás alertas técnicas concisas.", parse_mode="Markdown")
        elif arg == "basico":
            user.advanced_mode = False
            await session.commit()
            await update.message.reply_text("✅ Modo *básico* activado: recibirás alertas con explicación educativa.", parse_mode="Markdown")
        else:
            await update.message.reply_text("Uso: `/modo avanzado` o `/modo basico`", parse_mode="Markdown")
```

Also add `CommandHandler("modo", cmd_modo)` to the `return` list in `get_handlers()`.

**Step 2: Register in bot.py**

In `src/bot/bot.py`, the `admin_handlers()` import already covers admin.py, so no new import needed — `cmd_modo` is registered via `get_handlers()` in admin.py. Verify `bot.py` calls `for handler in admin_handlers(): app.add_handler(handler)` — it does.

**Step 3: Add to help.py COMMAND_LIST**

In `src/bot/handlers/help.py`, in the `# --- Admin ---` section, add before `/register`:

```python
("modo", "[avanzado|basico]", "Modo de alertas: técnico conciso o con explicación educativa"),
```

**Step 4: Run full suite**

```bash
.venv/bin/pytest tests/ -q
```

Expected: all tests pass.

**Step 5: Commit and push**

```bash
git add src/bot/handlers/admin.py src/bot/bot.py src/bot/handlers/help.py
git commit -m "feat: /modo command to toggle advanced/basic alert mode"
git push origin main
```

---

## Final verification

```bash
.venv/bin/pytest tests/ -v
```

Expected: all tests green (152+ passing).

**Deploy steps:**
```bash
.venv/bin/alembic upgrade head   # applies add_user_advanced_mode migration
# restart bot service
sudo systemctl restart scroogebot
```

**Test in Telegram:**
```
/modo               → shows current mode (básico by default)
/modo avanzado      → switches to concise mode
/modo basico        → switches back to explanatory mode
/modo               → confirms mode changed
```
