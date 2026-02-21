from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class PositionView:
    ticker: str
    quantity: Decimal
    avg_price: Decimal
    current_price: Decimal
    currency: str
    market_value: Decimal
    cost_basis: Decimal
    pnl: Decimal
    pnl_pct: Decimal


@dataclass
class BasketValuation:
    basket_id: int
    basket_name: str
    positions: list[PositionView] = field(default_factory=list)
    cash: Decimal = Decimal("0")
    total_invested: Decimal = Decimal("0")
    total_value: Decimal = Decimal("0")
    total_pnl: Decimal = Decimal("0")
    total_pnl_pct: Decimal = Decimal("0")
