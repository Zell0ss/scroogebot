import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from src.orders.paper import PaperTradingExecutor


def _make_session(basket=None, position=None):
    """Build a minimal async session mock with explicit sync execute result."""
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = position

    session = MagicMock()
    session.get = AsyncMock(return_value=basket)
    session.execute = AsyncMock(return_value=execute_result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def executor():
    return PaperTradingExecutor()


@pytest.mark.asyncio
async def test_buy_deducts_cash(executor):
    basket = MagicMock(cash=Decimal("10000"), id=1)
    session = _make_session(basket=basket, position=None)

    await executor.buy(
        session, basket_id=1, asset_id=1, user_id=1,
        ticker="AAPL", quantity=Decimal("10"), price=Decimal("150"),
    )
    assert basket.cash == Decimal("8500")


@pytest.mark.asyncio
async def test_buy_insufficient_cash_raises(executor):
    basket = MagicMock(cash=Decimal("100"), id=1)
    session = _make_session(basket=basket, position=None)

    with pytest.raises(ValueError, match="Insufficient cash"):
        await executor.buy(
            session, basket_id=1, asset_id=1, user_id=1,
            ticker="AAPL", quantity=Decimal("10"), price=Decimal("150"),
        )


@pytest.mark.asyncio
async def test_sell_no_position_raises(executor):
    session = _make_session(basket=None, position=None)

    with pytest.raises(ValueError, match="Insufficient position"):
        await executor.sell(
            session, basket_id=1, asset_id=1, user_id=1,
            ticker="AAPL", quantity=Decimal("5"), price=Decimal("150"),
        )
