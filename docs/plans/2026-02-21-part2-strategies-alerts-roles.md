# ScroogeBot — Part 2: Strategies, AlertEngine & Roles

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Slices 4-6 — `/cestas`, `/analiza`, two core strategies (StopLoss, MACrossover), automatic alert scanning via APScheduler, and role-based access (OWNER/MEMBER) with inline keyboard confirmations.

**Prerequisites:** Part 1 complete. All tables exist in DB, bot starts, `/compra` and `/valoracion` work.

**Tech Stack:** pandas-ta for indicators, APScheduler 3.x for scheduling, python-telegram-bot inline keyboards for confirmations.

---

## Task 1: Basket Commands `/cestas`, `/cesta`, `/analiza`

**Files:**
- Create: `src/bot/handlers/baskets.py`
- Create: `src/bot/handlers/analysis.py`

**Step 1: Write `src/bot/handlers/baskets.py`**

```python
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Basket, BasketAsset, Asset, BasketMember, User

logger = logging.getLogger(__name__)


async def cmd_cestas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(Basket).where(Basket.active == True))
        baskets = result.scalars().all()
        if not baskets:
            await update.message.reply_text("No hay cestas configuradas.")
            return
        lines = ["🗂 *Cestas disponibles*\n"]
        for b in baskets:
            lines.append(f"• *{b.name}* — estrategia: `{b.strategy}` ({b.risk_profile})")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_cesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /cesta nombre_cesta")
        return
    name = " ".join(context.args)
    async with async_session_factory() as session:
        result = await session.execute(select(Basket).where(Basket.name == name))
        basket = result.scalar_one_or_none()
        if not basket:
            await update.message.reply_text(f"Cesta '{name}' no encontrada.")
            return

        assets_result = await session.execute(
            select(Asset)
            .join(BasketAsset, BasketAsset.asset_id == Asset.id)
            .where(BasketAsset.basket_id == basket.id, BasketAsset.active == True)
        )
        members_result = await session.execute(
            select(BasketMember, User)
            .join(User, BasketMember.user_id == User.id)
            .where(BasketMember.basket_id == basket.id)
        )
        lines = [
            f"🗂 *{basket.name}*",
            f"Estrategia: `{basket.strategy}` | Perfil: {basket.risk_profile}",
            f"Cash: {basket.cash:.2f}€",
            "\n*Assets:*",
        ]
        for a in assets_result.scalars().all():
            lines.append(f"  • {a.ticker} ({a.market})")
        lines.append("\n*Miembros:*")
        for m, u in members_result.all():
            lines.append(f"  • @{u.username or u.first_name} [{m.role}]")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def get_handlers():
    return [
        CommandHandler("cestas", cmd_cestas),
        CommandHandler("cesta", cmd_cesta),
    ]
```

**Step 2: Write `src/bot/handlers/analysis.py`**

```python
import logging
from decimal import Decimal

import pandas_ta as ta
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from src.data.yahoo import YahooDataProvider

logger = logging.getLogger(__name__)
_provider = YahooDataProvider()


async def cmd_analiza(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /analiza TICKER")
        return
    ticker = context.args[0].upper()
    msg = await update.message.reply_text(f"⏳ Analizando {ticker}...")
    try:
        price = _provider.get_current_price(ticker)
        ohlcv = _provider.get_historical(ticker, period="3mo", interval="1d")
        close = ohlcv.data["Close"]

        rsi_series = ta.rsi(close, length=14)
        rsi_val = rsi_series.iloc[-1] if rsi_series is not None and not rsi_series.empty else None
        sma20 = close.rolling(20).mean().iloc[-1]
        sma50 = close.rolling(50).mean().iloc[-1]
        change_1d = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100
        sign = "+" if change_1d >= 0 else ""

        lines = [
            f"📊 *Análisis: {ticker}*",
            f"💰 Precio: {price.price:.2f} {price.currency}",
            f"📅 Cambio 1d: {sign}{change_1d:.2f}%",
            "",
            f"SMA 20: {sma20:.2f}",
            f"SMA 50: {sma50:.2f}",
            f"Tendencia: {'📈 Alcista' if sma20 > sma50 else '📉 Bajista'}",
        ]
        if rsi_val is not None:
            if rsi_val > 70:
                rsi_label = "sobrecomprado 🔴"
            elif rsi_val < 30:
                rsi_label = "sobrevendido 🟢"
            else:
                rsi_label = "neutral ⚪"
            lines.append(f"RSI (14): {rsi_val:.1f} — {rsi_label}")
        lines.append(f"\n🔍 [Finviz](https://finviz.com/quote.ashx?t={ticker})")
        await msg.edit_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Error analizando {ticker}: {e}")


def get_handlers():
    return [CommandHandler("analiza", cmd_analiza)]
```

**Step 3: Register in `src/bot/bot.py`**

Add imports and register in `run()`:
```python
from src.bot.handlers.baskets import get_handlers as basket_handlers
from src.bot.handlers.analysis import get_handlers as analysis_handlers
# In run():
for handler in basket_handlers():
    app.add_handler(handler)
for handler in analysis_handlers():
    app.add_handler(handler)
```

**Step 4: Test manually**

Start bot, try `/cestas`, `/cesta Cesta Agresiva`, `/analiza AAPL`. Stop with Ctrl+C.

**Step 5: Commit**

```bash
git add src/bot/handlers/baskets.py src/bot/handlers/analysis.py src/bot/bot.py
git commit -m "feat: /cestas, /cesta, /analiza commands"
```

---

## Task 2: Strategy Engine

**Files:**
- Create: `src/strategies/__init__.py`
- Create: `src/strategies/base.py`
- Create: `src/strategies/stop_loss.py`
- Create: `src/strategies/ma_crossover.py`
- Create: `tests/test_strategies.py`

**Step 1: Write `src/strategies/__init__.py`** (empty)

**Step 2: Write `src/strategies/base.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
import pandas as pd


@dataclass
class Signal:
    action: str        # BUY | SELL | HOLD
    ticker: str
    price: Decimal
    reason: str
    confidence: float = 1.0


class Strategy(ABC):
    @abstractmethod
    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        """Return a Signal or None (hold)."""
        ...
```

**Step 3: Write failing tests `tests/test_strategies.py`**

```python
import pytest
import pandas as pd
from decimal import Decimal
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy


def make_df(prices: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(prices), freq="D")
    return pd.DataFrame({"Close": prices}, index=idx)


def test_stop_loss_triggers_sell():
    strategy = StopLossStrategy()
    df = make_df([100.0] * 61)
    signal = strategy.evaluate("AAPL", df, Decimal("88"))  # 12% drop > 8% threshold
    assert signal is not None
    assert signal.action == "SELL"
    assert "Stop-loss" in signal.reason


def test_take_profit_triggers_sell():
    strategy = StopLossStrategy()
    df = make_df([100.0] * 61)
    signal = strategy.evaluate("AAPL", df, Decimal("120"))  # 20% gain > 15% threshold
    assert signal is not None
    assert signal.action == "SELL"
    assert "Take-profit" in signal.reason


def test_no_signal_within_thresholds():
    strategy = StopLossStrategy()
    df = make_df([100.0] * 61)
    signal = strategy.evaluate("AAPL", df, Decimal("100"))
    assert signal is None


def test_ma_crossover_runs_without_error():
    strategy = MACrossoverStrategy()
    prices = [100.0 + i * 0.1 for i in range(80)]
    df = make_df(prices)
    signal = strategy.evaluate("AAPL", df, Decimal("108"))
    if signal:
        assert signal.action in ("BUY", "SELL")
```

**Step 4: Run tests — expect ImportError (not yet written)**

```bash
.venv/bin/pytest tests/test_strategies.py -v
```

**Step 5: Write `src/strategies/stop_loss.py`**

```python
from decimal import Decimal
import pandas as pd
from src.strategies.base import Strategy, Signal
from src.config import app_config


class StopLossStrategy(Strategy):
    def __init__(self):
        cfg = app_config["strategies"]["stop_loss"]
        self.stop_loss_pct = Decimal(str(cfg["stop_loss_pct"])) / 100
        self.take_profit_pct = Decimal(str(cfg["take_profit_pct"])) / 100

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        if len(data) < 2:
            return None
        open_price = Decimal(str(data["Close"].iloc[0]))
        if open_price == 0:
            return None
        change = (current_price - open_price) / open_price

        if change <= -self.stop_loss_pct:
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"Stop-loss triggered: {change*100:.1f}% drop",
                confidence=0.95,
            )
        if change >= self.take_profit_pct:
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"Take-profit triggered: {change*100:.1f}% gain",
                confidence=0.9,
            )
        return None
```

**Step 6: Write `src/strategies/ma_crossover.py`**

```python
from decimal import Decimal
import pandas as pd
from src.strategies.base import Strategy, Signal
from src.config import app_config


class MACrossoverStrategy(Strategy):
    def __init__(self):
        cfg = app_config["strategies"]["ma_crossover"]
        self.fast = cfg["fast_period"]
        self.slow = cfg["slow_period"]

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        if len(data) < self.slow + 1:
            return None
        close = data["Close"]
        fast_ma = close.rolling(self.fast).mean()
        slow_ma = close.rolling(self.slow).mean()

        if (fast_ma.iloc[-1] > slow_ma.iloc[-1]) and (fast_ma.iloc[-2] <= slow_ma.iloc[-2]):
            return Signal(
                action="BUY", ticker=ticker, price=current_price,
                reason=f"MA{self.fast} crossed above MA{self.slow}",
                confidence=0.75,
            )
        if (fast_ma.iloc[-1] < slow_ma.iloc[-1]) and (fast_ma.iloc[-2] >= slow_ma.iloc[-2]):
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"MA{self.fast} crossed below MA{self.slow}",
                confidence=0.75,
            )
        return None
```

**Step 7: Run tests**

```bash
.venv/bin/pytest tests/test_strategies.py -v
```

Expected: 4 tests PASS.

**Step 8: Commit**

```bash
git add src/strategies/ tests/test_strategies.py
git commit -m "feat: Strategy base class, StopLoss and MACrossover"
```

---

## Task 3: AlertEngine + APScheduler

**Files:**
- Create: `src/alerts/__init__.py`
- Create: `src/alerts/engine.py`
- Modify: `src/bot/bot.py`

**Step 1: Write `src/alerts/__init__.py`** (empty)

**Step 2: Write `src/alerts/engine.py`**

```python
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import async_session_factory
from src.db.models import Alert, Basket, Asset, Position
from src.data.yahoo import YahooDataProvider
from src.strategies.base import Strategy
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy

logger = logging.getLogger(__name__)

STRATEGY_MAP: dict[str, type[Strategy]] = {
    "stop_loss": StopLossStrategy,
    "ma_crossover": MACrossoverStrategy,
}


class AlertEngine:
    def __init__(self, telegram_app=None):
        self.data = YahooDataProvider()
        self.app = telegram_app

    async def scan_all_baskets(self) -> None:
        """Called by scheduler every N minutes."""
        logger.info("Alert scan started")
        async with async_session_factory() as session:
            result = await session.execute(select(Basket).where(Basket.active == True))
            for basket in result.scalars().all():
                await self._scan_basket(session, basket)

    async def _scan_basket(self, session: AsyncSession, basket: Basket) -> None:
        strategy_cls = STRATEGY_MAP.get(basket.strategy)
        if not strategy_cls:
            return
        strategy = strategy_cls()

        result = await session.execute(
            select(Position, Asset)
            .join(Asset, Position.asset_id == Asset.id)
            .where(Position.basket_id == basket.id, Position.quantity > 0)
        )
        for pos, asset in result.all():
            try:
                price_obj = self.data.get_current_price(asset.ticker)
                historical = self.data.get_historical(asset.ticker, period="3mo")
                signal = strategy.evaluate(asset.ticker, historical.data, price_obj.price)

                if not signal or signal.action not in ("BUY", "SELL"):
                    continue

                # Deduplicate: skip if a PENDING alert already exists
                existing = await session.execute(
                    select(Alert).where(
                        Alert.basket_id == basket.id,
                        Alert.asset_id == asset.id,
                        Alert.status == "PENDING",
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                alert = Alert(
                    basket_id=basket.id, asset_id=asset.id,
                    strategy=basket.strategy, signal=signal.action,
                    price=signal.price, reason=signal.reason,
                    status="PENDING",
                )
                session.add(alert)
                await session.flush()
                await session.commit()
                await self._notify(alert, basket.name, asset.ticker)

            except Exception as e:
                logger.error(f"Alert scan error {asset.ticker}: {e}")

    async def _notify(self, alert: Alert, basket_name: str, ticker: str) -> None:
        """Notify all basket members. Full implementation in Task 4 (roles)."""
        logger.info(f"ALERT [{alert.signal}] {ticker} in {basket_name}: {alert.reason}")
        # Telegram notification added in Task 4
```

**Step 3: Update `src/bot/bot.py` to add scheduler**

Replace the full file:

```python
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from src.config import settings, app_config
from src.bot.handlers.portfolio import get_handlers as portfolio_handlers
from src.bot.handlers.orders import get_handlers as order_handlers
from src.bot.handlers.baskets import get_handlers as basket_handlers
from src.bot.handlers.analysis import get_handlers as analysis_handlers
from src.alerts.engine import AlertEngine

logger = logging.getLogger(__name__)


async def run() -> None:
    app = Application.builder().token(settings.telegram_apikey).build()

    for handler in portfolio_handlers():
        app.add_handler(handler)
    for handler in order_handlers():
        app.add_handler(handler)
    for handler in basket_handlers():
        app.add_handler(handler)
    for handler in analysis_handlers():
        app.add_handler(handler)

    alert_engine = AlertEngine(telegram_app=app)
    scheduler = AsyncIOScheduler()
    interval = app_config["scheduler"]["interval_minutes"]
    scheduler.add_job(alert_engine.scan_all_baskets, "interval", minutes=interval)
    scheduler.start()

    logger.info(f"ScroogeBot starting — scanning every {interval}min")
    await app.run_polling(drop_pending_updates=True)
```

**Step 4: Test startup**

```bash
.venv/bin/python scroogebot.py
```

Expected: logs `ScroogeBot starting — scanning every 5min`. No errors. Stop with Ctrl+C.

**Step 5: Commit**

```bash
git add src/alerts/ src/bot/bot.py
git commit -m "feat: AlertEngine with strategy scanning + APScheduler"
```

---

## Task 4: User Registration + Roles + Alert Confirmations

**Files:**
- Create: `src/bot/handlers/admin.py`
- Modify: `src/alerts/engine.py` (full _notify with inline keyboard)
- Modify: `src/bot/bot.py` (add callback handler + admin handlers)

**Step 1: Write `src/bot/handlers/admin.py`**

```python
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import User, Basket, BasketMember, Watchlist

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_user.id))
        if not result.scalar_one_or_none():
            session.add(User(
                tg_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
            ))
            await session.commit()
    await update.message.reply_text(
        f"¡Hola {tg_user.first_name}! 🦆 Soy TioGilito.\n"
        "Usa /valoracion para ver el estado de tus cestas.\n"
        "Usa /cestas para ver las cestas disponibles."
    )


async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /adduser @username OWNER|MEMBER basket name"""
    if len(context.args) < 3:
        await update.message.reply_text("Uso: /adduser @username OWNER|MEMBER nombre_cesta")
        return
    username = context.args[0].lstrip("@")
    role = context.args[1].upper()
    basket_name = " ".join(context.args[2:])

    if role not in ("OWNER", "MEMBER"):
        await update.message.reply_text("Rol debe ser OWNER o MEMBER.")
        return

    async with async_session_factory() as session:
        basket_result = await session.execute(
            select(Basket).where(Basket.name == basket_name)
        )
        basket = basket_result.scalar_one_or_none()
        if not basket:
            await update.message.reply_text(f"Cesta '{basket_name}' no encontrada.")
            return

        # Verify caller is OWNER
        caller_result = await session.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        caller = caller_result.scalar_one_or_none()
        if caller:
            owner_check = await session.execute(
                select(BasketMember).where(
                    BasketMember.basket_id == basket.id,
                    BasketMember.user_id == caller.id,
                    BasketMember.role == "OWNER",
                )
            )
            if not owner_check.scalar_one_or_none():
                await update.message.reply_text("Solo el OWNER puede añadir usuarios.")
                return

        target_result = await session.execute(
            select(User).where(User.username == username)
        )
        target = target_result.scalar_one_or_none()
        if not target:
            await update.message.reply_text(
                f"@{username} no encontrado. El usuario debe enviar /start primero."
            )
            return

        existing = await session.execute(
            select(BasketMember).where(
                BasketMember.basket_id == basket.id,
                BasketMember.user_id == target.id,
            )
        )
        member = existing.scalar_one_or_none()
        if member:
            member.role = role
        else:
            session.add(BasketMember(basket_id=basket.id, user_id=target.id, role=role))
        await session.commit()
        await update.message.reply_text(f"✅ @{username} → {role} en '{basket_name}'.")


async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Watchlist).order_by(Watchlist.created_at.desc())
        )
        items = result.scalars().all()
        if not items:
            await update.message.reply_text("Watchlist vacía.")
            return
        lines = ["👀 *Watchlist*\n"]
        for item in items:
            icon = "🔴" if item.status == "PENDING" else "🟢"
            note = f" — {item.note}" if item.note else ""
            lines.append(f"{icon} *{item.ticker}* {item.name or ''}{note}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_addwatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /addwatch TICKER Company name | note"""
    if not context.args:
        await update.message.reply_text("Uso: /addwatch TICKER Nombre | nota")
        return
    ticker = context.args[0].upper()
    rest = " ".join(context.args[1:])
    name, _, note = rest.partition("|")

    async with async_session_factory() as session:
        user_result = await session.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            await update.message.reply_text("Usa /start primero.")
            return
        session.add(Watchlist(
            ticker=ticker, name=name.strip() or None,
            note=note.strip() or None, added_by=user.id,
        ))
        await session.commit()
    await update.message.reply_text(f"✅ {ticker} añadido a watchlist.")


def get_handlers():
    return [
        CommandHandler("start", cmd_start),
        CommandHandler("adduser", cmd_adduser),
        CommandHandler("watchlist", cmd_watchlist),
        CommandHandler("addwatch", cmd_addwatch),
    ]
```

**Step 2: Replace `_notify` in `src/alerts/engine.py` with full implementation**

Replace the existing `_notify` method:

```python
async def _notify(self, alert: Alert, basket_name: str, ticker: str) -> None:
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
    text = (
        f"{icon} *{basket_name}* — {alert.strategy}\n\n"
        f"{color} {verb}: *{ticker}*\n"
        f"Precio: {alert.price:.2f}\n"
        f"Razón: {alert.reason}\n\n"
        f"¿Ejecutar {verb.lower()}?"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ejecutar", callback_data=f"alert:confirm:{alert.id}"),
        InlineKeyboardButton("❌ Rechazar", callback_data=f"alert:reject:{alert.id}"),
    ]])

    for _, user in members:
        try:
            await self.app.bot.send_message(
                chat_id=user.tg_id, text=text,
                parse_mode="Markdown", reply_markup=keyboard,
            )
        except Exception as e:
            logger.error(f"Cannot notify tg_id={user.tg_id}: {e}")
```

**Step 3: Write the callback handler and update `src/bot/bot.py`**

Replace `src/bot/bot.py` with:

```python
import logging
from datetime import datetime
from decimal import Decimal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CallbackQueryHandler

from src.config import settings, app_config
from src.bot.handlers.portfolio import get_handlers as portfolio_handlers
from src.bot.handlers.orders import get_handlers as order_handlers
from src.bot.handlers.baskets import get_handlers as basket_handlers
from src.bot.handlers.analysis import get_handlers as analysis_handlers
from src.bot.handlers.admin import get_handlers as admin_handlers
from src.alerts.engine import AlertEngine

logger = logging.getLogger(__name__)


async def handle_alert_callback(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    if len(parts) != 3 or parts[0] != "alert":
        return

    action, alert_id = parts[1], int(parts[2])

    from src.db.base import async_session_factory
    from src.db.models import Alert, Asset, Basket, Position, User
    from src.data.yahoo import YahooDataProvider
    from src.orders.paper import PaperTradingExecutor
    from sqlalchemy import select

    async with async_session_factory() as session:
        alert = await session.get(Alert, alert_id)
        if not alert or alert.status != "PENDING":
            await query.edit_message_text("Esta alerta ya fue procesada.")
            return

        asset = await session.get(Asset, alert.asset_id)
        basket = await session.get(Basket, alert.basket_id)
        user_result = await session.execute(
            select(User).where(User.tg_id == query.from_user.id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            await query.answer("Usa /start primero.", show_alert=True)
            return

        if action == "reject":
            alert.status = "REJECTED"
            alert.resolved_at = datetime.utcnow()
            await session.commit()
            await query.edit_message_text(f"❌ Alerta rechazada: {asset.ticker}")
            return

        if action == "confirm":
            try:
                provider = YahooDataProvider()
                price = provider.get_current_price(asset.ticker).price
                executor = PaperTradingExecutor()

                if alert.signal == "SELL":
                    pos_result = await session.execute(
                        select(Position).where(
                            Position.basket_id == basket.id,
                            Position.asset_id == asset.id,
                        )
                    )
                    pos = pos_result.scalar_one_or_none()
                    qty = pos.quantity if pos else Decimal("0")
                    if qty > 0:
                        await executor.sell(
                            session, basket.id, asset.id, user.id,
                            asset.ticker, qty, price, alert.strategy,
                        )
                    else:
                        await query.edit_message_text("Sin posición para vender.")
                        return

                elif alert.signal == "BUY":
                    # Invest up to 10% of available cash
                    qty = (basket.cash * Decimal("0.10") / price).quantize(Decimal("0.01"))
                    if qty > 0:
                        await executor.buy(
                            session, basket.id, asset.id, user.id,
                            asset.ticker, qty, price, alert.strategy,
                        )
                    else:
                        await query.edit_message_text("Cash insuficiente.")
                        return

                alert.status = "CONFIRMED"
                alert.resolved_at = datetime.utcnow()
                await session.commit()
                await query.edit_message_text(
                    f"✅ {alert.signal} {asset.ticker} ejecutado a {price:.2f}"
                )
            except Exception as e:
                logger.error(f"Alert execution error: {e}")
                await query.edit_message_text(f"❌ Error: {e}")


async def run() -> None:
    app = Application.builder().token(settings.telegram_apikey).build()

    for handler in portfolio_handlers():
        app.add_handler(handler)
    for handler in order_handlers():
        app.add_handler(handler)
    for handler in basket_handlers():
        app.add_handler(handler)
    for handler in analysis_handlers():
        app.add_handler(handler)
    for handler in admin_handlers():
        app.add_handler(handler)

    app.add_handler(CallbackQueryHandler(handle_alert_callback, pattern="^alert:"))

    alert_engine = AlertEngine(telegram_app=app)
    scheduler = AsyncIOScheduler()
    interval = app_config["scheduler"]["interval_minutes"]
    scheduler.add_job(alert_engine.scan_all_baskets, "interval", minutes=interval)
    scheduler.start()

    logger.info(f"ScroogeBot starting — scanning every {interval}min")
    await app.run_polling(drop_pending_updates=True)
```

**Step 4: Test manually**

```bash
.venv/bin/python scroogebot.py
```

Test:
1. `/start` — registers user
2. `/adduser @yourself OWNER Cesta Agresiva` — sets role
3. `/cestas` — lists baskets
4. `/watchlist` — shows empty watchlist
5. `/addwatch ANTHROPIC Anthropic | pending IPO`
6. `/watchlist` — shows entry

**Step 5: Run all tests**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add src/bot/handlers/admin.py src/bot/bot.py src/alerts/engine.py
git commit -m "feat: /start, /adduser, roles, alert inline keyboard confirmations — Part 2 complete"
```

---

## Part 2 Done ✅

| Task | Feature |
|------|---------|
| 1 | /cestas, /cesta, /analiza |
| 2 | StopLoss + MACrossover strategies |
| 3 | AlertEngine + APScheduler (scan every 5min) |
| 4 | /start, /adduser, roles, alert confirmation keyboard |
| + | /watchlist, /addwatch |

**Next:** [Part 3 — Backtesting & Advanced Strategies](2026-02-21-part3-backtest-advanced.md)
