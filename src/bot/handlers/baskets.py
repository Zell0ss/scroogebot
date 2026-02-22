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
            lines.append(f"• `{b.name}` — estrategia: `{b.strategy}` ({b.risk_profile})")
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
            f"🗂 `{basket.name}`",
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


async def cmd_sel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /sel [nombre_cesta] — select active basket or show current selection."""
    if not update.message:
        return

    async with async_session_factory() as session:
        caller_result = await session.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        caller = caller_result.scalar_one_or_none()
        if not caller:
            await update.message.reply_text("Usa /start primero.")
            return

        # No args → show current selection
        if not context.args:
            if caller.active_basket_id is None:
                await update.message.reply_text(
                    "🗂 Sin cesta seleccionada.\nUsa `/sel <nombre>` para elegir una.",
                    parse_mode="Markdown",
                )
            else:
                basket_result = await session.execute(
                    select(Basket).where(Basket.id == caller.active_basket_id)
                )
                basket = basket_result.scalar_one_or_none()
                name = basket.name if basket else "desconocida"
                await update.message.reply_text(
                    f"🗂 Cesta activa: `{name}`",
                    parse_mode="Markdown",
                )
            return

        # With args → select basket by name
        basket_name = " ".join(context.args)
        basket_result = await session.execute(
            select(Basket).where(Basket.name == basket_name, Basket.active == True)
        )
        basket = basket_result.scalar_one_or_none()
        if not basket:
            await update.message.reply_text(f"Cesta '{basket_name}' no encontrada.")
            return

        caller.active_basket_id = basket.id
        await session.commit()
        await update.message.reply_text(
            f"🗂 Cesta activa: `{basket.name}`",
            parse_mode="Markdown",
        )


def get_handlers():
    return [
        CommandHandler("cestas", cmd_cestas),
        CommandHandler("cesta", cmd_cesta),
        CommandHandler("sel", cmd_sel),
    ]
