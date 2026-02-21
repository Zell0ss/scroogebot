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
