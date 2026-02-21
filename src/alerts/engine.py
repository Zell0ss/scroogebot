import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import async_session_factory
from src.db.models import Alert, Basket, Asset, Position
from src.data.yahoo import YahooDataProvider
from src.strategies.base import Strategy
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy

logger = logging.getLogger(__name__)

STRATEGY_MAP: dict[str, type[Strategy]] = {
    "stop_loss": StopLossStrategy,
    "ma_crossover": MACrossoverStrategy,
}


class AlertEngine:
    def __init__(self, telegram_app=None):
        self.data = YahooDataProvider()
        self.app = telegram_app

    async def scan_all_baskets(self) -> None:
        """Called by scheduler every N minutes."""
        logger.info("Alert scan started")
        async with async_session_factory() as session:
            result = await session.execute(select(Basket).where(Basket.active == True))
            for basket in result.scalars().all():
                await self._scan_basket(session, basket)

    async def _scan_basket(self, session: AsyncSession, basket: Basket) -> None:
        strategy_cls = STRATEGY_MAP.get(basket.strategy)
        if not strategy_cls:
            return
        strategy = strategy_cls()

        result = await session.execute(
            select(Position, Asset)
            .join(Asset, Position.asset_id == Asset.id)
            .where(Position.basket_id == basket.id, Position.quantity > 0)
        )
        for pos, asset in result.all():
            try:
                price_obj = self.data.get_current_price(asset.ticker)
                historical = self.data.get_historical(asset.ticker, period="3mo")
                signal = strategy.evaluate(asset.ticker, historical.data, price_obj.price)

                if not signal or signal.action not in ("BUY", "SELL"):
                    continue

                # Deduplicate: skip if a PENDING alert already exists
                existing = await session.execute(
                    select(Alert).where(
                        Alert.basket_id == basket.id,
                        Alert.asset_id == asset.id,
                        Alert.status == "PENDING",
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                alert = Alert(
                    basket_id=basket.id, asset_id=asset.id,
                    strategy=basket.strategy, signal=signal.action,
                    price=signal.price, reason=signal.reason,
                    status="PENDING",
                )
                session.add(alert)
                await session.flush()
                await session.commit()
                await self._notify(alert, basket.name, asset.ticker)

            except Exception as e:
                logger.error(f"Alert scan error {asset.ticker}: {e}")

    async def _notify(self, alert: Alert, basket_name: str, ticker: str) -> None:
        """Notify all basket members. Full implementation in Task 4 (roles)."""
        logger.info(f"ALERT [{alert.signal}] {ticker} in {basket_name}: {alert.reason}")
        # Telegram notification added in Task 4
