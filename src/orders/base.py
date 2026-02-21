from abc import ABC, abstractmethod
from decimal import Decimal
from src.db.models import Order


class OrderExecutor(ABC):
    @abstractmethod
    async def buy(
        self, session, basket_id: int, asset_id: int, user_id: int,
        ticker: str, quantity: Decimal, price: Decimal,
        triggered_by: str = "MANUAL",
    ) -> Order: ...

    @abstractmethod
    async def sell(
        self, session, basket_id: int, asset_id: int, user_id: int,
        ticker: str, quantity: Decimal, price: Decimal,
        triggered_by: str = "MANUAL",
    ) -> Order: ...
