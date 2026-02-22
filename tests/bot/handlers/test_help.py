import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram.ext import CommandHandler, MessageHandler

from src.bot.handlers.help import _build_help_text, get_handlers


def test_build_help_text_contains_key_commands():
    text = _build_help_text()
    for cmd in ["/start", "/valoracion", "/cartera", "/historial",
                "/compra", "/vende", "/cestas", "/cesta", "/analiza",
                "/buscar", "/backtest", "/montecarlo", "/sizing",
                "/register", "/adduser", "/watchlist", "/addwatch", "/logs"]:
        assert cmd in text, f"{cmd} missing from help text"


def test_build_help_text_has_category_headers():
    text = _build_help_text()
    for header in ["Acceso", "Portfolio", "Órdenes", "Cestas",
                   "Análisis", "Estrategias", "Sizing", "Admin"]:
        assert header in text, f"Category '{header}' missing from help text"


def test_get_handlers_returns_command_and_message_handler():
    handlers = get_handlers()
    types = [type(h).__name__ for h in handlers]
    assert "CommandHandler" in types
    assert "MessageHandler" in types


@pytest.mark.asyncio
async def test_cmd_help_sends_help_text():
    from src.bot.handlers.help import cmd_help
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    await cmd_help(update, context)
    update.message.reply_text.assert_called_once()
    call_kwargs = update.message.reply_text.call_args
    text = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("text", "")
    assert "/valoracion" in text
    assert call_kwargs[1].get("parse_mode") == "Markdown"


@pytest.mark.asyncio
async def test_cmd_unknown_shows_command_name_and_help():
    from src.bot.handlers.help import cmd_unknown
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.text = "/hazme_rico"
    context = MagicMock()
    await cmd_unknown(update, context)
    update.message.reply_text.assert_called_once()
    call_kwargs = update.message.reply_text.call_args
    text = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("text", "")
    assert "no reconocido" in text
    assert "hazme_rico" in text
    assert "/valoracion" in text


@pytest.mark.asyncio
async def test_cmd_unknown_strips_botname_suffix():
    from src.bot.handlers.help import cmd_unknown
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.text = "/hazme_rico@ScroogeBotProd"
    context = MagicMock()
    await cmd_unknown(update, context)
    call_kwargs = update.message.reply_text.call_args
    text = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("text", "")
    assert "@ScroogeBotProd" not in text.split("\n")[0]  # suffix stripped from first line
    assert "hazme_rico" in text
