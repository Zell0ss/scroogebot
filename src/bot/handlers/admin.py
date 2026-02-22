import logging
from decimal import Decimal
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from sqlalchemy import desc
from src.db.models import User, Basket, BasketMember, CommandLog, Watchlist, Position
from src.bot.audit import log_command

STRATEGY_MAP = {
    "stop_loss": None,
    "ma_crossover": None,
    "rsi": None,
    "bollinger": None,
    "safe_haven": None,
}
_STRATEGY_LIST = ", ".join(STRATEGY_MAP.keys())

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    tg_user = update.effective_user
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_user.id))
        user = result.scalar_one_or_none()
        if not user:
            uname = f"@{tg_user.username}" if tg_user.username else "(sin username)"
            await update.message.reply_text(
                f"🔒 No estás registrado en el bot.\n\n"
                f"Pasa estos datos al administrador:\n"
                f"  ID: `{tg_user.id}`\n"
                f"  Usuario: `{uname}`",
                parse_mode="Markdown",
            )
            await log_command(update, "/start", False, "Unregistered user")
            return
        # Complete registration: fill in first_name/username from Telegram if missing
        if not user.first_name:
            user.first_name = tg_user.first_name
        if not user.username:
            user.username = tg_user.username
        await session.commit()
    await update.message.reply_text(
        f"¡Hola {tg_user.first_name}! 🦆 Soy TioGilito.\n"
        "Usa /valoracion para ver el estado de tus cestas.\n"
        "Usa /cestas para ver las cestas disponibles."
    )
    await log_command(update, "/start", True, "User welcomed")


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /register <tg_id> <username>  — pre-register a user (OWNER only)."""
    if not update.message:
        return
    raw_args = " ".join(context.args) if context.args else ""
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /register <tg_id> <username>")
        return

    try:
        new_tg_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("tg_id debe ser un número.")
        return
    new_username = context.args[1].lstrip("@")

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
            err = "Solo los OWNER pueden registrar usuarios."
            await update.message.reply_text(err)
            await log_command(update, "/register", False, err, raw_args)
            return

        existing = await session.execute(select(User).where(User.tg_id == new_tg_id))
        if existing.scalar_one_or_none():
            await update.message.reply_text(f"El usuario con ID `{new_tg_id}` ya está registrado.", parse_mode="Markdown")
            return

        session.add(User(tg_id=new_tg_id, username=new_username))
        await session.commit()

    ok_msg = f"@{new_username} (id:{new_tg_id}) pre-registrado. Debe enviar /start para completar el registro."
    await update.message.reply_text(f"✅ {ok_msg}")
    await log_command(update, "/register", True, ok_msg, raw_args)


async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /adduser @username OWNER|MEMBER basket name"""
    raw_args = " ".join(context.args) if context.args else ""

    if not update.message:
        return
    if len(context.args) < 3:
        await update.message.reply_text("Uso: /adduser @username OWNER|MEMBER nombre_cesta")
        return
    username = context.args[0].lstrip("@")
    # Accept role in position 1 (/adduser @u ROLE basket) or last (/adduser @u basket ROLE)
    if context.args[1].upper() in ("OWNER", "MEMBER"):
        role = context.args[1].upper()
        basket_name = " ".join(context.args[2:])
    elif context.args[-1].upper() in ("OWNER", "MEMBER"):
        role = context.args[-1].upper()
        basket_name = " ".join(context.args[1:-1])
    else:
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


async def cmd_estrategia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /estrategia <cesta> [nueva_estrategia]"""
    if not update.message or not context.args:
        await update.message.reply_text(
            f"Uso: /estrategia <cesta> [nueva\\_estrategia]\nDisponibles: {_STRATEGY_LIST}"
        )
        return

    parts = list(context.args)
    # If last token is a known strategy, it's a change request
    if parts[-1] in STRATEGY_MAP and len(parts) >= 2:
        new_strategy: str | None = parts.pop()
    elif parts[-1] not in STRATEGY_MAP and len(parts) >= 2:
        # Last token looks like an intended strategy but is invalid
        new_strategy = parts[-1]
        if new_strategy not in STRATEGY_MAP:
            await update.message.reply_text(
                f"Estrategia '{new_strategy}' no válida. Disponibles: {_STRATEGY_LIST}"
            )
            return
    else:
        new_strategy = None

    basket_name = " ".join(parts if new_strategy is not None else parts)

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

        if new_strategy is None:
            await update.message.reply_text(
                f"📊 *{basket_name}* usa estrategia: `{basket.strategy}`\n"
                f"Disponibles: {_STRATEGY_LIST}",
                parse_mode="Markdown",
            )
            return

        owner_check = await session.execute(
            select(BasketMember).where(
                BasketMember.basket_id == basket.id,
                BasketMember.user_id == caller.id,
                BasketMember.role == "OWNER",
            )
        )
        if not owner_check.scalar_one_or_none():
            await update.message.reply_text("Solo el OWNER puede cambiar la estrategia.")
            return

        basket.strategy = new_strategy
        await session.commit()
        await update.message.reply_text(
            f"✅ Estrategia de *{basket_name}* cambiada a `{new_strategy}`",
            parse_mode="Markdown",
        )


async def cmd_nuevacesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /nuevacesta <nombre> <estrategia>"""
    if not update.message or not context.args or len(context.args) < 2:
        await update.message.reply_text(
            f"Uso: /nuevacesta <nombre> <estrategia>\nDisponibles: {_STRATEGY_LIST}"
        )
        return

    strategy = context.args[-1]
    basket_name = " ".join(context.args[:-1])

    if strategy not in STRATEGY_MAP:
        await update.message.reply_text(
            f"Estrategia '{strategy}' no válida. Disponibles: {_STRATEGY_LIST}"
        )
        return

    async with async_session_factory() as session:
        caller_result = await session.execute(select(User).where(User.tg_id == update.effective_user.id))
        caller = caller_result.scalar_one_or_none()
        if not caller:
            await update.message.reply_text("Usa /start primero.")
            return

        dup_result = await session.execute(select(Basket).where(Basket.name == basket_name))
        if dup_result.scalar_one_or_none():
            await update.message.reply_text(f"Ya existe una cesta con el nombre '{basket_name}'.")
            return

        basket = Basket(name=basket_name, strategy=strategy, active=True, cash=Decimal("10000"))
        session.add(basket)
        await session.flush()
        session.add(BasketMember(basket_id=basket.id, user_id=caller.id, role="OWNER"))
        await session.commit()

    await update.message.reply_text(
        f'✅ Cesta "{basket_name}" creada con estrategia `{strategy}` y €10.000 de capital inicial. Eres OWNER.',
        parse_mode="Markdown",
    )


async def cmd_eliminarcesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /eliminarcesta <nombre>"""
    if not update.message or not context.args:
        await update.message.reply_text("Uso: /eliminarcesta <nombre>")
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
            await update.message.reply_text("Solo el OWNER puede eliminar una cesta.")
            return

        positions_result = await session.execute(
            select(Position).where(
                Position.basket_id == basket.id,
                Position.quantity > 0,
            )
        )
        open_positions = positions_result.scalars().all()
        if open_positions:
            tickers = ", ".join(p.ticker for p in open_positions)
            await update.message.reply_text(
                f"❌ No se puede eliminar: *{basket_name}* tiene posiciones abiertas ({tickers}).",
                parse_mode="Markdown",
            )
            return

        basket.active = False
        await session.commit()
        await update.message.reply_text(f"✅ Cesta \"{basket_name}\" desactivada.")


def get_handlers():
    return [
        CommandHandler("start", cmd_start),
        CommandHandler("register", cmd_register),
        CommandHandler("adduser", cmd_adduser),
        CommandHandler("watchlist", cmd_watchlist),
        CommandHandler("addwatch", cmd_addwatch),
        CommandHandler("logs", cmd_logs),
        CommandHandler("estrategia", cmd_estrategia),
        CommandHandler("nuevacesta", cmd_nuevacesta),
        CommandHandler("eliminarcesta", cmd_eliminarcesta),
    ]
