import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Basket, Position, Asset, Order
from src.data.yahoo import YahooDataProvider
from src.portfolio.engine import PortfolioEngine

logger = logging.getLogger(__name__)
_provider = YahooDataProvider()
_engine = PortfolioEngine(_provider)


def _fmt(val, decimals=2) -> str:
    return f"{val:,.{decimals}f}"


def _arrow(pnl) -> str:
    return "📈" if pnl >= 0 else "📉"


async def cmd_valoracion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(Basket).where(Basket.active == True))
        baskets = result.scalars().all()
        if not baskets:
            await update.message.reply_text("No hay cestas configuradas.")
            return
        if context.args:
            name_filter = " ".join(context.args).lower()
            baskets = [b for b in baskets if name_filter in b.name.lower()]

        for basket in baskets:
            msg = await update.message.reply_text(f"⏳ Calculando {basket.name}...")
            try:
                val = await _engine.get_valuation(session, basket.id)
                tickers = ",".join(p.ticker for p in val.positions)
                finviz_url = f"https://finviz.com/screener.ashx?v=111&t={tickers}" if tickers else ""
                yahoo_url = f"https://finance.yahoo.com/quotes/{tickers}/" if tickers else ""
                sign = lambda v: "+" if v >= 0 else ""
                activos_value = val.total_value - val.cash
                lines = [
                    f"📊 `{val.basket_name}` — {datetime.now().strftime('%d %b %Y %H:%M')}",
                    "",
                    f"💼 Coste a tipo actual: {_fmt(val.total_invested)}€",
                    f"💵 Cash disponible:     {_fmt(val.cash)}€",
                    f"💰 Valor actual:        {_fmt(val.total_value)}€  ({_fmt(activos_value)}€ + {_fmt(val.cash)}€ cash)",
                    f"{_arrow(val.total_pnl)} P&L total: {sign(val.total_pnl)}{_fmt(val.total_pnl)}€ ({sign(val.total_pnl_pct)}{_fmt(val.total_pnl_pct)}%)",
                    "", "─" * 33,
                ]
                for p in val.positions:
                    sym = p.currency if p.currency != "EUR" else "€"
                    lines.append(
                        f"{p.ticker:<8} {_fmt(p.quantity, 0)} × {sym}{_fmt(p.current_price)} = {_fmt(p.market_value)}€  {_arrow(p.pnl)} {sign(p.pnl_pct)}{_fmt(p.pnl_pct)}%"
                    )
                lines += ["─" * 33]
                if finviz_url:
                    lines.append(f"\n🔍 [Finviz]({finviz_url})  |  [Yahoo Finance]({yahoo_url})")
                await msg.edit_text("\n".join(lines), parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Valuation error basket {basket.id}: {e}")
                await msg.edit_text(f"❌ Error calculando {basket.name}: {e}")


async def cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(Basket).where(Basket.active == True))
        for basket in result.scalars().all():
            rows = (await session.execute(
                select(Order, Asset).join(Asset, Order.asset_id == Asset.id)
                .where(Order.basket_id == basket.id)
                .order_by(Order.created_at.desc()).limit(10)
            )).all()
            if not rows:
                await update.message.reply_text(f"`{basket.name}`: sin órdenes.", parse_mode="Markdown")
                continue
            lines = [f"📋 `{basket.name}` — Últimas 10 órdenes\n"]
            for order, asset in rows:
                icon = "🟢" if order.type == "BUY" else "🔴"
                dt = order.created_at.strftime("%d/%m %H:%M")
                lines.append(f"{icon} {dt} {order.type} {_fmt(order.quantity, 2)} {asset.ticker} @ {_fmt(order.price)}")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def get_handlers():
    return [
        CommandHandler("valoracion", cmd_valoracion),
        CommandHandler("historial", cmd_historial),
    ]
