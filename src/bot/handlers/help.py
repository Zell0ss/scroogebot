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
