import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Basket, BasketAsset, Asset, BasketMember, Position, User
from src.utils.text import normalize_basket_name

logger = logging.getLogger(__name__)


async def cmd_cesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        async with async_session_factory() as session:
            result = await session.execute(select(Basket).where(Basket.active == True))
            baskets = result.scalars().all()
        if not baskets:
            await update.message.reply_text("No hay cestas configuradas.")
            return
        lines = ["🗂 *Cestas disponibles*\n"]
        for b in baskets:
            lines.append(f"• `{b.name}` — estrategia: `{b.strategy}` ({b.risk_profile})")
        lines.append("\nUsa `/cesta nombre` para ver el detalle de una cesta.")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return
    name = " ".join(context.args)
    async with async_session_factory() as session:
        result = await session.execute(select(Basket).where(Basket.name_normalized == normalize_basket_name(name), Basket.active == True))
        basket = result.scalar_one_or_none()
        if not basket:
            await update.message.reply_text(f"Cesta '{name}' no encontrada.")
            return

        # Predefined assets (model baskets)
        basket_assets = (await session.execute(
            select(Asset)
            .join(BasketAsset, BasketAsset.asset_id == Asset.id)
            .where(BasketAsset.basket_id == basket.id, BasketAsset.active == True)
        )).scalars().all()

        # Open positions (personal baskets — no BasketAsset entries)
        if not basket_assets:
            pos_pairs = (await session.execute(
                select(Position, Asset)
                .join(Asset, Asset.id == Position.asset_id)
                .where(Position.basket_id == basket.id, Position.quantity > 0)
            )).all()
        else:
            pos_pairs = []

        members_result = await session.execute(
            select(BasketMember, User)
            .join(User, BasketMember.user_id == User.id)
            .where(BasketMember.basket_id == basket.id)
        )
        sl_part = f" | Stop-loss: {basket.stop_loss_pct}%" if basket.stop_loss_pct else ""
        lines = [
            f"🗂 `{basket.name}`",
            f"Estrategia: `{basket.strategy}`{sl_part} | Perfil: {basket.risk_profile}",
            f"Cash: {basket.cash:.2f}€",
            "\n*Assets:*",
        ]
        if basket_assets:
            for a in basket_assets:
                lines.append(f"  • {a.ticker} ({a.market})")
        elif pos_pairs:
            for pos, asset in pos_pairs:
                lines.append(f"  • {asset.ticker} ({pos.quantity:.4f} acc @ {pos.avg_price:.2f})")
        else:
            lines.append("  Sin posiciones abiertas")
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
            select(Basket).where(Basket.name_normalized == normalize_basket_name(basket_name), Basket.active == True)
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
        CommandHandler("cesta", cmd_cesta),
        CommandHandler("sel", cmd_sel),
    ]
