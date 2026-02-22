from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Numeric,
    String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(100))
    first_name: Mapped[str | None] = mapped_column(String(100))
    active_basket_id: Mapped[int | None] = mapped_column(ForeignKey("baskets.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    memberships: Mapped[list[BasketMember]] = relationship(back_populates="user")


class Basket(Base):
    __tablename__ = "baskets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_profile: Mapped[str] = mapped_column(String(50), default="moderate")
    cash: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), default="EUR")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    broker: Mapped[str] = mapped_column(String(50), nullable=False, default="paper")
    stop_loss_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    members: Mapped[list[BasketMember]] = relationship(back_populates="basket")
    basket_assets: Mapped[list[BasketAsset]] = relationship(back_populates="basket")
    positions: Mapped[list[Position]] = relationship(back_populates="basket")
    orders: Mapped[list[Order]] = relationship(back_populates="basket")
    alerts: Mapped[list[Alert]] = relationship(back_populates="basket")


class BasketMember(Base):
    __tablename__ = "basket_members"

    basket_id: Mapped[int] = mapped_column(ForeignKey("baskets.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # OWNER | MEMBER

    basket: Mapped[Basket] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    market: Mapped[str | None] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(10), default="USD")


class BasketAsset(Base):
    __tablename__ = "basket_assets"

    basket_id: Mapped[int] = mapped_column(ForeignKey("baskets.id"), primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    basket: Mapped[Basket] = relationship(back_populates="basket_assets")
    asset: Mapped[Asset] = relationship()


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    basket_id: Mapped[int] = mapped_column(ForeignKey("baskets.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 6), default=Decimal("0"))
    avg_price: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    basket: Mapped[Basket] = relationship(back_populates="positions")
    asset: Mapped[Asset] = relationship()


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    basket_id: Mapped[int] = mapped_column(ForeignKey("baskets.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)   # BUY | SELL
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="EXECUTED")
    triggered_by: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)

    basket: Mapped[Basket] = relationship(back_populates="orders")
    asset: Mapped[Asset] = relationship()
    user: Mapped[User] = relationship()


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    basket_id: Mapped[int] = mapped_column(ForeignKey("baskets.id"), nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    signal: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY | SELL
    price: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    basket: Mapped[Basket] = relationship(back_populates="alerts")
    asset: Mapped[Asset] = relationship()


class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped[User] = relationship()


class CommandLog(Base):
    __tablename__ = "command_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str | None] = mapped_column(String(100))
    command: Mapped[str] = mapped_column(String(50), nullable=False)
    args: Mapped[str | None] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
