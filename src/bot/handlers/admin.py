import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from sqlalchemy import desc
from src.db.models import User, Basket, BasketMember, CommandLog, Watchlist
from src.bot.audit import log_command

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
    reply = (
        f"¡Hola {tg_user.first_name}! 🦆 Soy TioGilito.\n"
        "Usa /valoracion para ver el estado de tus cestas.\n"
        "Usa /cestas para ver las cestas disponibles."
    )
    await update.message.reply_text(reply)
    await log_command(update, "/start", True, "User registered or already exists")


async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /adduser @username OWNER|MEMBER basket name"""
    raw_args = " ".join(context.args) if context.args else ""

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
            err = f"Cesta '{basket_name}' no encontrada."
            await update.message.reply_text(err)
            await log_command(update, "/adduser", False, err, raw_args)
            return

        caller_result = await session.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        caller = caller_result.scalar_one_or_none()
        if not caller:
            await update.message.reply_text("Usa /start primero.")
            return

        owner_check = await session.execute(
            select(BasketMember).where(
                BasketMember.basket_id == basket.id,
                BasketMember.user_id == caller.id,
                BasketMember.role == "OWNER",
            )
        )
        if not owner_check.scalar_one_or_none():
            err = "Solo el OWNER puede añadir usuarios."
            await update.message.reply_text(err)
            await log_command(update, "/adduser", False, err, raw_args)
            return

        target_result = await session.execute(
            select(User).where(User.username == username)
        )
        target = target_result.scalar_one_or_none()
        if not target:
            err = f"@{username} no encontrado. El usuario debe enviar /start primero."
            await update.message.reply_text(err)
            await log_command(update, "/adduser", False, err, raw_args)
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
        ok_msg = f"@{username} → {role} en '{basket_name}'"
        await update.message.reply_text(f"✅ {ok_msg}.")
        await log_command(update, "/adduser", True, ok_msg, raw_args)


async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session_factory() as session:
        user_result = await session.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            await update.message.reply_text("Usa /start primero.")
            return
        result = await session.execute(
            select(Watchlist)
            .where(Watchlist.added_by == user.id)
            .order_by(Watchlist.created_at.desc())
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
    raw_args = " ".join(context.args) if context.args else ""

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
    ok_msg = f"{ticker} añadido a watchlist"
    await update.message.reply_text(f"✅ {ticker} añadido a watchlist.")
    await log_command(update, "/addwatch", True, ok_msg, raw_args)


async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /logs [N] — last N command_logs entries (OWNER of any basket only)."""
    n = 20
    if context.args and context.args[0].isdigit():
        n = min(int(context.args[0]), 50)

    async with async_session_factory() as session:
        caller_result = await session.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        caller = caller_result.scalar_one_or_none()
        if not caller:
            await update.message.reply_text("Usa /start primero.")
            return

        owner_check = await session.execute(
            select(BasketMember).where(
                BasketMember.user_id == caller.id,
                BasketMember.role == "OWNER",
            )
        )
        if not owner_check.scalar_one_or_none():
            await update.message.reply_text("Solo los OWNER pueden ver los logs.")
            return

        result = await session.execute(
            select(CommandLog)
            .order_by(desc(CommandLog.created_at))
            .limit(n)
        )
        logs = result.scalars().all()

    if not logs:
        await update.message.reply_text("No hay registros aún.")
        return

    lines = [f"📋 *Últimos {len(logs)} comandos*\n"]
    for entry in logs:
        status = "✅" if entry.success else "❌"
        user = f"@{entry.username}" if entry.username else f"id:{entry.tg_id}"
        ts = entry.created_at.strftime("%d/%m %H:%M") if entry.created_at else "—"
        lines.append(f"{status} `{ts}` {user} — `{entry.command}`")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def get_handlers():
    return [
        CommandHandler("start", cmd_start),
        CommandHandler("adduser", cmd_adduser),
        CommandHandler("watchlist", cmd_watchlist),
        CommandHandler("addwatch", cmd_addwatch),
        CommandHandler("logs", cmd_logs),
    ]
