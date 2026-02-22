import asyncio
import logging
import math
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Basket, BasketAsset, Asset, User, Position
from src.backtest.engine import BacktestEngine
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy
from src.strategies.rsi import RSIStrategy
from src.strategies.bollinger import BollingerStrategy
from src.strategies.safe_haven import SafeHavenStrategy

logger = logging.getLogger(__name__)

sign = lambda v: "+" if v >= 0 else ""


def _fp(val: float, decimals: int = 1) -> str:
    """Format percentage safely — returns 'N/A' for NaN or infinite values."""
    if not math.isfinite(val):
        return "N/A"
    s = "+" if val >= 0 else ""
    return f"{s}{val:.{decimals}f}%"


def _ff(val: float, decimals: int = 2) -> str:
    """Format float safely — returns 'N/A' for NaN or infinite values."""
    if not math.isfinite(val):
        return "N/A"
    return f"{val:.{decimals}f}"

VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y"}

STRATEGY_MAP = {
    "stop_loss": StopLossStrategy,
    "ma_crossover": MACrossoverStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerStrategy,
    "safe_haven": SafeHavenStrategy,
}


def _parse_args(args: list[str]) -> tuple[str | None, str]:
    """Parse optional basket name and optional period.

    Period is the last arg if it matches VALID_PERIODS (case-insensitive).
    Everything before it is the basket name (may be empty → use active basket).
    """
    parts = list(args)
    period = "1y"
    if parts and parts[-1].lower() in VALID_PERIODS:
        period = parts[-1].lower()
        parts = parts[:-1]
    basket_name = " ".join(parts) if parts else None
    return basket_name, period


async def cmd_backtest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /backtest [CESTA] [period]  e.g. /backtest CestaAgresiva 1y"""
    basket_name_arg, period = _parse_args(list(context.args) if context.args else [])

    async with async_session_factory() as session:
        basket = None

        if basket_name_arg:
            result = await session.execute(
                select(Basket).where(Basket.name == basket_name_arg, Basket.active == True)
            )
            basket = result.scalar_one_or_none()
            if not basket:
                await update.message.reply_text(
                    f"Cesta '{basket_name_arg}' no encontrada."
                )
                return
        else:
            # Resolve user's active basket
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
                basket = basket_result.scalar_one_or_none()

            if not basket:
                await update.message.reply_text(
                    "No tienes cesta activa. Usa /sel para seleccionar una o "
                    "indica el nombre: /backtest Mi_Cesta 1y"
                )
                return

        strategy_cls = STRATEGY_MAP.get(basket.strategy)
        if not strategy_cls:
            await update.message.reply_text(
                f"`{basket.name}`: estrategia `{basket.strategy}` no soporta backtest aún.",
                parse_mode="Markdown",
            )
            return

        strategy = strategy_cls()
        assets_result = await session.execute(
            select(Asset)
            .join(BasketAsset, BasketAsset.asset_id == Asset.id)
            .where(BasketAsset.basket_id == basket.id, BasketAsset.active == True)
        )
        assets = assets_result.scalars().all()

        if not assets:
            # Fall back to currently held positions (personal baskets)
            pos_result = await session.execute(
                select(Asset)
                .join(Position, Position.asset_id == Asset.id)
                .where(Position.basket_id == basket.id, Position.quantity > 0)
                .distinct()
            )
            assets = pos_result.scalars().all()

        if not assets:
            await update.message.reply_text(
                f"`{basket.name}`: sin activos para hacer backtest.\n"
                "Compra algún activo con /compra o usa una cesta modelo.",
                parse_mode="Markdown",
            )
            return

        msg = await update.message.reply_text(
            f"⏳ Backtesting `{basket.name}` ({period})...",
            parse_mode="Markdown",
        )
        engine = BacktestEngine()

        lines = [f"📊 *Backtest:* `{basket.name}` ({period})\n   Estrategia: `{basket.strategy}`\n"]
        for asset in assets:
            try:
                loop = asyncio.get_event_loop()
                sl_pct = float(basket.stop_loss_pct) if basket.stop_loss_pct else None
                r = await loop.run_in_executor(
                    None, engine.run, asset.ticker, strategy, basket.strategy, period, sl_pct
                )
                alpha = r.total_return_pct - r.benchmark_return_pct
                lines += [
                    f"*{asset.ticker}*",
                    f"  Rentabilidad: {_fp(r.total_return_pct)}  (B&H: {_fp(r.benchmark_return_pct)},  α: {_fp(alpha)})",
                    f"  Sharpe: {_ff(r.sharpe_ratio)}  |  Max DD: {_fp(-r.max_drawdown_pct)}",
                    f"  Operaciones: {r.n_trades}  |  Win rate: {_fp(r.win_rate_pct, 0)}",
                    "",
                ]
            except Exception as e:
                logger.error(f"Backtest error {asset.ticker}: {e}")
                lines.append(f"❌ {asset.ticker}: {e}\n")

        await msg.edit_text("\n".join(lines), parse_mode="Markdown")


def get_handlers():
    return [CommandHandler("backtest", cmd_backtest)]
