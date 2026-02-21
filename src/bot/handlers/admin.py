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
