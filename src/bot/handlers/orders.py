import logging
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Asset, Basket, User
from src.data.yahoo import YahooDataProvider
from src.orders.paper import PaperTradingExecutor

logger = logging.getLogger(__name__)
_provider = YahooDataProvider()
_executor = PaperTradingExecutor()


async def _get_or_create_user(session, tg_user) -> User:
    result = await session.execute(select(User).where(User.tg_id == tg_user.id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(tg_id=tg_user.id, username=tg_user.username, first_name=tg_user.first_name)
        session.add(user)
        await session.flush()
    return user


async def _handle_order(update: Update, context, order_type: str) -> None:
    if len(context.args) < 2:
        await update.message.reply_text(f"Uso: /{order_type.lower()} TICKER cantidad")
        return
    ticker = context.args[0].upper()
    try:
        quantity = Decimal(context.args[1])
    except InvalidOperation:
        await update.message.reply_text("Cantidad inválida.")
        return
    if quantity <= 0:
        await update.message.reply_text("Cantidad debe ser positiva.")
        return

    try:
        price_obj = _provider.get_current_price(ticker)
    except Exception as e:
        await update.message.reply_text(f"Error obteniendo precio de {ticker}: {e}")
        return

    async with async_session_factory() as session:
        asset_result = await session.execute(select(Asset).where(Asset.ticker == ticker))
        asset = asset_result.scalar_one_or_none()
        if not asset:
            await update.message.reply_text(f"Ticker {ticker} no está en ninguna cesta.")
            return

        basket_result = await session.execute(select(Basket).where(Basket.active == True))
        basket = basket_result.scalars().first()
        if not basket:
            await update.message.reply_text("No hay cestas activas.")
            return

        user = await _get_or_create_user(session, update.effective_user)
        try:
            if order_type == "BUY":
                await _executor.buy(session, basket.id, asset.id, user.id, ticker, quantity, price_obj.price)
            else:
                await _executor.sell(session, basket.id, asset.id, user.id, ticker, quantity, price_obj.price)
            verb = "Compra" if order_type == "BUY" else "Venta"
            await update.message.reply_text(
                f"✅ *{verb} ejecutada*\n"
                f"{quantity} {ticker} × {price_obj.price:.2f} {price_obj.currency}\n"
                f"Total: {quantity * price_obj.price:.2f} {price_obj.currency}",
                parse_mode="Markdown",
            )
        except ValueError as e:
            await update.message.reply_text(f"❌ {e}")


async def cmd_compra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_order(update, context, "BUY")


async def cmd_vende(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_order(update, context, "SELL")


def get_handlers():
    return [
        CommandHandler("compra", cmd_compra),
        CommandHandler("vende", cmd_vende),
    ]
