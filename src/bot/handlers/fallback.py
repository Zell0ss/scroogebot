"""Fallback handler for commands with accented characters.

Telegram only accepts [a-z0-9_] in command entities. When users type
e.g. /valoración it arrives as plain TEXT (not a COMMAND entity).
This handler normalises the text and dispatches to the real handler.
"""
import unicodedata

from telegram import Update
from telegram.ext import MessageHandler, filters

from src.bot.handlers.portfolio import cmd_valoracion


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


# Maps normalized command name → actual handler coroutine
_ACCENT_ALIASES: dict[str, object] = {
    "valoracion": cmd_valoracion,
}


async def _accent_fallback(update: Update, context) -> None:
    text = (update.message.text or "").strip()
    if not text.startswith("/"):
        return
    raw_cmd = text.split()[0][1:].split("@")[0]
    handler_fn = _ACCENT_ALIASES.get(_normalize(raw_cmd))
    if handler_fn:
        await handler_fn(update, context)


def get_handlers():
    return [
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r"^/"),
            _accent_fallback,
        )
    ]
