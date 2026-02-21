"""Audit logger for write commands.

Persists a row to command_logs for every command that mutates state.
Failures are silently swallowed and logged via loguru — audit should
never break the main flow.
"""
import logging

from telegram import Update

from src.db.base import async_session_factory
from src.db.models import CommandLog

logger = logging.getLogger(__name__)


async def log_command(
    update: Update,
    command: str,
    success: bool,
    message: str = "",
    args: str | None = None,
) -> None:
    """Write one audit row to command_logs.

    Args:
        update:  Telegram Update object (provides tg_id / username).
        command: Command name, e.g. "/compra".
        success: True if the command completed without error.
        message: Human-readable outcome (confirmation text or error).
        args:    Raw argument string, e.g. "AAPL 3".
    """
    tg_user = update.effective_user
    try:
        async with async_session_factory() as session:
            session.add(CommandLog(
                tg_id=tg_user.id,
                username=tg_user.username,
                command=command,
                args=args,
                success=success,
                message=message,
            ))
            await session.commit()
    except Exception as exc:
        logger.error(f"audit.log_command failed: {exc}")
