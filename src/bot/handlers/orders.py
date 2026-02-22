import logging
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Asset, Basket, User
from src.data.yahoo import YahooDataProvider
from src.orders.paper import PaperTradingExecutor
from src.bot.audit import log_command

logger = logging.getLogger(__name__)
_provider = YahooDataProvider()
_executor = PaperTradingExecutor()


def _parse_order_args(args: list[str]) -> tuple[str, Decimal | None, str | None]:
    """Parse /compra or /vende args.

    Returns (ticker, quantity, basket_override_name).
    basket_override_name is set when args[2:] start with @.
    quantity is None if parsing fails.
    """
    if len(args) < 2:
        return "", None, None

    ticker = args[0].upper()
    try:
        quantity = Decimal(args[1])
    except InvalidOperation:
        return ticker, None, None

    basket_override = None
    if len(args) > 2 and args[2].startswith("@"):
        parts = [args[2].lstrip("@")] + list(args[3:])
        basket_override = " ".join(parts)

    return ticker, quantity, basket_override


async def _handle_order(update: Update, context, order_type: str) -> None:
    cmd = "/compra" if order_type == "BUY" else "/vende"
    raw_args = " ".join(context.args) if context.args else ""

    if len(context.args) < 2:
        await update.message.reply_text(
            f"Uso: `{cmd} TICKER cantidad [@cesta]`\n"
            "Ejemplo: `/compra AAPL 10` — usa la cesta activa\n"
            "Ejemplo: `/compra AAPL 10 @Cesta Agresiva` — override puntual",
            parse_mode="Markdown",
        )
        return

    ticker, quantity, basket_override = _parse_order_args(list(context.args))

    if quantity is None:
        await update.message.reply_text("Cantidad inválida.")
        return
    if quantity <= 0:
        await update.message.reply_text("Cantidad debe ser positiva.")
        return

    try:
        price_obj = _provider.get_current_price(ticker)
    except Exception as e:
        err = f"Error obteniendo precio de {ticker}: {e}"
        await update.message.reply_text(err)
        await log_command(update, cmd, False, err, raw_args)
        return

    async with async_session_factory() as session:
        # Resolve caller
        caller_result = await session.execute(select(User).where(User.tg_id == update.effective_user.id))
        caller = caller_result.scalar_one_or_none()

        # Resolve asset
        asset_result = await session.execute(select(Asset).where(Asset.ticker == ticker))
        asset = asset_result.scalar_one_or_none()
        if not asset:
            err = f"Ticker {ticker} no está en ninguna cesta."
            await update.message.reply_text(err)
            await log_command(update, cmd, False, err, raw_args)
            return

        # Resolve basket
        if basket_override:
            basket_result = await session.execute(
                select(Basket).where(Basket.name == basket_override, Basket.active == True)
            )
            basket = basket_result.scalar_one_or_none()
            if not basket:
                err = f"Cesta '@{basket_override}' no encontrada."
                await update.message.reply_text(err)
                await log_command(update, cmd, False, err, raw_args)
                return
        else:
            if not caller or not caller.active_basket_id:
                await update.message.reply_text(
                    "🗂 Sin cesta activa. Usa `/sel <nombre>` para seleccionar una.",
                    parse_mode="Markdown",
                )
                return
            basket_result = await session.execute(
                select(Basket).where(Basket.id == caller.active_basket_id, Basket.active == True)
            )
            basket = basket_result.scalar_one_or_none()
            if not basket:
                await update.message.reply_text(
                    "🗂 La cesta seleccionada ya no está activa. Usa `/sel <nombre>` para elegir otra.",
                    parse_mode="Markdown",
                )
                return

        user_id = caller.id if caller else 0
        try:
            if order_type == "BUY":
                await _executor.buy(session, basket.id, asset.id, user_id, ticker, quantity, price_obj.price)
            else:
                await _executor.sell(session, basket.id, asset.id, user_id, ticker, quantity, price_obj.price)

            verb = "Compra" if order_type == "BUY" else "Venta"
            ok_msg = (
                f"🗂 `{basket.name}`\n"
                f"✅ *{verb} ejecutada*\n"
                f"{quantity} {ticker} × {price_obj.price:.2f} {price_obj.currency}\n"
                f"Total: {quantity * price_obj.price:.2f} {price_obj.currency}"
            )
            await update.message.reply_text(ok_msg, parse_mode="Markdown")
            await log_command(update, cmd, True, f"{verb} {quantity} {ticker} @ {price_obj.price:.2f}", raw_args)
        except ValueError as e:
            err = str(e)
            await update.message.reply_text(f"❌ {err}")
            await log_command(update, cmd, False, err, raw_args)


async def cmd_compra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_order(update, context, "BUY")


async def cmd_vende(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_order(update, context, "SELL")


def get_handlers():
    return [
        CommandHandler("compra", cmd_compra),
        CommandHandler("vende", cmd_vende),
    ]
