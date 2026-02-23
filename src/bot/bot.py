import asyncio
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
from src.bot.handlers.backtest import get_handlers as backtest_handlers
from src.bot.handlers.sizing import get_handlers as sizing_handlers
from src.bot.handlers.search import get_handlers as search_handlers
from src.bot.handlers.montecarlo import get_handlers as montecarlo_handlers
from src.bot.handlers.help import get_handlers as help_handlers
from src.alerts.engine import AlertEngine
from src.bot.audit import log_command
from src.db.base import async_session_factory
from src.metrics import start_metrics_server
from src.scheduler.market_hours import is_market_open

logger = logging.getLogger(__name__)


async def handle_alert_callback(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    if len(parts) != 3 or parts[0] != "alert":
        return

    action, alert_id = parts[1], int(parts[2])

    from src.db.models import Alert, Asset, Basket, BasketMember, Position, User
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
            await query.edit_message_text("Usa /start primero.")
            return

        member_check = await session.execute(
            select(BasketMember).where(
                BasketMember.basket_id == basket.id,
                BasketMember.user_id == user.id,
            )
        )
        if not member_check.scalar_one_or_none():
            await query.edit_message_text("No tienes acceso a esta cesta.")
            return

        if action == "reject":
            alert.status = "REJECTED"
            alert.resolved_at = datetime.utcnow()
            await session.commit()
            msg = f"Alerta rechazada: {asset.ticker}"
            await query.edit_message_text(f"❌ {msg}")
            await log_command(update, "/alert:reject", True, msg, f"alert_id={alert_id}")
            return

        if action == "confirm":
            # Guard: do not execute at stale prices when market is closed
            if asset.market and not is_market_open(asset.market):
                await query.edit_message_text(
                    f"❌ Mercado {asset.market} cerrado ahora.\n"
                    "La alerta sigue activa — confírmala cuando abra el mercado,\n"
                    "o usa /compra para ejecutar manualmente."
                )
                return
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
                ok_msg = f"{alert.signal} {asset.ticker} ejecutado a {price:.2f}"
                await query.edit_message_text(f"✅ {ok_msg}")
                await log_command(update, "/alert:confirm", True, ok_msg, f"alert_id={alert_id}")
            except Exception as e:
                err = str(e)
                logger.error(f"Alert execution error: {err}")
                await query.edit_message_text(f"❌ Error: {err}")
                await log_command(update, "/alert:confirm", False, err, f"alert_id={alert_id}")


async def run() -> None:
    metrics_port = app_config.get("metrics", {}).get("port", 9090)
    start_metrics_server(metrics_port)

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
    for handler in backtest_handlers():
        app.add_handler(handler)
    for handler in sizing_handlers():
        app.add_handler(handler)
    for handler in search_handlers():
        app.add_handler(handler)
    for handler in montecarlo_handlers():
        app.add_handler(handler)
    for handler in help_handlers():          # ← LAST: fallback catches unknown commands
        app.add_handler(handler)

    app.add_handler(CallbackQueryHandler(handle_alert_callback, pattern="^alert:"))

    alert_engine = AlertEngine(telegram_app=app)
    scheduler = AsyncIOScheduler()
    interval = app_config["scheduler"]["interval_minutes"]
    scheduler.add_job(alert_engine.scan_all_baskets, "interval", minutes=interval)

    async with app:
        await app.start()
        scheduler.start()
        logger.info(f"ScroogeBot starting — scanning every {interval}min")
        await app.updater.start_polling(drop_pending_updates=True)
        try:
            await asyncio.sleep(float("inf"))
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            scheduler.shutdown(wait=False)
            await app.updater.stop()
            await app.stop()
