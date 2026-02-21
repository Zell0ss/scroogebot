import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Order, Position, Basket
from src.orders.base import OrderExecutor

logger = logging.getLogger(__name__)


class PaperTradingExecutor(OrderExecutor):
    async def buy(self, session: AsyncSession, basket_id, asset_id, user_id,
                  ticker, quantity, price, triggered_by="MANUAL") -> Order:
        total_cost = quantity * price
        basket = await session.get(Basket, basket_id)
        if basket.cash < total_cost:
            raise ValueError(f"Insufficient cash: {basket.cash:.2f} < {total_cost:.2f}")

        basket.cash -= total_cost

        result = await session.execute(
            select(Position).where(
                Position.basket_id == basket_id, Position.asset_id == asset_id,
            )
        )
        pos = result.scalar_one_or_none()
        if pos:
            total_qty = pos.quantity + quantity
            pos.avg_price = (pos.avg_price * pos.quantity + price * quantity) / total_qty
            pos.quantity = total_qty
        else:
            pos = Position(basket_id=basket_id, asset_id=asset_id, quantity=quantity, avg_price=price)
            session.add(pos)

        order = Order(
            basket_id=basket_id, asset_id=asset_id, user_id=user_id,
            type="BUY", quantity=quantity, price=price, status="EXECUTED",
            triggered_by=triggered_by, executed_at=datetime.utcnow(),
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order

    async def sell(self, session: AsyncSession, basket_id, asset_id, user_id,
                   ticker, quantity, price, triggered_by="MANUAL") -> Order:
        result = await session.execute(
            select(Position).where(
                Position.basket_id == basket_id, Position.asset_id == asset_id,
            )
        )
        pos = result.scalar_one_or_none()
        if not pos or pos.quantity < quantity:
            held = pos.quantity if pos else Decimal("0")
            raise ValueError(f"Insufficient position: have {held}, selling {quantity}")

        pos.quantity -= quantity
        basket = await session.get(Basket, basket_id)
        basket.cash += quantity * price

        order = Order(
            basket_id=basket_id, asset_id=asset_id, user_id=user_id,
            type="SELL", quantity=quantity, price=price, status="EXECUTED",
            triggered_by=triggered_by, executed_at=datetime.utcnow(),
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order
