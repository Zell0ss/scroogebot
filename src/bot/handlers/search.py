import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select, or_

from src.db.base import async_session_factory
from src.db.models import Asset, Basket, BasketAsset
from src.data.models import SearchResult
from src.data.yahoo import YahooDataProvider

logger = logging.getLogger(__name__)
_provider = YahooDataProvider()

MAX_RESULTS = 8
MIN_LOCAL_BEFORE_YAHOO = 3
MIN_QUERY_LEN = 2


def _format_results(query: str, local: list[SearchResult], yahoo: list[SearchResult]) -> str:
    if not local and not yahoo:
        return f'❌ Sin resultados para "{query}". Prueba con otro nombre o ticker.'

    lines = [f'🔍 *"{query}"*', ""]

    if local:
        lines.append("📌 *En tus cestas:*")
        for r in local:
            lines.append(f"  {r.ticker} — {r.name} ({r.exchange} · {r.type}) [{r.basket_name}]")

    if yahoo:
        if local:
            lines.append("")
        lines.append("🌐 *Yahoo Finance:*")
        for r in yahoo:
            lines.append(f"  {r.ticker} — {r.name} ({r.exchange} · {r.type})")

    # Suggest actions using the first local ticker, or first yahoo ticker
    first = local[0] if local else yahoo[0]
    lines += [
        "",
        f"▶ `/analiza {first.ticker}` · `/sizing {first.ticker}` · `/compra {first.ticker} 10`",
    ]
    return "\n".join(lines)


async def cmd_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /buscar <nombre o ticker>\nEjemplo: /buscar banco santander")
        return

    query = " ".join(context.args).strip()
    if len(query) < MIN_QUERY_LEN:
        await update.message.reply_text("La búsqueda debe tener al menos 2 caracteres.")
        return

    # 1. Local DB search
    async with async_session_factory() as session:
        rows = (await session.execute(
            select(Asset, Basket)
            .join(BasketAsset, BasketAsset.asset_id == Asset.id)
            .join(Basket, BasketAsset.basket_id == Basket.id)
            .where(
                or_(
                    Asset.name.ilike(f"%{query}%"),
                    Asset.ticker.ilike(f"%{query}%"),
                ),
                Basket.active == True,
                BasketAsset.active == True,
            )
        )).all()

    local: list[SearchResult] = [
        SearchResult(
            ticker=asset.ticker,
            name=asset.name or asset.ticker,
            exchange=asset.market or "",
            type="Equity",
            in_basket=True,
            basket_name=basket.name,
        )
        for asset, basket in rows
    ]

    # 2. Yahoo fallback if local results are few
    yahoo: list[SearchResult] = []
    if len(local) < MIN_LOCAL_BEFORE_YAHOO:
        local_tickers = {r.ticker for r in local}
        remaining = MAX_RESULTS - len(local)
        all_yahoo = _provider.search_yahoo(query, max_results=MAX_RESULTS)
        yahoo = [r for r in all_yahoo if r.ticker not in local_tickers][:remaining]

    await update.message.reply_text(
        _format_results(query, local, yahoo),
        parse_mode="Markdown",
    )


def get_handlers():
    return [CommandHandler("buscar", cmd_buscar)]
