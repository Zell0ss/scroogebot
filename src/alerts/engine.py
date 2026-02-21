import logging

from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Alert, Basket, Asset, Position
from src.data.yahoo import YahooDataProvider
from src.metrics import alert_scans_total, alerts_generated_total, market_open, scan_duration_seconds
from src.scheduler.market_hours import any_market_open, is_market_open
from src.strategies.base import Strategy
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy
from src.strategies.rsi import RSIStrategy
from src.strategies.bollinger import BollingerStrategy
from src.strategies.safe_haven import SafeHavenStrategy

logger = logging.getLogger(__name__)

STRATEGY_MAP: dict[str, type[Strategy]] = {
    "stop_loss": StopLossStrategy,
    "ma_crossover": MACrossoverStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerStrategy,
    "safe_haven": SafeHavenStrategy,
}


class AlertEngine:
    def __init__(self, telegram_app=None):
        self.data = YahooDataProvider()
        self.app = telegram_app

    async def scan_all_baskets(self) -> None:
        """Called by scheduler every N minutes."""
        # Update market-open gauges so Prometheus always reflects current state
        from src.config import app_config
        for mkt in app_config.get("scheduler", {}).get("market_hours", {}):
            market_open.labels(market=mkt).set(1 if is_market_open(mkt) else 0)

        if not any_market_open():
            logger.debug("All markets closed — skipping alert scan")
            alert_scans_total.labels(result="skipped_closed").inc()
            return

        logger.info("Alert scan started")
        with scan_duration_seconds.time():
            async with async_session_factory() as session:
                result = await session.execute(select(Basket).where(Basket.active == True))
                baskets = result.scalars().all()

            for basket in baskets:
                try:
                    await self._scan_basket(basket)
                except Exception as e:
                    logger.error(f"Error scanning basket '{basket.name}': {e}")

        alert_scans_total.labels(result="completed").inc()

    async def _scan_basket(self, basket: Basket) -> None:
        strategy_cls = STRATEGY_MAP.get(basket.strategy)
        if not strategy_cls:
            return
        strategy = strategy_cls()

        async with async_session_factory() as session:
            result = await session.execute(
                select(Position, Asset)
                .join(Asset, Position.asset_id == Asset.id)
                .where(Position.basket_id == basket.id, Position.quantity > 0)
            )
            positions = result.all()

            new_alerts: list[tuple[Alert, str]] = []
            for pos, asset in positions:
                try:
                    if asset.market and not is_market_open(asset.market):
                        logger.debug(f"Skipping {asset.ticker} — {asset.market} closed")
                        continue
                    price_obj = self.data.get_current_price(asset.ticker)
                    historical = self.data.get_historical(asset.ticker, period="3mo", interval="1d")
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
                    new_alerts.append((alert, asset.ticker))
                    alerts_generated_total.labels(
                        strategy=basket.strategy, signal=signal.action
                    ).inc()

                except Exception as e:
                    logger.error(f"Alert scan error {asset.ticker}: {e}")

            if new_alerts:
                await session.flush()  # assign IDs before notify
                for alert, ticker in new_alerts:
                    await self._notify(alert, basket.name, ticker)
                await session.commit()

    async def _notify(self, alert: Alert, basket_name: str, ticker: str) -> None:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        from src.db.models import BasketMember, User

        if not self.app:
            logger.warning("No telegram app set — cannot send notifications")
            return

        async with async_session_factory() as session:
            result = await session.execute(
                select(BasketMember, User)
                .join(User, BasketMember.user_id == User.id)
                .where(BasketMember.basket_id == alert.basket_id)
            )
            members = result.all()

        icon = "⚠️" if alert.signal == "SELL" else "💡"
        verb = "VENTA" if alert.signal == "SELL" else "COMPRA"
        color = "🔴" if alert.signal == "SELL" else "🟢"
        text = (
            f"{icon} *{basket_name}* — {alert.strategy}\n\n"
            f"{color} {verb}: *{ticker}*\n"
            f"Precio: {alert.price:.2f}\n"
            f"Razón: {alert.reason}\n\n"
            f"¿Ejecutar {verb.lower()}?"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Ejecutar", callback_data=f"alert:confirm:{alert.id}"),
            InlineKeyboardButton("❌ Rechazar", callback_data=f"alert:reject:{alert.id}"),
        ]])

        for _, user in members:
            try:
                await self.app.bot.send_message(
                    chat_id=user.tg_id, text=text,
                    parse_mode="Markdown", reply_markup=keyboard,
                )
            except Exception as e:
                logger.error(f"Cannot notify tg_id={user.tg_id}: {e}")
