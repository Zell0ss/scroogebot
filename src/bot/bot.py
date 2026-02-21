import logging
from telegram.ext import Application
from src.config import settings
from src.bot.handlers.portfolio import get_handlers as portfolio_handlers

logger = logging.getLogger(__name__)


async def run() -> None:
    app = Application.builder().token(settings.telegram_apikey).build()
    for handler in portfolio_handlers():
        app.add_handler(handler)
    logger.info("ScroogeBot starting...")
    await app.run_polling(drop_pending_updates=True)
