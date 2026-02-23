import logging
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Asset, Basket, BasketMember, Position, User
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


async def cmd_liquidarcesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /liquidarcesta <nombre> — vende todas las posiciones abiertas (OWNER)."""
    if not update.message or not context.args:
        await update.message.reply_text("Uso: `/liquidarcesta <nombre>`", parse_mode="Markdown")
        return

    basket_name = " ".join(context.args)

    async with async_session_factory() as session:
        caller_result = await session.execute(select(User).where(User.tg_id == update.effective_user.id))
        caller = caller_result.scalar_one_or_none()
        if not caller:
            await update.message.reply_text("Usa /start primero.")
            return

        basket_result = await session.execute(
            select(Basket).where(Basket.name == basket_name, Basket.active == True)
        )
        basket = basket_result.scalar_one_or_none()
        if not basket:
            await update.message.reply_text(f"Cesta '{basket_name}' no encontrada.")
            return

        owner_check = await session.execute(
            select(BasketMember).where(
                BasketMember.basket_id == basket.id,
                BasketMember.user_id == caller.id,
                BasketMember.role == "OWNER",
            )
        )
        if not owner_check.scalar_one_or_none():
            await update.message.reply_text("Solo el OWNER puede liquidar una cesta.")
            return

        pairs_result = await session.execute(
            select(Position, Asset)
            .join(Asset, Asset.id == Position.asset_id)
            .where(Position.basket_id == basket.id, Position.quantity > 0)
        )
        # Materialise to plain values before any commit expires ORM objects
        positions_data = [
            {
                "asset_id": asset.id,
                "ticker": asset.ticker,
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
            }
            for pos, asset in pairs_result.all()
        ]

        if not positions_data:
            await update.message.reply_text(
                f"`{basket_name}` no tiene posiciones abiertas.", parse_mode="Markdown"
            )
            return

        lines = [f"💰 *Liquidación:* `{basket_name}`\n"]
        total_recovered = Decimal("0")

        for item in positions_data:
            ticker = item["ticker"]
            try:
                price_obj = _provider.get_current_price(ticker)
                await _executor.sell(
                    session, basket.id, item["asset_id"], caller.id,
                    ticker, item["quantity"], price_obj.price,
                    triggered_by="MANUAL",
                )
                recovered = item["quantity"] * price_obj.price
                total_recovered += recovered
                pct = (price_obj.price - item["avg_price"]) / item["avg_price"] * 100
                sign = "+" if pct >= 0 else ""
                lines.append(
                    f"✅ *{ticker}*: {item['quantity']} × {price_obj.price:.2f}"
                    f"  ({sign}{pct:.1f}% vs entrada {item['avg_price']:.2f})"
                )
            except Exception as e:
                logger.error("Liquidation error %s/%s: %s", basket_name, ticker, e)
                lines.append(f"❌ *{ticker}*: {e}")

        lines.append(f"\n💵 Cash recuperado: {total_recovered:.2f}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_compra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_order(update, context, "BUY")


async def cmd_vende(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_order(update, context, "SELL")


def get_handlers():
    return [
        CommandHandler("compra", cmd_compra),
        CommandHandler("vende", cmd_vende),
        CommandHandler("liquidarcesta", cmd_liquidarcesta),
    ]
