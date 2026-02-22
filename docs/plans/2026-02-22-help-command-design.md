# Design: /help command + unknown command fallback

**Date:** 2026-02-22
**Status:** Approved

## Problem

The bot has no `/help` command and silently ignores unknown commands like `/garbage` or `/hazme_rico`. Users have no discoverable reference for available commands.

## Solution

Add a dedicated `help.py` handler that:
1. Serves `/help` with a categorized list of all commands
2. Catches any unrecognized command and shows the same help text with a "command not found" prefix

## Files Changed

| File | Change |
|---|---|
| `src/bot/handlers/help.py` | New — `COMMAND_LIST`, `cmd_help`, `cmd_unknown`, `get_handlers()` |
| `src/bot/bot.py` | Register help handlers **last** (after all other handlers) |

## Implementation Details

### `help.py`

**`COMMAND_LIST`** — list of `(command, args_hint, description)` tuples, grouped by category headers. Includes `/montecarlo` (documented, not yet registered).

**`_build_help_text()`** — renders the list into Markdown with category emoji headers.

**`cmd_help`** — `CommandHandler("help", ...)` → sends help text.

**`cmd_unknown`** — `MessageHandler(filters.COMMAND, ...)` → replies with
`"❓ Comando no reconocido: /xyz\n\n" + help_text`

**`get_handlers()`** — returns `[CommandHandler("help", cmd_help), MessageHandler(filters.COMMAND, cmd_unknown)]`

### `bot.py` registration order (critical)

```python
# ... all existing handlers ...
for handler in help_handlers():   # ← LAST
    app.add_handler(handler)
```

The `MessageHandler(filters.COMMAND, ...)` must be registered after all `CommandHandler`s so it only fires when no specific command matched.

## Help Message Structure

```
🦆 *TioGilito — Comandos disponibles*

🔑 *Acceso*
/start — Registrarse y ver bienvenida

💼 *Portfolio*
/valoracion — Valor actual de las cestas
/cartera — Posiciones abiertas
/historial — Últimas 10 órdenes por cesta

📈 *Órdenes*
/compra TICKER cantidad — Comprar (paper trading)
/vende TICKER cantidad — Vender (paper trading)

🗂 *Cestas*
/cestas — Listar cestas disponibles
/cesta nombre — Detalle de una cesta

🔍 *Análisis*
/analiza TICKER — RSI, SMA y tendencia
/buscar nombre|ticker — Buscar activos

📊 *Estrategias*
/backtest [periodo] — Backtest (1mo/3mo/6mo/1y/2y)
/montecarlo CESTA [sims] [dias] — Simulación Monte Carlo

📐 *Sizing*
/sizing TICKER [stop] — Position sizing con comisiones

🛠 *Admin*
/register tg_id username — Pre-registrar usuario
/adduser @user ROL cesta — Añadir a cesta
/watchlist — Ver watchlist personal
/addwatch TICKER Nombre|nota — Añadir a watchlist
/logs [N] — Ver últimos N comandos (OWNER)
```

## Out of Scope

- Role-based help (admin-only section hidden from regular users)
- Registering `/montecarlo` in bot.py (handled separately)
