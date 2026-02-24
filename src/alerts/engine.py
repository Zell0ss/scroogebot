import logging
from datetime import datetime

from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Alert, Basket, Asset, Position
from src.data.yahoo import YahooDataProvider
from src.metrics import alert_scans_total, alerts_generated_total, market_open, scan_duration_seconds
from src.scheduler.market_hours import any_market_open, is_market_open
from decimal import Decimal

from src.strategies.base import Signal, Strategy
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy
from src.strategies.rsi import RSIStrategy
from src.strategies.bollinger import BollingerStrategy
from src.strategies.safe_haven import SafeHavenStrategy
from src.alerts.market_context import MarketContext, compute_market_context
from anthropic import AsyncAnthropic

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

            new_alerts: list[tuple[Alert, str, MarketContext]] = []
            expired_alerts: list[Alert] = []
            for pos, asset in positions:
                try:
                    if asset.market and not is_market_open(asset.market):
                        logger.debug(f"Skipping {asset.ticker} — {asset.market} closed")
                        continue
                    price_obj = self.data.get_current_price(asset.ticker)
                    historical = self.data.get_historical(asset.ticker, period="3mo", interval="1d")
                    signal = strategy.evaluate(asset.ticker, historical.data, price_obj.price, pos.avg_price)

                    # Stop-loss layer: position-based, independent of entry strategy.
                    # Overrides any signal (including BUY) when position is down >= threshold.
                    if basket.stop_loss_pct and pos.avg_price and pos.avg_price > 0:
                        threshold = Decimal(str(basket.stop_loss_pct)) / 100
                        change = (price_obj.price - pos.avg_price) / pos.avg_price
                        if change <= -threshold:
                            signal = Signal(
                                action="SELL", ticker=asset.ticker,
                                price=price_obj.price,
                                reason=(
                                    f"Stop-loss de cesta {basket.stop_loss_pct}% activado"
                                    f" (entrada: {pos.avg_price:.2f})"
                                ),
                                confidence=Decimal("0.99"),
                            )

                    # Deduplicate / expire stale alerts
                    existing = await session.execute(
                        select(Alert).where(
                            Alert.basket_id == basket.id,
                            Alert.asset_id == asset.id,
                            Alert.status == "PENDING",
                        )
                    )
                    existing_alert = existing.scalar_one_or_none()
                    if existing_alert:
                        if not signal or signal.action not in ("BUY", "SELL"):
                            # Condition no longer holds — expire the stale alert
                            existing_alert.status = "EXPIRED"
                            existing_alert.resolved_at = datetime.utcnow()
                            expired_alerts.append(existing_alert)
                        continue

                    if not signal or signal.action not in ("BUY", "SELL"):
                        continue

                    alert = Alert(
                        basket_id=basket.id, asset_id=asset.id,
                        strategy=basket.strategy, signal=signal.action,
                        price=signal.price, reason=signal.reason,
                        status="PENDING",
                    )
                    session.add(alert)
                    market_ctx = compute_market_context(
                        asset.ticker, historical.data, price_obj.price,
                        pos, basket.cash, signal.action, signal.confidence,
                    )
                    new_alerts.append((alert, asset.ticker, market_ctx))
                    alerts_generated_total.labels(
                        strategy=basket.strategy, signal=signal.action
                    ).inc()

                except Exception as e:
                    logger.error(f"Alert scan error {asset.ticker}: {e}")

            if new_alerts:
                await session.flush()  # assign IDs before notify
                for alert, ticker, market_ctx in new_alerts:
                    await self._notify(alert, basket.name, ticker, market_ctx)

            if new_alerts or expired_alerts:
                await session.commit()

    async def _notify(
        self,
        alert: Alert,
        basket_name: str,
        ticker: str,
        ctx: MarketContext | None = None,
    ) -> None:
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

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Ejecutar", callback_data=f"alert:confirm:{alert.id}"),
            InlineKeyboardButton("❌ Rechazar", callback_data=f"alert:reject:{alert.id}"),
        ]])

        if ctx is not None:
            conf_str = f" | Confianza: {int(ctx.confidence * 100)}%"

            if ctx.position_qty > 0 and ctx.avg_price:
                pnl_str = f" (P&L: {ctx.pnl_pct:+.1f}%)" if ctx.pnl_pct is not None else ""
                pos_line = f"Posición: {ctx.position_qty} acc @ {ctx.avg_price:.2f} €{pnl_str}"
            else:
                pos_line = "Posición: sin entrada previa"

            sma20_s = f"{ctx.sma20:.2f}" if ctx.sma20 else "N/D"
            sma50_s = f"{ctx.sma50:.2f}" if ctx.sma50 else "N/D"
            rsi_s   = f"{ctx.rsi14:.1f}" if ctx.rsi14 else "N/D"
            atr_s   = f"{ctx.atr_pct:.1f}%" if ctx.atr_pct else "N/D"

            lines = [
                f"{icon} *{basket_name}* — {alert.strategy}",
                "",
                f"{color} {verb}: *{ticker}*",
                f"Precio: {alert.price:.2f} €{conf_str}",
                pos_line,
                f"Cantidad sugerida: {ctx.suggested_qty} acc",
                f"Razón: {alert.reason}",
                f"SMA20: {sma20_s} | SMA50: {sma50_s} | RSI: {rsi_s} | ATR: {atr_s}",
                f"Tendencia: {ctx.trend}",
            ]
        else:
            lines = [
                f"{icon} *{basket_name}* — {alert.strategy}",
                "",
                f"{color} {verb}: *{ticker}*",
                f"Precio: {alert.price:.2f} €",
                f"Razón: {alert.reason}",
            ]

        for _, user in members:
            try:
                text = "\n".join(lines)
                if ctx is not None and not user.advanced_mode:
                    explanation = await self._build_explanation(
                        alert.strategy, alert.signal, alert.reason, ctx
                    )
                    if explanation:
                        text += f"\n\n💬 _{explanation}_"
                text += f"\n\n¿Ejecutar {verb.lower()}?"
                await self.app.bot.send_message(
                    chat_id=user.tg_id, text=text,
                    parse_mode="Markdown", reply_markup=keyboard,
                )
            except Exception as e:
                logger.error(f"Cannot notify tg_id={user.tg_id}: {e}")

    async def _build_explanation(
        self,
        strategy: str,
        signal: str,
        reason: str,
        ctx: MarketContext,
    ) -> str | None:
        """Call Claude Haiku to generate a 2-3 sentence educational explanation.

        Returns None if the API call fails so the alert is still sent without it.
        """
        try:
            client = AsyncAnthropic()
            sma20_s = f"{ctx.sma20:.2f}" if ctx.sma20 else "N/D"
            sma50_s = f"{ctx.sma50:.2f}" if ctx.sma50 else "N/D"
            rsi_s   = f"{ctx.rsi14:.1f}" if ctx.rsi14 else "N/D"
            atr_s   = f"{ctx.atr_pct:.1f}%" if ctx.atr_pct else "N/D"

            prompt = (
                f"Eres un asesor financiero educativo para un inversor principiante que practica paper trading.\n"
                f"Se ha generado una señal de {signal} para {ctx.ticker}.\n\n"
                f"Estrategia: {strategy}\n"
                f"Razón técnica: {reason}\n"
                f"Precio actual: {ctx.price:.2f}\n"
                f"SMA20: {sma20_s} | SMA50: {sma50_s}\n"
                f"RSI(14): {rsi_s} | ATR: {atr_s}\n"
                f"Tendencia: {ctx.trend}\n"
            )
            if ctx.avg_price and ctx.pnl_pct is not None:
                prompt += f"Posición: entrada a {ctx.avg_price:.2f}, P&L actual: {ctx.pnl_pct:+.1f}%\n"

            prompt += (
                "\nExplica en 2-3 frases cortas y en español:\n"
                "1. Qué significa esta señal técnicamente.\n"
                "2. Por qué es relevante ahora según los indicadores.\n"
                "3. Un recordatorio breve de que es paper trading (sin dinero real).\n"
                "Sé conciso y no uses markdown."
            )

            message = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            logger.warning("Haiku explanation failed for %s: %s", ctx.ticker, e)
            return None
