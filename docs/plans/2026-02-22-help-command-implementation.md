# /help Command + Unknown Command Fallback — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `/help` command that lists all bot commands with descriptions, and show the same help when the user sends an unrecognized command.

**Architecture:** New `src/bot/handlers/help.py` holds a `COMMAND_LIST` constant, a text builder, and two handlers (`cmd_help`, `cmd_unknown`). It is registered **last** in `bot.py` so the `MessageHandler(filters.COMMAND, ...)` fallback only fires when no other handler matched.

**Tech Stack:** python-telegram-bot v20+ (`CommandHandler`, `MessageHandler`, `filters.COMMAND`), pytest + AsyncMock for tests.

---

### Task 1: Write and verify the `help.py` handler

**Files:**
- Create: `src/bot/handlers/help.py`
- Create: `tests/bot/handlers/test_help.py`

---

**Step 1: Write the failing tests**

Create `tests/bot/handlers/test_help.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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
    assert "hazme_rico" in text or "no reconocido" in text
    assert "/valoracion" in text
```

**Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/bot/handlers/test_help.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `help.py` doesn't exist yet.

---

**Step 3: Create `src/bot/handlers/help.py`**

```python
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters

# (command, args_hint, description)
# Use "" for args_hint when command takes no arguments.
COMMAND_LIST = [
    # --- Acceso ---
    ("__header__", "", "🔑 *Acceso*"),
    ("start", "", "Registrarse y ver bienvenida"),

    # --- Portfolio ---
    ("__header__", "", "💼 *Portfolio*"),
    ("valoracion", "[nombre\\_cesta]", "Valor actual de las cestas"),
    ("cartera", "", "Posiciones abiertas"),
    ("historial", "", "Últimas 10 órdenes por cesta"),

    # --- Órdenes ---
    ("__header__", "", "📈 *Órdenes*"),
    ("compra", "TICKER cantidad", "Comprar acciones (paper trading)"),
    ("vende", "TICKER cantidad", "Vender acciones (paper trading)"),

    # --- Cestas ---
    ("__header__", "", "🗂 *Cestas*"),
    ("cestas", "", "Listar cestas disponibles"),
    ("cesta", "nombre", "Detalle de una cesta"),

    # --- Análisis ---
    ("__header__", "", "🔍 *Análisis*"),
    ("analiza", "TICKER", "RSI, SMA y tendencia"),
    ("buscar", "nombre|ticker", "Buscar activos en cestas y Yahoo Finance"),

    # --- Estrategias ---
    ("__header__", "", "📊 *Estrategias*"),
    ("backtest", "[periodo]", "Backtest de estrategia (1mo/3mo/6mo/1y/2y)"),
    ("montecarlo", "CESTA [sims] [dias]", "Simulación Monte Carlo"),

    # --- Sizing ---
    ("__header__", "", "📐 *Sizing*"),
    ("sizing", "TICKER [stop\\_loss]", "Position sizing con comisiones del broker"),

    # --- Admin ---
    ("__header__", "", "🛠 *Admin*"),
    ("register", "tg\\_id username", "Pre-registrar usuario (OWNER)"),
    ("adduser", "@user ROL cesta", "Añadir usuario a cesta (OWNER)"),
    ("watchlist", "", "Ver tu watchlist personal"),
    ("addwatch", "TICKER Nombre | nota", "Añadir ticker a watchlist"),
    ("logs", "[N]", "Ver últimos N comandos ejecutados (OWNER)"),
]


def _build_help_text() -> str:
    lines = ["🦆 *TioGilito — Comandos disponibles*", ""]
    for cmd, args, desc in COMMAND_LIST:
        if cmd == "__header__":
            lines += ["", desc]
        elif args:
            lines.append(f"`/{cmd} {args}` — {desc}")
        else:
            lines.append(f"`/{cmd}` — {desc}")
    return "\n".join(lines)


_HELP_TEXT = _build_help_text()


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(_HELP_TEXT, parse_mode="Markdown")


async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = update.message.text or ""
    cmd = raw.split()[0] if raw else "desconocido"
    await update.message.reply_text(
        f"❓ Comando no reconocido: `{cmd}`\n\n{_HELP_TEXT}",
        parse_mode="Markdown",
    )


def get_handlers():
    return [
        CommandHandler("help", cmd_help),
        MessageHandler(filters.COMMAND, cmd_unknown),
    ]
```

**Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/bot/handlers/test_help.py -v
```

Expected: all 5 tests PASS.

**Step 5: Commit**

```bash
git add src/bot/handlers/help.py tests/bot/handlers/test_help.py
git commit -m "feat: /help command and unknown command fallback handler"
```

---

### Task 2: Register help handlers in bot.py

**Files:**
- Modify: `src/bot/bot.py`

---

**Step 1: Add import at top of bot.py**

In `src/bot/bot.py`, after the existing handler imports (around line 18), add:

```python
from src.bot.handlers.help import get_handlers as help_handlers
```

**Step 2: Register handlers last in `run()`**

In the `run()` function (around line 145, after all existing `add_handler` loops), add this block as the **very last** handler registration — before the `CallbackQueryHandler` line:

```python
    for handler in help_handlers():
        app.add_handler(handler)
```

The final registration block should look like:

```python
    for handler in portfolio_handlers():
        app.add_handler(handler)
    for handler in order_handlers():
        app.add_handler(handler)
    for handler in basket_handlers():
        app.add_handler(handler)
    for handler in analysis_handlers():
        app.add_handler(handler)
    for handler in admin_handlers():
        app.add_handler(handler)
    for handler in backtest_handlers():
        app.add_handler(handler)
    for handler in sizing_handlers():
        app.add_handler(handler)
    for handler in search_handlers():
        app.add_handler(handler)
    for handler in help_handlers():          # ← LAST: fallback catches unknown commands
        app.add_handler(handler)

    app.add_handler(CallbackQueryHandler(handle_alert_callback, pattern="^alert:"))
```

**Step 3: Run the full test suite**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all existing tests still pass, plus the 5 new help tests.

**Step 4: Commit**

```bash
git add src/bot/bot.py
git commit -m "feat: register /help and unknown-command fallback in bot"
```
