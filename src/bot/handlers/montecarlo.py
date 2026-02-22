import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Basket, BasketAsset, Asset
from src.data.yahoo import YahooDataProvider
from src.backtest.montecarlo import MonteCarloAnalyzer, AssetMonteCarloResult, _profile_line
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy
from src.strategies.rsi import RSIStrategy
from src.strategies.bollinger import BollingerStrategy
from src.strategies.safe_haven import SafeHavenStrategy

import numpy as np

logger = logging.getLogger(__name__)

STRATEGY_MAP = {
    "stop_loss": StopLossStrategy,
    "ma_crossover": MACrossoverStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerStrategy,
    "safe_haven": SafeHavenStrategy,
}

_sign = lambda v: "+" if v >= 0 else ""


def _parse_args(args: list[str]) -> tuple[str, int, int]:
    """Parse: trailing ints (in order) are N_SIMS then HORIZONTE. Rest is basket name."""
    parts = list(args)
    numerics: list[int] = []

    while parts and parts[-1].isdigit():
        numerics.insert(0, int(parts.pop()))

    n_sims = min(numerics[0], 500) if len(numerics) >= 1 else 100
    horizon = min(numerics[1], 365) if len(numerics) >= 2 else 90
    basket_name = " ".join(parts)
    return basket_name, n_sims, horizon


class MonteCarloFormatter:
    def format_header(
        self,
        basket_name: str,
        strategy: str,
        n_assets: int,
        n_sims: int,
        horizon: int,
        seed: int,
    ) -> str:
        return (
            f"🎲 *Monte Carlo — {basket_name}* "
            f"({n_sims} sims, {horizon} días, seed: {seed})\n"
            f"   Estrategia: `{strategy}` | Activos: {n_assets}\n"
        )

    def format_asset(self, r: AssetMonteCarloResult) -> str:
        s = _sign
        lines = [
            f"*{r.ticker}*",
            f"  Rentabilidad",
            f"    Mediana:          {s(r.return_median)}{r.return_median:.1f}%",
            f"    Rango 80%:        {s(r.return_p10)}{r.return_p10:.1f}% a {s(r.return_p90)}{r.return_p90:.1f}%",
            f"    Peor caso (5%):   {s(r.return_p05)}{r.return_p05:.1f}%  |  Prob. pérdida: {r.prob_loss*100:.0f}%",
            f"  Riesgo",
            f"    VaR 95%: {s(r.var_95)}{r.var_95:.1f}%  |  CVaR 95%: {s(r.cvar_95)}{r.cvar_95:.1f}%",
            f"    Max DD mediano: {r.max_dd_median:.1f}%  |  Max DD peor (5%): {r.max_dd_p95:.1f}%",
            f"  Calidad",
            f"    Sharpe mediano: {r.sharpe_median:.2f}  |  Win rate mediano: {r.win_rate_median:.0f}%",
            f"  {_profile_line(r)}",
            "",
        ]
        return "\n".join(lines)

    def format_footer(self) -> str:
        return (
            "⚠️ _Correlaciones entre activos no modeladas — el riesgo real puede ser mayor._\n"
            "_Pool de retornos: últimos 2 años. Distribución histórica asumida estacionaria._"
        )


async def cmd_montecarlo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /montecarlo CESTA [N_SIMS] [HORIZONTE]"""
    if not context.args:
        await update.message.reply_text(
            "Uso: `/montecarlo Nombre Cesta [simulaciones] [horizonte_días]`\n"
            "Ejemplo: `/montecarlo Cesta Agresiva 100 90`",
            parse_mode="Markdown",
        )
        return

    basket_name, n_sims, horizon = _parse_args(list(context.args))
    if not basket_name:
        await update.message.reply_text("Indica el nombre de la cesta.")
        return

    seed = int(np.random.default_rng().integers(0, 99_999))
    rng = np.random.default_rng(seed)

    msg = await update.message.reply_text(
        f"⏳ Monte Carlo en curso ({n_sims} simulaciones, {horizon} días)..."
        f"\nEsto puede tardar un momento."
    )

    data_provider = YahooDataProvider()
    analyzer = MonteCarloAnalyzer()
    fmt = MonteCarloFormatter()

    async with async_session_factory() as session:
        result = await session.execute(
            select(Basket).where(Basket.name == basket_name, Basket.active == True)
        )
        basket = result.scalar_one_or_none()
        if not basket:
            await msg.delete()
            await update.message.reply_text(f"Cesta '{basket_name}' no encontrada.")
            return

        strategy_cls = STRATEGY_MAP.get(basket.strategy)
        if not strategy_cls:
            await msg.delete()
            await update.message.reply_text(
                f"Estrategia `{basket.strategy}` no soportada en Monte Carlo.",
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
            await msg.delete()
            await update.message.reply_text(f"Cesta '{basket_name}' sin activos activos.")
            return

        header = fmt.format_header(
            basket_name=basket.name,
            strategy=basket.strategy,
            n_assets=len(assets),
            n_sims=n_sims,
            horizon=horizon,
            seed=seed,
        )
        await update.message.reply_text(header, parse_mode="Markdown")

        loop = asyncio.get_event_loop()
        for asset in assets:
            try:
                ohlcv = await loop.run_in_executor(
                    None,
                    lambda t=asset.ticker: data_provider.get_historical(t, period="2y", interval="1d"),
                )
                mc_result = await loop.run_in_executor(
                    None,
                    analyzer.run_asset,
                    asset.ticker, strategy, basket.strategy,
                    ohlcv.data, n_sims, horizon, rng, seed,
                )
                await update.message.reply_text(
                    fmt.format_asset(mc_result), parse_mode="Markdown"
                )
            except Exception as e:
                logger.error("Monte Carlo error %s: %s", asset.ticker, e)
                await update.message.reply_text(f"❌ {asset.ticker}: {e}")

        await update.message.reply_text(fmt.format_footer(), parse_mode="Markdown")

    await msg.delete()


def get_handlers():
    return [CommandHandler("montecarlo", cmd_montecarlo)]
