import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Basket, BasketAsset, Asset, User
from src.sizing.broker import BROKER_REGISTRY, Broker
from src.sizing.engine import calculate_sizing, CAPITAL_TOTAL
from src.sizing.models import SizingResult

logger = logging.getLogger(__name__)

_FALLBACK_BROKER = BROKER_REGISTRY["paper"]


def _fmt(val: float, decimals: int = 2) -> str:
    return f"{val:,.{decimals}f}"


def _volatilidad(atr: float, precio: float) -> str:
    pct = atr / precio * 100 if precio else 0
    if pct < 1.5:
        return "baja"
    if pct < 3.0:
        return "media"
    return "alta"


def _format_result(r: SizingResult, basket_name: str | None = None) -> str:
    if basket_name:
        header = (
            f"🗂 `{basket_name}` · Capital: €{_fmt(r.capital_total)}\n"
        )
    else:
        header = f"⚠️ Sin cesta activa — capital de referencia: €{_fmt(r.capital_total)}\n"

    lines = [
        f"📊 *Position Sizing — {r.company_name} ({r.ticker})*",
        header,
        f"Precio actual:      €{_fmt(r.precio)}",
        f"Stop loss:          €{_fmt(r.stop_loss)}  ({r.stop_tipo})",
    ]
    if r.atr is not None:
        lines.append(
            f"  └─ ATR(14):       €{_fmt(r.atr)}  |  Volatilidad {_volatilidad(r.atr, r.precio)}"
        )
    lines += [
        f"Distancia al stop:  €{_fmt(r.distancia)} (-{_fmt(r.distancia_pct)}%)",
        "",
        f"Acciones:           {r.acciones}  (limitado por {r.factor_limite})",
        f"Posición nominal:   €{_fmt(r.nominal)} ({_fmt(r.pct_cartera)}% de cartera)",
        f"Riesgo máximo:      €{_fmt(r.riesgo_maximo)} ({_fmt(r.riesgo_maximo / r.capital_total * 100)}%)",
        "",
        f"Comisiones ({r.broker_nombre}): €{_fmt(r.com_compra)} compra + €{_fmt(r.com_venta)} venta",
        f"Riesgo real:        €{_fmt(r.riesgo_real)}",
    ]
    if r.aviso:
        lines += ["", r.aviso]
    else:
        lines += ["", "✅ Stop dentro del rango recomendado"]
    return "\n".join(lines)


async def cmd_sizing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Uso: /sizing TICKER [STOP_LOSS [CAPITAL]]\n"
            "Ejemplo: /sizing SAN.MC\n"
            "Ejemplo: /sizing SAN.MC 3.85\n"
            "Ejemplo: /sizing SAN.MC 3.85 8000"
        )
        return

    ticker = context.args[0].upper()
    stop_manual = None
    capital_manual = None

    if len(context.args) >= 2:
        try:
            stop_manual = float(context.args[1])
        except ValueError:
            await update.message.reply_text(
                "Stop loss debe ser un número. Ej: /sizing SAN.MC 3.85"
            )
            return

    if len(context.args) >= 3:
        try:
            capital_manual = float(context.args[2])
        except ValueError:
            await update.message.reply_text(
                "Capital debe ser un número. Ej: /sizing SAN.MC 3.85 8000"
            )
            return

    # Look up baskets containing this ticker (for broker resolution)
    async with async_session_factory() as session:
        rows = (await session.execute(
            select(Basket, Asset)
            .join(BasketAsset, BasketAsset.basket_id == Basket.id)
            .join(Asset, BasketAsset.asset_id == Asset.id)
            .where(Asset.ticker == ticker, Basket.active == True, BasketAsset.active == True)
        )).all()

        # Resolve user's active basket for capital
        basket_name: str | None = None
        capital_total: float = capital_manual or CAPITAL_TOTAL

        if capital_manual is None:
            user_result = await session.execute(
                select(User).where(User.tg_id == update.effective_user.id)
            )
            user = user_result.scalar_one_or_none()
            if user and user.active_basket_id:
                basket_result = await session.execute(
                    select(Basket).where(
                        Basket.id == user.active_basket_id,
                        Basket.active == True,
                    )
                )
                active_basket = basket_result.scalar_one_or_none()
                if active_basket:
                    basket_name = active_basket.name
                    capital_total = float(active_basket.cash)

    brokers_to_use: list[tuple[str, Broker]] = []
    if rows:
        seen: set[str] = set()
        for basket, asset in rows:
            if basket.broker not in seen:
                seen.add(basket.broker)
                broker = BROKER_REGISTRY.get(basket.broker, _FALLBACK_BROKER)
                label = f"{basket.name} ({basket.broker})"
                brokers_to_use.append((label, broker))
    else:
        brokers_to_use = [("paper (fallback)", _FALLBACK_BROKER)]

    msg = await update.message.reply_text(f"⏳ Calculando sizing para {ticker}...")

    results = []
    for label, broker in brokers_to_use:
        try:
            r = calculate_sizing(ticker, stop_manual, broker, capital_total=capital_total)
            results.append(_format_result(r, basket_name=basket_name))
        except Exception as e:
            logger.error(f"Sizing error {ticker} broker {label}: {e}")
            results.append(f"❌ Error calculando sizing para {ticker}: {e}")

    await msg.edit_text("\n\n---\n\n".join(results), parse_mode="Markdown")


def get_handlers():
    return [CommandHandler("sizing", cmd_sizing)]
