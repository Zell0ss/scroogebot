import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.base import DataProvider
from src.db.models import Basket, Position, Asset
from src.portfolio.models import BasketValuation, PositionView

logger = logging.getLogger(__name__)
EUR = "EUR"


class PortfolioEngine:
    def __init__(self, data_provider: DataProvider):
        self.data = data_provider

    async def get_valuation(self, session: AsyncSession, basket_id: int) -> BasketValuation:
        basket = await session.get(Basket, basket_id)
        result = await session.execute(
            select(Position, Asset)
            .join(Asset, Position.asset_id == Asset.id)
            .where(Position.basket_id == basket_id, Position.quantity > 0)
        )
        rows = result.all()

        positions = []
        total_invested = Decimal("0")
        total_value = Decimal("0")

        for pos, asset in rows:
            try:
                price_obj = self.data.get_current_price(asset.ticker)
                current_price = price_obj.price
                if price_obj.currency != EUR:
                    fx = self.data.get_fx_rate(price_obj.currency, EUR)
                    current_price_eur = current_price * fx
                    avg_price_eur = pos.avg_price * fx
                else:
                    current_price_eur = current_price
                    avg_price_eur = pos.avg_price

                market_value = current_price_eur * pos.quantity
                cost_basis = avg_price_eur * pos.quantity
                pnl = market_value - cost_basis
                pnl_pct = (pnl / cost_basis * 100) if cost_basis else Decimal("0")

                positions.append(PositionView(
                    ticker=asset.ticker, quantity=pos.quantity,
                    avg_price=pos.avg_price, current_price=current_price,
                    currency=price_obj.currency, market_value=market_value,
                    cost_basis=cost_basis, pnl=pnl, pnl_pct=pnl_pct,
                ))
                total_invested += cost_basis
                total_value += market_value
            except Exception as e:
                logger.error(f"Error pricing {asset.ticker}: {e}")

        total_value += basket.cash
        total_pnl = total_value - total_invested - basket.cash
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else Decimal("0")

        return BasketValuation(
            basket_id=basket.id, basket_name=basket.name,
            positions=positions, cash=basket.cash,
            total_invested=total_invested, total_value=total_value,
            total_pnl=total_pnl, total_pnl_pct=total_pnl_pct,
        )
