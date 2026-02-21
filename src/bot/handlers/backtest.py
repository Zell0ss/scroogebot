import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Basket, BasketAsset, Asset
from src.backtest.engine import BacktestEngine
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy
from src.strategies.rsi import RSIStrategy
from src.strategies.bollinger import BollingerStrategy
from src.strategies.safe_haven import SafeHavenStrategy

logger = logging.getLogger(__name__)

sign = lambda v: "+" if v >= 0 else ""

VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y"}

STRATEGY_MAP = {
    "stop_loss": StopLossStrategy,
    "ma_crossover": MACrossoverStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerStrategy,
    "safe_haven": SafeHavenStrategy,
}


async def cmd_backtest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /backtest [period]  e.g. /backtest 1y"""
    period = "1y"
    if context.args and context.args[-1] in VALID_PERIODS:
        period = context.args[-1]

    msg = await update.message.reply_text(f"⏳ Backtesting ({period})... puede tardar un momento.")
    engine = BacktestEngine()

    async with async_session_factory() as session:
        result = await session.execute(select(Basket).where(Basket.active == True))
        baskets = result.scalars().all()

        for basket in baskets:
            strategy_cls = STRATEGY_MAP.get(basket.strategy)
            if not strategy_cls:
                await update.message.reply_text(
                    f"*{basket.name}*: estrategia `{basket.strategy}` no soporta backtest aún.",
                    parse_mode="Markdown",
                )
                continue

            strategy = strategy_cls()
            assets_result = await session.execute(
                select(Asset)
                .join(BasketAsset, BasketAsset.asset_id == Asset.id)
                .where(BasketAsset.basket_id == basket.id, BasketAsset.active == True)
            )
            assets = assets_result.scalars().all()

            if not assets:
                await update.message.reply_text(
                    f"*{basket.name}*: sin activos activos.", parse_mode="Markdown"
                )
                continue

            lines = [f"📊 *Backtest: {basket.name}* ({period})\n"]
            for asset in assets:
                try:
                    loop = asyncio.get_event_loop()
                    r = await loop.run_in_executor(
                        None, engine.run, asset.ticker, strategy, basket.strategy, period
                    )
                    alpha = r.total_return_pct - r.benchmark_return_pct
                    lines += [
                        f"*{asset.ticker}*",
                        f"  Rentabilidad: {sign(r.total_return_pct)}{r.total_return_pct:.1f}%  (B&H: {sign(r.benchmark_return_pct)}{r.benchmark_return_pct:.1f}%,  α: {sign(alpha)}{alpha:.1f}%)",
                        f"  Sharpe: {r.sharpe_ratio:.2f}  |  Max DD: {r.max_drawdown_pct:.1f}%",
                        f"  Operaciones: {r.n_trades}  |  Win rate: {r.win_rate_pct:.0f}%",
                        "",
                    ]
                except Exception as e:
                    logger.error(f"Backtest error {asset.ticker}: {e}")
                    lines.append(f"❌ {asset.ticker}: {e}\n")

            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    await msg.delete()


def get_handlers():
    return [CommandHandler("backtest", cmd_backtest)]
