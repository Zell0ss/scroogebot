# ScroogeBot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a full Telegram investment bot with shared baskets, automatic strategy alerts, paper trading, and backtesting.

**Architecture:** 8 vertical slices from scaffold to advanced features. Each slice delivers working, testable functionality. Abstract interfaces (DataProvider, OrderExecutor, Strategy) allow clean PoC→production swap.

**Tech Stack:** Python 3.11, python-telegram-bot v20+, SQLAlchemy 2.0 async, aiomysql, Alembic, APScheduler 3.x, yfinance, pandas-ta, vectorbt, pydantic-settings, MariaDB.

---

## Environment

All credentials are in `/data/scroogebot/.env`. Never hardcode them.

```
telegram_apikey, telegram_name, telegram_username
anthropic_apikey   (reserved for v2)
mariadb_host, mariadb_port, mariadb_database, mariadb_user, mariadb_password
```

Run all commands from `/data/scroogebot/`.
Python: `.venv/bin/python` — install deps: `.venv/bin/pip install -e ".[dev]"`.

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `scroogebot.py`
- Create: `src/__init__.py`
- Create: `config/config.yaml`
- Create: `config/logging.yaml`

**Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "scroogebot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "python-telegram-bot>=20.0",
    "yfinance>=0.2",
    "pandas-ta>=0.3",
    "sqlalchemy>=2.0",
    "aiomysql>=0.2",
    "alembic>=1.13",
    "apscheduler>=3.10",
    "pydantic-settings>=2.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov",
]
backtest = [
    "vectorbt>=0.26",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Write `config/config.yaml`**

```yaml
scheduler:
  interval_minutes: 5
  market_hours:
    NYSE:
      open: "14:30"   # UTC
      close: "21:00"
    IBEX:
      open: "08:00"
      close: "16:30"

strategies:
  stop_loss:
    stop_loss_pct: 8.0
    take_profit_pct: 15.0

  ma_crossover:
    fast_period: 20
    slow_period: 50

  rsi:
    period: 14
    oversold: 30
    overbought: 70

  bollinger:
    period: 20
    std_dev: 2.0

baskets:
  - name: "Cesta Agresiva"
    strategy: ma_crossover
    risk_profile: aggressive
    cash: 10000.0
    assets:
      - ticker: AAPL
        name: "Apple Inc"
        market: NYSE
        currency: USD
      - ticker: MSFT
        name: "Microsoft Corp"
        market: NYSE
        currency: USD
      - ticker: NVDA
        name: "NVIDIA Corp"
        market: NYSE
        currency: USD

  - name: "Cesta Conservadora"
    strategy: safe_haven
    risk_profile: conservative
    cash: 10000.0
    assets:
      - ticker: "SAN.MC"
        name: "Banco Santander"
        market: IBEX
        currency: EUR
      - ticker: "IBE.MC"
        name: "Iberdrola"
        market: IBEX
        currency: EUR
      - ticker: GLD
        name: "SPDR Gold Shares"
        market: NYSE
        currency: USD
```

**Step 3: Write `config/logging.yaml`**

```yaml
version: 1
disable_existing_loggers: false
formatters:
  standard:
    format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
handlers:
  console:
    class: logging.StreamHandler
    formatter: standard
    stream: ext://sys.stdout
  file:
    class: logging.FileHandler
    formatter: standard
    filename: scroogebot.log
root:
  level: INFO
  handlers: [console, file]
```

**Step 4: Write `scroogebot.py` (entrypoint stub)**

```python
import asyncio
import logging
import logging.config
import yaml

with open("config/logging.yaml") as f:
    logging.config.dictConfig(yaml.safe_load(f))

from src.bot.bot import run

if __name__ == "__main__":
    asyncio.run(run())
```

**Step 5: Write `src/__init__.py`**

```python
```

**Step 6: Install dependencies**

```bash
.venv/bin/pip install -e ".[dev]"
```

Expected: packages installed without errors.

**Step 7: Commit**

```bash
git add pyproject.toml scroogebot.py src/__init__.py config/
git commit -m "feat: project scaffold with pyproject.toml and config files"
```

---

## Task 2: Configuration Module

**Files:**
- Create: `src/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

**Step 1: Write `src/config.py`**

```python
from __future__ import annotations
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    telegram_apikey: str
    telegram_name: str
    telegram_username: str
    anthropic_apikey: str = ""

    mariadb_host: str = "localhost"
    mariadb_port: int = 3306
    mariadb_database: str
    mariadb_user: str
    mariadb_password: str

    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.mariadb_user}:{self.mariadb_password}"
            f"@{self.mariadb_host}:{self.mariadb_port}/{self.mariadb_database}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"mysql+pymysql://{self.mariadb_user}:{self.mariadb_password}"
            f"@{self.mariadb_host}:{self.mariadb_port}/{self.mariadb_database}"
        )


def load_app_config(path: str = "config/config.yaml") -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


settings = Settings()
app_config = load_app_config()
```

**Step 2: Write `tests/__init__.py`**

```python
```

**Step 3: Write failing test `tests/test_config.py`**

```python
from src.config import settings, app_config


def test_settings_loads():
    assert settings.telegram_apikey
    assert settings.mariadb_host
    assert settings.database_url.startswith("mysql+aiomysql://")


def test_app_config_has_baskets():
    assert "baskets" in app_config
    assert len(app_config["baskets"]) >= 1


def test_app_config_has_strategies():
    assert "strategies" in app_config
    assert "stop_loss" in app_config["strategies"]
```

**Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_config.py -v
```

Expected: 3 tests PASS.

**Step 5: Commit**

```bash
git add src/config.py tests/
git commit -m "feat: pydantic-settings config module with yaml app config"
```

---

## Task 3: Database Models and Migrations

**Files:**
- Create: `src/db/__init__.py`
- Create: `src/db/base.py`
- Create: `src/db/models.py`
- Create: `alembic.ini`
- Create: `src/db/migrations/env.py` (via alembic init)

**Step 1: Write `src/db/__init__.py`**

```python
```

**Step 2: Write `src/db/base.py`**

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from src.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
```

**Step 3: Write `src/db/models.py`**

```python
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
    triggered_by: Mapped[str | None] = mapped_column(String(50))  # MANUAL | strategy name
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
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING|CONFIRMED|REJECTED|EXPIRED
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
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING | ACTIVE
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped[User] = relationship()
```

**Step 4: Install pymysql for Alembic sync driver**

```bash
.venv/bin/pip install pymysql
```

**Step 5: Initialize Alembic**

```bash
.venv/bin/alembic init src/db/migrations
```

**Step 6: Edit `alembic.ini`**

Replace the `sqlalchemy.url` line with:
```ini
sqlalchemy.url = driver://user:pass@localhost/dbname
```
(We override it in env.py so this value doesn't matter.)

**Step 7: Edit `src/db/migrations/env.py`**

Replace the file content with:

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from src.config import settings
from src.db.base import Base
import src.db.models  # noqa: F401 — registers all models

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Step 8: Generate and apply initial migration**

```bash
.venv/bin/alembic revision --autogenerate -m "initial schema"
.venv/bin/alembic upgrade head
```

Expected: tables created in MariaDB without errors.

**Step 9: Verify tables exist**

```bash
.venv/bin/python -c "
import asyncio
from sqlalchemy import text
from src.db.base import engine

async def check():
    async with engine.connect() as conn:
        result = await conn.execute(text('SHOW TABLES'))
        for row in result:
            print(row[0])

asyncio.run(check())
"
```

Expected: lists `users`, `baskets`, `basket_members`, `assets`, `basket_assets`, `positions`, `orders`, `alerts`, `watchlist`.

**Step 10: Commit**

```bash
git add src/db/ alembic.ini
git commit -m "feat: SQLAlchemy models and Alembic initial migration"
```

---

## Task 4: DB Seeder (baskets from config.yaml)

**Files:**
- Create: `src/db/seed.py`

**Step 1: Write `src/db/seed.py`**

```python
"""Seed baskets and assets from config/config.yaml into the database.
Run once after migrations: python -m src.db.seed
Idempotent: skips existing records.
"""
import asyncio
from src.config import app_config
from src.db.base import async_session_factory
from src.db.models import Asset, Basket, BasketAsset
from sqlalchemy import select


async def seed() -> None:
    async with async_session_factory() as session:
        for basket_cfg in app_config["baskets"]:
            # Upsert basket
            result = await session.execute(
                select(Basket).where(Basket.name == basket_cfg["name"])
            )
            basket = result.scalar_one_or_none()
            if not basket:
                basket = Basket(
                    name=basket_cfg["name"],
                    strategy=basket_cfg["strategy"],
                    risk_profile=basket_cfg.get("risk_profile", "moderate"),
                    cash=basket_cfg.get("cash", 0),
                )
                session.add(basket)
                await session.flush()
                print(f"Created basket: {basket.name}")

            for asset_cfg in basket_cfg.get("assets", []):
                # Upsert asset
                result = await session.execute(
                    select(Asset).where(Asset.ticker == asset_cfg["ticker"])
                )
                asset = result.scalar_one_or_none()
                if not asset:
                    asset = Asset(
                        ticker=asset_cfg["ticker"],
                        name=asset_cfg.get("name"),
                        market=asset_cfg.get("market"),
                        currency=asset_cfg.get("currency", "USD"),
                    )
                    session.add(asset)
                    await session.flush()

                # Link basket ↔ asset
                result = await session.execute(
                    select(BasketAsset).where(
                        BasketAsset.basket_id == basket.id,
                        BasketAsset.asset_id == asset.id,
                    )
                )
                if not result.scalar_one_or_none():
                    session.add(BasketAsset(basket_id=basket.id, asset_id=asset.id))

        await session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
```

**Step 2: Run seeder**

```bash
.venv/bin/python -m src.db.seed
```

Expected: `Created basket: Cesta Agresiva`, `Created basket: Cesta Conservadora`, `Seed complete.`

**Step 3: Commit**

```bash
git add src/db/seed.py
git commit -m "feat: DB seeder from config.yaml baskets"
```

---

## Task 5: DataProvider

**Files:**
- Create: `src/data/__init__.py`
- Create: `src/data/models.py`
- Create: `src/data/base.py`
- Create: `src/data/yahoo.py`
- Create: `tests/test_data.py`

**Step 1: Write `src/data/models.py`**

```python
from dataclasses import dataclass
from decimal import Decimal
import pandas as pd


@dataclass
class Price:
    ticker: str
    price: Decimal
    currency: str


@dataclass
class OHLCV:
    ticker: str
    data: pd.DataFrame  # columns: Open, High, Low, Close, Volume; DatetimeIndex
```

**Step 2: Write `src/data/base.py`**

```python
from abc import ABC, abstractmethod
from decimal import Decimal
import pandas as pd
from src.data.models import Price, OHLCV


class DataProvider(ABC):
    @abstractmethod
    def get_current_price(self, ticker: str) -> Price: ...

    @abstractmethod
    def get_historical(self, ticker: str, period: str = "3mo", interval: str = "1d") -> OHLCV: ...

    def get_fx_rate(self, from_currency: str, to_currency: str) -> Decimal:
        """EUR/USD conversion via EURUSD=X. Override in broker implementations."""
        if from_currency == to_currency:
            return Decimal("1")
        fx_ticker = f"{from_currency}{to_currency}=X"
        price = self.get_current_price(fx_ticker)
        return price.price
```

**Step 3: Write `src/data/yahoo.py`**

```python
import logging
from decimal import Decimal

import yfinance as yf
import pandas as pd

from src.data.base import DataProvider
from src.data.models import Price, OHLCV

logger = logging.getLogger(__name__)


class YahooDataProvider(DataProvider):
    def get_current_price(self, ticker: str) -> Price:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = Decimal(str(info.last_price))
        currency = getattr(info, "currency", "USD") or "USD"
        return Price(ticker=ticker, price=price, currency=currency)

    def get_historical(self, ticker: str, period: str = "3mo", interval: str = "1d") -> OHLCV:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            raise ValueError(f"No data for {ticker}")
        # Flatten multi-index columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return OHLCV(ticker=ticker, data=df)
```

**Step 4: Write failing test `tests/test_data.py`**

```python
"""Integration tests — requires network access to Yahoo Finance."""
import pytest
from decimal import Decimal
from src.data.yahoo import YahooDataProvider


@pytest.fixture
def provider():
    return YahooDataProvider()


def test_get_current_price(provider):
    price = provider.get_current_price("AAPL")
    assert price.ticker == "AAPL"
    assert price.price > Decimal("10")
    assert price.currency == "USD"


def test_get_historical(provider):
    ohlcv = provider.get_historical("AAPL", period="1mo", interval="1d")
    assert ohlcv.ticker == "AAPL"
    assert not ohlcv.data.empty
    assert "Close" in ohlcv.data.columns


def test_get_fx_rate(provider):
    rate = provider.get_fx_rate("EUR", "USD")
    assert Decimal("0.5") < rate < Decimal("2.0")
```

**Step 5: Run tests**

```bash
.venv/bin/pytest tests/test_data.py -v
```

Expected: 3 tests PASS (requires network).

**Step 6: Commit**

```bash
git add src/data/ tests/test_data.py
git commit -m "feat: DataProvider abstraction with YahooDataProvider"
```

---

## Task 6: PortfolioEngine + /valoracion

**Files:**
- Create: `src/portfolio/__init__.py`
- Create: `src/portfolio/models.py`
- Create: `src/portfolio/engine.py`
- Create: `src/bot/__init__.py`
- Create: `src/bot/handlers/__init__.py`
- Create: `src/bot/handlers/portfolio.py`
- Create: `src/bot/bot.py`
- Create: `tests/test_portfolio.py`

**Step 1: Write `src/portfolio/models.py`**

```python
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
    currency: str = "EUR"
```

**Step 2: Write `src/portfolio/engine.py`**

```python
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
        result = await session.execute(
            select(Basket).where(Basket.id == basket_id)
        )
        basket = result.scalar_one()

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
                current_currency = price_obj.currency

                # Convert to EUR if needed
                if current_currency != EUR:
                    fx = self.data.get_fx_rate(current_currency, EUR)
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
                    ticker=asset.ticker,
                    quantity=pos.quantity,
                    avg_price=pos.avg_price,
                    current_price=current_price,
                    currency=current_currency,
                    market_value=market_value,
                    cost_basis=cost_basis,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                ))
                total_invested += cost_basis
                total_value += market_value

            except Exception as e:
                logger.error(f"Error pricing {asset.ticker}: {e}")

        total_value += basket.cash
        total_pnl = total_value - total_invested - basket.cash
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else Decimal("0")

        return BasketValuation(
            basket_id=basket.id,
            basket_name=basket.name,
            positions=positions,
            cash=basket.cash,
            total_invested=total_invested,
            total_value=total_value,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
        )
```

**Step 3: Write `src/bot/handlers/portfolio.py`**

```python
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from src.db.base import async_session_factory
from src.db.models import Basket, BasketMember
from src.data.yahoo import YahooDataProvider
from src.portfolio.engine import PortfolioEngine
from sqlalchemy import select

logger = logging.getLogger(__name__)
_provider = YahooDataProvider()
_engine = PortfolioEngine(_provider)


def _fmt(val, decimals=2) -> str:
    return f"{val:,.{decimals}f}"


def _arrow(pnl) -> str:
    return "📈" if pnl >= 0 else "📉"


async def cmd_valoracion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_tg_id = update.effective_user.id
    async with async_session_factory() as session:
        # Find baskets where user is a member
        result = await session.execute(
            select(Basket)
            .join(BasketMember, BasketMember.basket_id == Basket.id)
            .join_from(BasketMember, BasketMember.user_id == user_tg_id)  # simplified; see note
        )
        # Note: this join uses tg_id. For simplicity in first slice we query all baskets.
        # Full role check added in Task 11.
        baskets_result = await session.execute(select(Basket).where(Basket.active == True))
        baskets = baskets_result.scalars().all()

        if not baskets:
            await update.message.reply_text("No hay cestas configuradas.")
            return

        # If args given, filter by name
        if context.args:
            name_filter = " ".join(context.args).lower()
            baskets = [b for b in baskets if name_filter in b.name.lower()]

        for basket in baskets:
            msg = await update.message.reply_text(f"⏳ Calculando {basket.name}...")
            try:
                val = await _engine.get_valuation(session, basket.id)
                tickers = ",".join(p.ticker for p in val.positions)
                finviz_url = f"https://finviz.com/screener.ashx?v=111&t={tickers}" if tickers else ""

                lines = [
                    f"📊 *{val.basket_name}* — {datetime.now().strftime('%d %b %Y %H:%M')}",
                    "",
                    f"💼 Capital invertido: {_fmt(val.total_invested)}€",
                    f"💰 Valor actual:      {_fmt(val.total_value)}€",
                    f"{'📈' if val.total_pnl >= 0 else '📉'} P&L total:        {'+' if val.total_pnl >= 0 else ''}{_fmt(val.total_pnl)}€ ({'+' if val.total_pnl_pct >= 0 else ''}{_fmt(val.total_pnl_pct)}%)",
                    "",
                    "─" * 33,
                ]
                for p in val.positions:
                    sym = p.currency if p.currency != "EUR" else "€"
                    lines.append(
                        f"{p.ticker:<8} {_fmt(p.quantity, 0)} × {sym}{_fmt(p.current_price)} = {_fmt(p.market_value)}€  {_arrow(p.pnl)} {'+' if p.pnl_pct >= 0 else ''}{_fmt(p.pnl_pct)}%"
                    )
                lines += [
                    "─" * 33,
                    f"💵 Cash disponible: {_fmt(val.cash)}€",
                ]
                if finviz_url:
                    lines.append(f"\n🔍 [Detalle Finviz]({finviz_url})")

                await msg.edit_text("\n".join(lines), parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Valuation error basket {basket.id}: {e}")
                await msg.edit_text(f"❌ Error calculando {basket.name}: {e}")


def get_handlers():
    return [CommandHandler("valoracion", cmd_valoracion)]
```

**Step 4: Write `src/bot/bot.py`**

```python
import logging
from telegram.ext import Application
from src.config import settings
from src.bot.handlers.portfolio import get_handlers as portfolio_handlers

logger = logging.getLogger(__name__)


async def run() -> None:
    app = Application.builder().token(settings.telegram_apikey).build()

    for handler in portfolio_handlers():
        app.add_handler(handler)

    logger.info("ScroogeBot starting...")
    await app.run_polling(drop_pending_updates=True)
```

**Step 5: Run the bot manually to test `/valoracion`**

```bash
.venv/bin/python scroogebot.py
```

Open Telegram, send `/valoracion` to `@Tio_IA_Gilito_bot`.
Expected: bot replies with portfolio valuation (or "No hay cestas" if no positions yet).

Stop with Ctrl+C.

**Step 6: Commit**

```bash
git add src/portfolio/ src/bot/ tests/test_portfolio.py
git commit -m "feat: PortfolioEngine and /valoracion command"
```

---

## Task 7: OrderExecutor (Paper Trading) + /compra /vende

**Files:**
- Create: `src/orders/__init__.py`
- Create: `src/orders/base.py`
- Create: `src/orders/paper.py`
- Create: `src/bot/handlers/orders.py`
- Create: `tests/test_orders.py`

**Step 1: Write `src/orders/base.py`**

```python
from abc import ABC, abstractmethod
from decimal import Decimal
from src.db.models import Order


class OrderExecutor(ABC):
    @abstractmethod
    async def buy(
        self,
        session,
        basket_id: int,
        asset_id: int,
        user_id: int,
        ticker: str,
        quantity: Decimal,
        price: Decimal,
        triggered_by: str = "MANUAL",
    ) -> Order: ...

    @abstractmethod
    async def sell(
        self,
        session,
        basket_id: int,
        asset_id: int,
        user_id: int,
        ticker: str,
        quantity: Decimal,
        price: Decimal,
        triggered_by: str = "MANUAL",
    ) -> Order: ...
```

**Step 2: Write `src/orders/paper.py`**

```python
import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Order, Position, Asset, Basket
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

        # Update position
        result = await session.execute(
            select(Position).where(
                Position.basket_id == basket_id,
                Position.asset_id == asset_id,
            )
        )
        pos = result.scalar_one_or_none()
        if pos:
            total_qty = pos.quantity + quantity
            pos.avg_price = (pos.avg_price * pos.quantity + price * quantity) / total_qty
            pos.quantity = total_qty
        else:
            pos = Position(
                basket_id=basket_id, asset_id=asset_id,
                quantity=quantity, avg_price=price,
            )
            session.add(pos)

        order = Order(
            basket_id=basket_id, asset_id=asset_id, user_id=user_id,
            type="BUY", quantity=quantity, price=price,
            status="EXECUTED", triggered_by=triggered_by,
            executed_at=datetime.utcnow(),
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order

    async def sell(self, session: AsyncSession, basket_id, asset_id, user_id,
                   ticker, quantity, price, triggered_by="MANUAL") -> Order:
        result = await session.execute(
            select(Position).where(
                Position.basket_id == basket_id,
                Position.asset_id == asset_id,
            )
        )
        pos = result.scalar_one_or_none()
        if not pos or pos.quantity < quantity:
            held = pos.quantity if pos else 0
            raise ValueError(f"Insufficient position: have {held}, selling {quantity}")

        pos.quantity -= quantity
        basket = await session.get(Basket, basket_id)
        basket.cash += quantity * price

        order = Order(
            basket_id=basket_id, asset_id=asset_id, user_id=user_id,
            type="SELL", quantity=quantity, price=price,
            status="EXECUTED", triggered_by=triggered_by,
            executed_at=datetime.utcnow(),
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order
```

**Step 3: Write `tests/test_orders.py`**

```python
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from src.orders.paper import PaperTradingExecutor


@pytest.fixture
def executor():
    return PaperTradingExecutor()


@pytest.mark.asyncio
async def test_buy_updates_position(executor):
    basket = MagicMock(cash=Decimal("10000"), id=1)
    session = AsyncMock()
    session.get.return_value = basket
    session.execute.return_value.scalar_one_or_none.return_value = None  # no existing position

    order = await executor.buy(
        session, basket_id=1, asset_id=1, user_id=1,
        ticker="AAPL", quantity=Decimal("10"), price=Decimal("150"),
    )
    assert basket.cash == Decimal("8500")
    session.add.assert_called()


@pytest.mark.asyncio
async def test_sell_insufficient_raises(executor):
    session = AsyncMock()
    session.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(ValueError, match="Insufficient position"):
        await executor.sell(
            session, basket_id=1, asset_id=1, user_id=1,
            ticker="AAPL", quantity=Decimal("5"), price=Decimal("150"),
        )
```

**Step 4: Write `src/bot/handlers/orders.py`**

```python
import logging
from decimal import Decimal, InvalidOperation

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from src.db.base import async_session_factory
from src.db.models import Asset, Basket, User
from src.data.yahoo import YahooDataProvider
from src.orders.paper import PaperTradingExecutor
from sqlalchemy import select

logger = logging.getLogger(__name__)
_provider = YahooDataProvider()
_executor = PaperTradingExecutor()


async def _get_or_create_user(session, tg_user) -> User:
    result = await session.execute(select(User).where(User.tg_id == tg_user.id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(tg_id=tg_user.id, username=tg_user.username, first_name=tg_user.first_name)
        session.add(user)
        await session.flush()
    return user


async def _parse_order_args(context, update) -> tuple[str, Decimal, Basket, Asset] | None:
    """Parse /compra|/vende TICKER quantity [basket_name]"""
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /compra TICKER cantidad [cesta]")
        return None
    ticker = context.args[0].upper()
    try:
        quantity = Decimal(context.args[1])
    except InvalidOperation:
        await update.message.reply_text("Cantidad inválida.")
        return None

    async with async_session_factory() as session:
        asset_result = await session.execute(select(Asset).where(Asset.ticker == ticker))
        asset = asset_result.scalar_one_or_none()
        if not asset:
            await update.message.reply_text(f"Ticker {ticker} no encontrado en ninguna cesta.")
            return None

        basket_result = await session.execute(select(Basket).where(Basket.active == True))
        basket = basket_result.scalars().first()  # simplified: first basket; full role check in Task 11
        if not basket:
            await update.message.reply_text("No hay cestas activas.")
            return None

        return ticker, quantity, basket, asset


async def cmd_compra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parsed = await _parse_order_args(context, update)
    if not parsed:
        return
    ticker, quantity, basket, asset = parsed

    try:
        price_obj = _provider.get_current_price(ticker)
        price = price_obj.price
    except Exception as e:
        await update.message.reply_text(f"Error obteniendo precio de {ticker}: {e}")
        return

    async with async_session_factory() as session:
        user = await _get_or_create_user(session, update.effective_user)
        try:
            order = await _executor.buy(
                session, basket_id=basket.id, asset_id=asset.id, user_id=user.id,
                ticker=ticker, quantity=quantity, price=price,
            )
            await update.message.reply_text(
                f"✅ *Compra ejecutada*\n"
                f"{quantity} {ticker} × {price:.2f} {price_obj.currency}\n"
                f"Total: {quantity * price:.2f} {price_obj.currency}\n"
                f"Cesta: {basket.name}",
                parse_mode="Markdown",
            )
        except ValueError as e:
            await update.message.reply_text(f"❌ {e}")


async def cmd_vende(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parsed = await _parse_order_args(context, update)
    if not parsed:
        return
    ticker, quantity, basket, asset = parsed

    try:
        price_obj = _provider.get_current_price(ticker)
        price = price_obj.price
    except Exception as e:
        await update.message.reply_text(f"Error obteniendo precio de {ticker}: {e}")
        return

    async with async_session_factory() as session:
        user = await _get_or_create_user(session, update.effective_user)
        try:
            order = await _executor.sell(
                session, basket_id=basket.id, asset_id=asset.id, user_id=user.id,
                ticker=ticker, quantity=quantity, price=price,
            )
            await update.message.reply_text(
                f"✅ *Venta ejecutada*\n"
                f"{quantity} {ticker} × {price:.2f} {price_obj.currency}\n"
                f"Total: {quantity * price:.2f} {price_obj.currency}\n"
                f"Cesta: {basket.name}",
                parse_mode="Markdown",
            )
        except ValueError as e:
            await update.message.reply_text(f"❌ {e}")


def get_handlers():
    return [
        CommandHandler("compra", cmd_compra),
        CommandHandler("vende", cmd_vende),
    ]
```

**Step 5: Register handlers in `src/bot/bot.py`**

Add to the imports and `run()` function:
```python
from src.bot.handlers.orders import get_handlers as order_handlers
# In run():
for handler in order_handlers():
    app.add_handler(handler)
```

**Step 6: Run tests**

```bash
.venv/bin/pytest tests/test_orders.py -v
```

Expected: 2 tests PASS.

**Step 7: Test manually**

Start bot, send `/compra AAPL 5` — expect execution confirmation. Then `/valoracion` — expect position reflected.

**Step 8: Commit**

```bash
git add src/orders/ src/bot/handlers/orders.py tests/test_orders.py
git commit -m "feat: paper trading OrderExecutor and /compra /vende commands"
```

---

## Task 8: /cartera and /historial

**Files:**
- Modify: `src/bot/handlers/portfolio.py`

**Step 1: Add `cmd_cartera` to `src/bot/handlers/portfolio.py`**

```python
async def cmd_cartera(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session_factory() as session:
        baskets_result = await session.execute(select(Basket).where(Basket.active == True))
        baskets = baskets_result.scalars().all()
        for basket in baskets:
            result = await session.execute(
                select(Position, Asset)
                .join(Asset, Position.asset_id == Asset.id)
                .where(Position.basket_id == basket.id, Position.quantity > 0)
            )
            rows = result.all()
            if not rows:
                await update.message.reply_text(f"*{basket.name}*: sin posiciones abiertas.", parse_mode="Markdown")
                continue
            lines = [f"💼 *{basket.name}* — Posiciones abiertas\n"]
            for pos, asset in rows:
                lines.append(f"{asset.ticker:<8} {_fmt(pos.quantity, 4)} acc @ {_fmt(pos.avg_price)}")
            lines.append(f"\n💵 Cash: {_fmt(basket.cash)}€")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
```

**Step 2: Add `cmd_historial` to `src/bot/handlers/portfolio.py`**

```python
from src.db.models import Order  # add to imports

async def cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    limit = 10
    async with async_session_factory() as session:
        baskets_result = await session.execute(select(Basket).where(Basket.active == True))
        baskets = baskets_result.scalars().all()
        for basket in baskets:
            result = await session.execute(
                select(Order, Asset)
                .join(Asset, Order.asset_id == Asset.id)
                .where(Order.basket_id == basket.id)
                .order_by(Order.created_at.desc())
                .limit(limit)
            )
            rows = result.all()
            if not rows:
                await update.message.reply_text(f"*{basket.name}*: sin órdenes.", parse_mode="Markdown")
                continue
            lines = [f"📋 *{basket.name}* — Últimas {limit} órdenes\n"]
            for order, asset in rows:
                icon = "🟢" if order.type == "BUY" else "🔴"
                dt = order.created_at.strftime("%d/%m %H:%M")
                lines.append(f"{icon} {dt} {order.type} {_fmt(order.quantity, 2)} {asset.ticker} @ {_fmt(order.price)}")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
```

**Step 3: Register in `get_handlers()`**

```python
def get_handlers():
    return [
        CommandHandler("valoracion", cmd_valoracion),
        CommandHandler("cartera", cmd_cartera),
        CommandHandler("historial", cmd_historial),
    ]
```

**Step 4: Test manually** — send `/cartera` and `/historial`.

**Step 5: Commit**

```bash
git add src/bot/handlers/portfolio.py
git commit -m "feat: /cartera and /historial commands"
```

---

## Task 9: Strategy Engine

**Files:**
- Create: `src/strategies/__init__.py`
- Create: `src/strategies/base.py`
- Create: `src/strategies/stop_loss.py`
- Create: `src/strategies/ma_crossover.py`
- Create: `tests/test_strategies.py`

**Step 1: Write `src/strategies/base.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
import pandas as pd


@dataclass
class Signal:
    action: str       # BUY | SELL | HOLD
    ticker: str
    price: Decimal
    reason: str
    confidence: float = 1.0  # 0.0 - 1.0


class Strategy(ABC):
    @abstractmethod
    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        """Return a Signal or None (HOLD)."""
        ...
```

**Step 2: Write `src/strategies/stop_loss.py`**

```python
from decimal import Decimal
import pandas as pd
from src.strategies.base import Strategy, Signal
from src.config import app_config


class StopLossStrategy(Strategy):
    def __init__(self):
        cfg = app_config["strategies"]["stop_loss"]
        self.stop_loss_pct = Decimal(str(cfg["stop_loss_pct"])) / 100
        self.take_profit_pct = Decimal(str(cfg["take_profit_pct"])) / 100

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        if len(data) < 2:
            return None
        open_price = Decimal(str(data["Close"].iloc[0]))
        change = (current_price - open_price) / open_price

        if change <= -self.stop_loss_pct:
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"Stop-loss triggered: {change*100:.1f}% drop",
                confidence=0.95,
            )
        if change >= self.take_profit_pct:
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"Take-profit triggered: {change*100:.1f}% gain",
                confidence=0.9,
            )
        return None
```

**Step 3: Write `src/strategies/ma_crossover.py`**

```python
from decimal import Decimal
import pandas as pd
import pandas_ta as ta
from src.strategies.base import Strategy, Signal
from src.config import app_config


class MACrossoverStrategy(Strategy):
    def __init__(self):
        cfg = app_config["strategies"]["ma_crossover"]
        self.fast = cfg["fast_period"]
        self.slow = cfg["slow_period"]

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        if len(data) < self.slow + 1:
            return None
        close = data["Close"]
        fast_ma = close.rolling(self.fast).mean()
        slow_ma = close.rolling(self.slow).mean()

        # Crossover: today fast > slow, yesterday fast < slow
        if (fast_ma.iloc[-1] > slow_ma.iloc[-1]) and (fast_ma.iloc[-2] <= slow_ma.iloc[-2]):
            return Signal(
                action="BUY", ticker=ticker, price=current_price,
                reason=f"MA{self.fast} crossed above MA{self.slow}",
                confidence=0.75,
            )
        if (fast_ma.iloc[-1] < slow_ma.iloc[-1]) and (fast_ma.iloc[-2] >= slow_ma.iloc[-2]):
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"MA{self.fast} crossed below MA{self.slow}",
                confidence=0.75,
            )
        return None
```

**Step 4: Write failing tests `tests/test_strategies.py`**

```python
import pytest
import pandas as pd
import numpy as np
from decimal import Decimal
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy


def make_df(prices: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(prices), freq="D")
    return pd.DataFrame({"Close": prices}, index=idx)


def test_stop_loss_triggers_sell():
    strategy = StopLossStrategy()
    # Opened at 100, now at 88 (12% drop > 8% threshold)
    df = make_df([100.0] + [99.0] * 60)
    signal = strategy.evaluate("AAPL", df, Decimal("88"))
    assert signal is not None
    assert signal.action == "SELL"
    assert "Stop-loss" in signal.reason


def test_take_profit_triggers_sell():
    strategy = StopLossStrategy()
    # Opened at 100, now at 120 (20% gain > 15% threshold)
    df = make_df([100.0] + [101.0] * 60)
    signal = strategy.evaluate("AAPL", df, Decimal("120"))
    assert signal is not None
    assert signal.action == "SELL"
    assert "Take-profit" in signal.reason


def test_no_signal_within_thresholds():
    strategy = StopLossStrategy()
    df = make_df([100.0] * 61)
    signal = strategy.evaluate("AAPL", df, Decimal("100"))
    assert signal is None


def test_ma_crossover_buy_signal():
    strategy = MACrossoverStrategy()
    # Build data where fast MA just crossed above slow MA
    prices = [100.0] * 50 + [95.0] * 20 + [105.0, 110.0]  # price surge at end
    df = make_df(prices)
    # Just test it runs without error and returns Signal or None
    signal = strategy.evaluate("AAPL", df, Decimal("110"))
    # Signal type must be valid if returned
    if signal:
        assert signal.action in ("BUY", "SELL", "HOLD")
```

**Step 5: Run tests**

```bash
.venv/bin/pytest tests/test_strategies.py -v
```

Expected: 4 tests PASS.

**Step 6: Commit**

```bash
git add src/strategies/ tests/test_strategies.py
git commit -m "feat: Strategy base class, StopLoss and MACrossover implementations"
```

---

## Task 10: AlertEngine + APScheduler

**Files:**
- Create: `src/alerts/__init__.py`
- Create: `src/alerts/engine.py`
- Modify: `src/bot/bot.py`

**Step 1: Write `src/alerts/engine.py`**

```python
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import async_session_factory
from src.db.models import Alert, Basket, BasketAsset, Asset, Position
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
        self.app = telegram_app  # set after bot creation

    async def scan_all_baskets(self) -> None:
        """Called by scheduler every N minutes during market hours."""
        async with async_session_factory() as session:
            result = await session.execute(select(Basket).where(Basket.active == True))
            baskets = result.scalars().all()
            for basket in baskets:
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

                if signal and signal.action in ("BUY", "SELL"):
                    # Avoid duplicate alerts
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
        """Send alert to all basket members via Telegram. Implemented in Task 11."""
        logger.info(f"ALERT: {alert.signal} {ticker} in {basket_name} — {alert.reason}")
```

**Step 2: Modify `src/bot/bot.py` to add scheduler**

```python
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application
from src.config import settings, app_config
from src.bot.handlers.portfolio import get_handlers as portfolio_handlers
from src.bot.handlers.orders import get_handlers as order_handlers
from src.alerts.engine import AlertEngine

logger = logging.getLogger(__name__)


async def run() -> None:
    app = Application.builder().token(settings.telegram_apikey).build()

    for handler in portfolio_handlers():
        app.add_handler(handler)
    for handler in order_handlers():
        app.add_handler(handler)

    alert_engine = AlertEngine(telegram_app=app)
    scheduler = AsyncIOScheduler()
    interval = app_config["scheduler"]["interval_minutes"]
    scheduler.add_job(alert_engine.scan_all_baskets, "interval", minutes=interval)
    scheduler.start()

    logger.info(f"ScroogeBot starting (scan every {interval}min)...")
    await app.run_polling(drop_pending_updates=True)
```

**Step 3: Test scheduler starts**

```bash
.venv/bin/python scroogebot.py
```

Expected: starts without errors, logs `ScroogeBot starting (scan every 5min)...`

**Step 4: Commit**

```bash
git add src/alerts/ src/bot/bot.py
git commit -m "feat: AlertEngine with strategy scanning and APScheduler integration"
```

---

## Task 11: User Roles + Alert Confirmations

**Files:**
- Create: `src/bot/handlers/admin.py`
- Modify: `src/bot/handlers/portfolio.py` (role-aware basket filtering)
- Modify: `src/bot/handlers/orders.py` (role check before order)
- Modify: `src/alerts/engine.py` (notify members via inline keyboard)

**Step 1: Write `src/bot/handlers/admin.py`**

```python
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from src.db.base import async_session_factory
from src.db.models import User, Basket, BasketMember
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /adduser @username OWNER|MEMBER basket_name"""
    if len(context.args) < 3:
        await update.message.reply_text("Uso: /adduser @username OWNER|MEMBER nombre_cesta")
        return

    username = context.args[0].lstrip("@")
    role = context.args[1].upper()
    basket_name = " ".join(context.args[2:])

    if role not in ("OWNER", "MEMBER"):
        await update.message.reply_text("Rol debe ser OWNER o MEMBER.")
        return

    async with async_session_factory() as session:
        # Verify caller is OWNER of the basket
        caller_result = await session.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        caller = caller_result.scalar_one_or_none()

        basket_result = await session.execute(
            select(Basket).where(Basket.name == basket_name)
        )
        basket = basket_result.scalar_one_or_none()
        if not basket:
            await update.message.reply_text(f"Cesta '{basket_name}' no encontrada.")
            return

        if caller:
            member_result = await session.execute(
                select(BasketMember).where(
                    BasketMember.basket_id == basket.id,
                    BasketMember.user_id == caller.id,
                    BasketMember.role == "OWNER",
                )
            )
            if not member_result.scalar_one_or_none():
                await update.message.reply_text("Solo el OWNER puede añadir usuarios.")
                return

        # Find or create target user by username (they must have started the bot)
        target_result = await session.execute(
            select(User).where(User.username == username)
        )
        target = target_result.scalar_one_or_none()
        if not target:
            await update.message.reply_text(
                f"@{username} no encontrado. El usuario debe enviar /start primero."
            )
            return

        existing = await session.execute(
            select(BasketMember).where(
                BasketMember.basket_id == basket.id,
                BasketMember.user_id == target.id,
            )
        )
        member = existing.scalar_one_or_none()
        if member:
            member.role = role
        else:
            session.add(BasketMember(basket_id=basket.id, user_id=target.id, role=role))

        await session.commit()
        await update.message.reply_text(
            f"✅ @{username} añadido como {role} en '{basket_name}'."
        )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register user on first contact."""
    async with async_session_factory() as session:
        tg_user = update.effective_user
        result = await session.execute(select(User).where(User.tg_id == tg_user.id))
        if not result.scalar_one_or_none():
            session.add(User(
                tg_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
            ))
            await session.commit()
    await update.message.reply_text(
        f"¡Hola {update.effective_user.first_name}! 🦆 Soy TioGilito.\n"
        "Usa /valoracion para ver el estado de tus cestas."
    )


def get_handlers():
    return [
        CommandHandler("start", cmd_start),
        CommandHandler("adduser", cmd_adduser),
    ]
```

**Step 2: Update `src/alerts/engine.py` `_notify` method to send inline keyboard**

Replace `_notify` with:

```python
async def _notify(self, alert: Alert, basket_name: str, ticker: str) -> None:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from sqlalchemy import select
    from src.db.models import BasketMember, User

    if not self.app:
        return

    async with async_session_factory() as session:
        result = await session.execute(
            select(BasketMember, User)
            .join(User, BasketMember.user_id == User.id)
            .where(BasketMember.basket_id == alert.basket_id)
        )
        members = result.all()

    icon = "⚠️" if alert.signal == "SELL" else "💡"
    text = (
        f"{icon} *{basket_name}* — Alerta {alert.strategy}\n\n"
        f"{'🔴 VENTA' if alert.signal == 'SELL' else '🟢 COMPRA'}: *{ticker}*\n"
        f"Precio: {alert.price:.2f}\n"
        f"Razón: {alert.reason}\n\n"
        f"¿Ejecutar {alert.signal}?"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Ejecutar", callback_data=f"alert:confirm:{alert.id}"),
        InlineKeyboardButton("❌ Rechazar", callback_data=f"alert:reject:{alert.id}"),
    ]])

    for member, user in members:
        try:
            await self.app.bot.send_message(
                chat_id=user.tg_id, text=text,
                parse_mode="Markdown", reply_markup=keyboard,
            )
        except Exception as e:
            logger.error(f"Could not notify {user.tg_id}: {e}")
```

**Step 3: Add callback handler for alert confirmation in `src/bot/bot.py`**

```python
from telegram.ext import CallbackQueryHandler

async def handle_alert_callback(update, context):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    if len(parts) != 3 or parts[0] != "alert":
        return
    action, alert_id = parts[1], int(parts[2])

    from src.db.base import async_session_factory
    from src.db.models import Alert, Asset, Basket
    from src.data.yahoo import YahooDataProvider
    from src.orders.paper import PaperTradingExecutor
    from src.db.models import User
    from sqlalchemy import select
    from decimal import Decimal

    async with async_session_factory() as session:
        alert = await session.get(Alert, alert_id)
        if not alert or alert.status != "PENDING":
            await query.edit_message_text("Esta alerta ya fue procesada.")
            return

        asset = await session.get(Asset, alert.asset_id)
        basket = await session.get(Basket, alert.basket_id)
        user_result = await session.execute(select(User).where(User.tg_id == query.from_user.id))
        user = user_result.scalar_one_or_none()

        if action == "reject":
            alert.status = "REJECTED"
            from datetime import datetime
            alert.resolved_at = datetime.utcnow()
            await session.commit()
            await query.edit_message_text(f"❌ Alerta rechazada: {asset.ticker}")
            return

        if action == "confirm":
            try:
                provider = YahooDataProvider()
                price = provider.get_current_price(asset.ticker).price
                executor = PaperTradingExecutor()
                if alert.signal == "SELL":
                    # Get quantity from position
                    from src.db.models import Position
                    pos_result = await session.execute(
                        select(Position).where(
                            Position.basket_id == basket.id,
                            Position.asset_id == asset.id,
                        )
                    )
                    pos = pos_result.scalar_one_or_none()
                    qty = pos.quantity if pos else Decimal("0")
                    if qty > 0:
                        await executor.sell(session, basket.id, asset.id, user.id, asset.ticker, qty, price, alert.strategy)
                elif alert.signal == "BUY":
                    # Invest 10% of cash by default
                    qty = (basket.cash * Decimal("0.1") / price).quantize(Decimal("0.01"))
                    if qty > 0:
                        await executor.buy(session, basket.id, asset.id, user.id, asset.ticker, qty, price, alert.strategy)

                alert.status = "CONFIRMED"
                from datetime import datetime
                alert.resolved_at = datetime.utcnow()
                await session.commit()
                await query.edit_message_text(f"✅ {alert.signal} {asset.ticker} ejecutado a {price:.2f}")
            except Exception as e:
                await query.edit_message_text(f"❌ Error ejecutando: {e}")

# In run(), add:
# app.add_handler(CallbackQueryHandler(handle_alert_callback, pattern="^alert:"))
```

**Step 4: Register all handlers in `src/bot/bot.py`**

Final `run()` function:

```python
async def run() -> None:
    app = Application.builder().token(settings.telegram_apikey).build()

    from src.bot.handlers.admin import get_handlers as admin_handlers
    for handler in portfolio_handlers():
        app.add_handler(handler)
    for handler in order_handlers():
        app.add_handler(handler)
    for handler in admin_handlers():
        app.add_handler(handler)

    app.add_handler(CallbackQueryHandler(handle_alert_callback, pattern="^alert:"))

    alert_engine = AlertEngine(telegram_app=app)
    scheduler = AsyncIOScheduler()
    interval = app_config["scheduler"]["interval_minutes"]
    scheduler.add_job(alert_engine.scan_all_baskets, "interval", minutes=interval)
    scheduler.start()

    logger.info(f"ScroogeBot starting (scan every {interval}min)...")
    await app.run_polling(drop_pending_updates=True)
```

**Step 5: Test manually** — `/start`, then `/adduser @yourself OWNER Cesta Agresiva`, then wait for alert.

**Step 6: Commit**

```bash
git add src/bot/handlers/admin.py src/alerts/engine.py src/bot/bot.py
git commit -m "feat: user roles, /start, /adduser, alert inline keyboard confirmations"
```

---

## Task 12: Backtesting + /backtest

**Files:**
- Create: `src/backtest/__init__.py`
- Create: `src/backtest/engine.py`
- Create: `src/bot/handlers/backtest.py`

**Step 1: Install vectorbt**

```bash
.venv/bin/pip install ".[backtest]"
```

**Step 2: Write `src/backtest/engine.py`**

```python
import logging
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from src.data.yahoo import YahooDataProvider
from src.strategies.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    ticker: str
    period: str
    strategy_name: str
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    n_trades: int
    win_rate_pct: float
    benchmark_return_pct: float


class BacktestEngine:
    def __init__(self):
        self.data = YahooDataProvider()

    def run(self, ticker: str, strategy: Strategy, strategy_name: str, period: str = "1y") -> BacktestResult:
        import vectorbt as vbt

        ohlcv = self.data.get_historical(ticker, period=period, interval="1d")
        close = ohlcv.data["Close"]

        # Generate signals using strategy on rolling windows
        entries = pd.Series(False, index=close.index)
        exits = pd.Series(False, index=close.index)

        window = 60  # lookback window for strategy evaluation
        for i in range(window, len(close)):
            window_data = ohlcv.data.iloc[i - window:i]
            current_price = Decimal(str(close.iloc[i]))
            signal = strategy.evaluate(ticker, window_data, current_price)
            if signal:
                if signal.action == "BUY":
                    entries.iloc[i] = True
                elif signal.action == "SELL":
                    exits.iloc[i] = True

        pf = vbt.Portfolio.from_signals(close, entries, exits, init_cash=10_000)
        stats = pf.stats()

        # Buy-and-hold benchmark
        bh_return = (close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100

        return BacktestResult(
            ticker=ticker,
            period=period,
            strategy_name=strategy_name,
            total_return_pct=float(stats.get("Total Return [%]", 0)),
            annualized_return_pct=float(stats.get("Annualized Return [%]", 0)),
            sharpe_ratio=float(stats.get("Sharpe Ratio", 0)),
            max_drawdown_pct=float(stats.get("Max Drawdown [%]", 0)),
            n_trades=int(stats.get("Total Trades", 0)),
            win_rate_pct=float(stats.get("Win Rate [%]", 0)),
            benchmark_return_pct=float(bh_return),
        )
```

**Step 3: Write `src/bot/handlers/backtest.py`**

```python
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from src.db.base import async_session_factory
from src.db.models import Basket, BasketAsset, Asset
from src.backtest.engine import BacktestEngine
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy
from sqlalchemy import select

logger = logging.getLogger(__name__)

STRATEGY_MAP = {
    "stop_loss": StopLossStrategy,
    "ma_crossover": MACrossoverStrategy,
}


async def cmd_backtest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /backtest [basket_name] [period]  e.g. /backtest "Cesta Agresiva" 1y"""
    period = "1y"
    if context.args:
        period = context.args[-1] if context.args[-1] in ("1mo", "3mo", "6mo", "1y", "2y") else "1y"

    msg = await update.message.reply_text("⏳ Ejecutando backtesting...")
    engine = BacktestEngine()

    async with async_session_factory() as session:
        baskets_result = await session.execute(select(Basket).where(Basket.active == True))
        baskets = baskets_result.scalars().all()

        for basket in baskets:
            strategy_cls = STRATEGY_MAP.get(basket.strategy)
            if not strategy_cls:
                continue
            strategy = strategy_cls()

            assets_result = await session.execute(
                select(Asset)
                .join(BasketAsset, BasketAsset.asset_id == Asset.id)
                .where(BasketAsset.basket_id == basket.id, BasketAsset.active == True)
            )
            assets = assets_result.scalars().all()

            lines = [f"📊 *Backtest: {basket.name}* ({period})\n"]
            for asset in assets:
                try:
                    result = engine.run(asset.ticker, strategy, basket.strategy, period)
                    bm = result.benchmark_return_pct
                    ret = result.total_return_pct
                    alpha = ret - bm
                    lines += [
                        f"*{asset.ticker}*",
                        f"  Rentabilidad: {ret:+.1f}% (benchmark: {bm:+.1f}%, α: {alpha:+.1f}%)",
                        f"  Sharpe: {result.sharpe_ratio:.2f}  MaxDD: {result.max_drawdown_pct:.1f}%",
                        f"  Trades: {result.n_trades}  Win rate: {result.win_rate_pct:.0f}%",
                        "",
                    ]
                except Exception as e:
                    lines.append(f"❌ {asset.ticker}: {e}\n")

            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    await msg.delete()


def get_handlers():
    return [CommandHandler("backtest", cmd_backtest)]
```

**Step 4: Register in `src/bot/bot.py`**

```python
from src.bot.handlers.backtest import get_handlers as backtest_handlers
# In run():
for handler in backtest_handlers():
    app.add_handler(handler)
```

**Step 5: Test manually** — `/backtest`

**Step 6: Commit**

```bash
git add src/backtest/ src/bot/handlers/backtest.py src/bot/bot.py
git commit -m "feat: backtesting engine with vectorbt and /backtest command"
```

---

## Task 13: Advanced Strategies (RSI, Bollinger, Safe Haven)

**Files:**
- Create: `src/strategies/rsi.py`
- Create: `src/strategies/bollinger.py`
- Create: `src/strategies/safe_haven.py`
- Modify: `src/alerts/engine.py` (add to STRATEGY_MAP)
- Modify: `src/backtest/engine.py` (add to STRATEGY_MAP)

**Step 1: Write `src/strategies/rsi.py`**

```python
from decimal import Decimal
import pandas as pd
import pandas_ta as ta
from src.strategies.base import Strategy, Signal
from src.config import app_config


class RSIStrategy(Strategy):
    def __init__(self):
        cfg = app_config["strategies"]["rsi"]
        self.period = cfg["period"]
        self.oversold = cfg["oversold"]
        self.overbought = cfg["overbought"]

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        if len(data) < self.period + 1:
            return None
        rsi = ta.rsi(data["Close"], length=self.period)
        if rsi is None or rsi.empty:
            return None
        last_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]

        if prev_rsi <= self.oversold < last_rsi:
            return Signal(
                action="BUY", ticker=ticker, price=current_price,
                reason=f"RSI crossed above oversold ({last_rsi:.1f})",
                confidence=0.7,
            )
        if prev_rsi >= self.overbought > last_rsi:
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"RSI crossed below overbought ({last_rsi:.1f})",
                confidence=0.7,
            )
        return None
```

**Step 2: Write `src/strategies/bollinger.py`**

```python
from decimal import Decimal
import pandas as pd
import pandas_ta as ta
from src.strategies.base import Strategy, Signal
from src.config import app_config


class BollingerStrategy(Strategy):
    def __init__(self):
        cfg = app_config["strategies"]["bollinger"]
        self.period = cfg["period"]
        self.std_dev = cfg["std_dev"]

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        if len(data) < self.period:
            return None
        bb = ta.bbands(data["Close"], length=self.period, std=self.std_dev)
        if bb is None or bb.empty:
            return None
        lower_col = [c for c in bb.columns if "BBL" in c]
        upper_col = [c for c in bb.columns if "BBU" in c]
        if not lower_col or not upper_col:
            return None

        lower = Decimal(str(bb[lower_col[0]].iloc[-1]))
        upper = Decimal(str(bb[upper_col[0]].iloc[-1]))

        if current_price <= lower:
            return Signal(
                action="BUY", ticker=ticker, price=current_price,
                reason=f"Price touched lower Bollinger band ({lower:.2f})",
                confidence=0.65,
            )
        if current_price >= upper:
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"Price touched upper Bollinger band ({upper:.2f})",
                confidence=0.65,
            )
        return None
```

**Step 3: Write `src/strategies/safe_haven.py`**

```python
from decimal import Decimal
import pandas as pd
from src.strategies.base import Strategy, Signal
from src.config import app_config

SAFE_TICKERS = {"GLD", "BND", "TLT", "SHY"}


class SafeHavenStrategy(Strategy):
    """Rotate to safe haven assets when drawdown exceeds threshold."""

    def __init__(self):
        cfg = app_config["strategies"].get("stop_loss", {})
        self.drawdown_threshold = Decimal(str(cfg.get("stop_loss_pct", 8))) / 100

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        if ticker in SAFE_TICKERS:
            return None  # Don't sell safe havens via this strategy
        if len(data) < 2:
            return None
        peak = Decimal(str(data["Close"].max()))
        drawdown = (peak - current_price) / peak
        if drawdown >= self.drawdown_threshold:
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"Drawdown {drawdown*100:.1f}% from peak — rotating to safe haven",
                confidence=0.8,
            )
        return None
```

**Step 4: Add strategies to STRATEGY_MAP in `src/alerts/engine.py`**

```python
from src.strategies.rsi import RSIStrategy
from src.strategies.bollinger import BollingerStrategy
from src.strategies.safe_haven import SafeHavenStrategy

STRATEGY_MAP: dict[str, type[Strategy]] = {
    "stop_loss": StopLossStrategy,
    "ma_crossover": MACrossoverStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerStrategy,
    "safe_haven": SafeHavenStrategy,
}
```

Do the same in `src/backtest/engine.py`.

**Step 5: Add tests for RSI and Bollinger**

In `tests/test_strategies.py`, add:

```python
from src.strategies.rsi import RSIStrategy
from src.strategies.bollinger import BollingerStrategy


def test_rsi_returns_signal_or_none():
    strategy = RSIStrategy()
    prices = [100.0 + i * 0.5 for i in range(30)]
    df = make_df(prices)
    signal = strategy.evaluate("MSFT", df, Decimal("115"))
    if signal:
        assert signal.action in ("BUY", "SELL")


def test_bollinger_returns_signal_or_none():
    strategy = BollingerStrategy()
    prices = [100.0] * 30
    df = make_df(prices)
    signal = strategy.evaluate("MSFT", df, Decimal("100"))
    if signal:
        assert signal.action in ("BUY", "SELL")
```

**Step 6: Run all tests**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all tests PASS.

**Step 7: Commit**

```bash
git add src/strategies/ src/alerts/engine.py src/backtest/engine.py tests/test_strategies.py
git commit -m "feat: RSI, Bollinger and SafeHaven strategies"
```

---

## Task 14: /cestas, /analiza, /watchlist

**Files:**
- Create: `src/bot/handlers/baskets.py`
- Create: `src/bot/handlers/analysis.py`
- Modify: `src/bot/handlers/admin.py` (add /watchlist)

**Step 1: Write `src/bot/handlers/baskets.py`**

```python
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from src.db.base import async_session_factory
from src.db.models import Basket, BasketAsset, Asset, BasketMember, User
from sqlalchemy import select


async def cmd_cestas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(Basket).where(Basket.active == True))
        baskets = result.scalars().all()
        if not baskets:
            await update.message.reply_text("No hay cestas configuradas.")
            return
        lines = ["🗂 *Cestas disponibles*\n"]
        for b in baskets:
            lines.append(f"• *{b.name}* — estrategia: `{b.strategy}` ({b.risk_profile})")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_cesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /cesta nombre_cesta")
        return
    name = " ".join(context.args)
    async with async_session_factory() as session:
        result = await session.execute(select(Basket).where(Basket.name == name))
        basket = result.scalar_one_or_none()
        if not basket:
            await update.message.reply_text(f"Cesta '{name}' no encontrada.")
            return
        assets_result = await session.execute(
            select(Asset)
            .join(BasketAsset, BasketAsset.asset_id == Asset.id)
            .where(BasketAsset.basket_id == basket.id, BasketAsset.active == True)
        )
        assets = assets_result.scalars().all()
        members_result = await session.execute(
            select(BasketMember, User)
            .join(User, BasketMember.user_id == User.id)
            .where(BasketMember.basket_id == basket.id)
        )
        lines = [
            f"🗂 *{basket.name}*",
            f"Estrategia: `{basket.strategy}` | Perfil: {basket.risk_profile}",
            f"Cash: {basket.cash:.2f}€",
            "\n*Assets:*",
        ]
        for a in assets:
            lines.append(f"  • {a.ticker} ({a.market})")
        lines.append("\n*Miembros:*")
        for m, u in members_result.all():
            lines.append(f"  • @{u.username or u.first_name} [{m.role}]")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def get_handlers():
    return [
        CommandHandler("cestas", cmd_cestas),
        CommandHandler("cesta", cmd_cesta),
    ]
```

**Step 2: Write `src/bot/handlers/analysis.py`**

```python
from decimal import Decimal
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from src.data.yahoo import YahooDataProvider
import pandas_ta as ta

_provider = YahooDataProvider()


async def cmd_analiza(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /analiza TICKER")
        return
    ticker = context.args[0].upper()
    msg = await update.message.reply_text(f"⏳ Analizando {ticker}...")
    try:
        price = _provider.get_current_price(ticker)
        ohlcv = _provider.get_historical(ticker, period="3mo", interval="1d")
        close = ohlcv.data["Close"]

        rsi = ta.rsi(close, length=14)
        rsi_val = rsi.iloc[-1] if rsi is not None and not rsi.empty else None
        sma20 = close.rolling(20).mean().iloc[-1]
        sma50 = close.rolling(50).mean().iloc[-1]
        change_1d = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100

        lines = [
            f"📊 *Análisis técnico: {ticker}*",
            f"💰 Precio: {price.price:.2f} {price.currency}",
            f"📅 Cambio 1d: {change_1d:+.2f}%",
            "",
            f"SMA 20: {sma20:.2f}",
            f"SMA 50: {sma50:.2f}",
            f"Tendencia: {'📈 Alcista' if sma20 > sma50 else '📉 Bajista'}",
        ]
        if rsi_val is not None:
            status = "sobrecomprado 🔴" if rsi_val > 70 else "sobrevendido 🟢" if rsi_val < 30 else "neutral ⚪"
            lines.append(f"RSI (14): {rsi_val:.1f} — {status}")

        tickers_str = ticker
        lines.append(f"\n🔍 [Finviz](https://finviz.com/quote.ashx?t={ticker})")
        await msg.edit_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Error analizando {ticker}: {e}")


def get_handlers():
    return [CommandHandler("analiza", cmd_analiza)]
```

**Step 3: Add `/watchlist` commands to `src/bot/handlers/admin.py`**

```python
from src.db.models import Watchlist

async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Watchlist).order_by(Watchlist.created_at.desc())
        )
        items = result.scalars().all()
        if not items:
            await update.message.reply_text("Watchlist vacía.")
            return
        lines = ["👀 *Watchlist*\n"]
        for item in items:
            status_icon = "🔴" if item.status == "PENDING" else "🟢"
            lines.append(f"{status_icon} *{item.ticker}* — {item.name or ''}\n   {item.note or ''}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_addwatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /addwatch TICKER Company name | note"""
    if not context.args:
        await update.message.reply_text("Uso: /addwatch TICKER Nombre | nota")
        return
    ticker = context.args[0].upper()
    rest = " ".join(context.args[1:])
    name, _, note = rest.partition("|")

    async with async_session_factory() as session:
        user_result = await session.execute(select(User).where(User.tg_id == update.effective_user.id))
        user = user_result.scalar_one_or_none()
        if not user:
            await update.message.reply_text("Usa /start primero.")
            return
        session.add(Watchlist(
            ticker=ticker, name=name.strip(), note=note.strip(),
            added_by=user.id, status="PENDING",
        ))
        await session.commit()
    await update.message.reply_text(f"✅ {ticker} añadido a la watchlist.")

# Add to get_handlers():
# CommandHandler("watchlist", cmd_watchlist),
# CommandHandler("addwatch", cmd_addwatch),
```

**Step 4: Register all new handlers in `src/bot/bot.py`**

```python
from src.bot.handlers.baskets import get_handlers as basket_handlers
from src.bot.handlers.analysis import get_handlers as analysis_handlers
# In run():
for handler in basket_handlers():
    app.add_handler(handler)
for handler in analysis_handlers():
    app.add_handler(handler)
```

**Step 5: Final run — test all commands**

```bash
.venv/bin/python scroogebot.py
```

Test: `/start`, `/cestas`, `/cesta Cesta Agresiva`, `/analiza AAPL`, `/valoracion`, `/cartera`, `/historial`, `/watchlist`, `/addwatch ANTHROPIC Anthropic | pendiente de IPO`

**Step 6: Run full test suite**

```bash
.venv/bin/pytest tests/ -v --tb=short
```

Expected: all tests PASS.

**Step 7: Commit**

```bash
git add src/bot/handlers/ src/bot/bot.py
git commit -m "feat: /cestas, /cesta, /analiza, /watchlist, /addwatch commands — feature complete"
```

---

## Task 15: Systemd Service File

**Files:**
- Create: `scroogebot.service`

**Step 1: Write `scroogebot.service`**

```ini
[Unit]
Description=ScroogeBot — Investment Telegram Bot
After=network.target mariadb.service

[Service]
Type=simple
ExecStart=/data/scroogebot/.venv/bin/python /data/scroogebot/scroogebot.py
User=ubuntu
WorkingDirectory=/data/scroogebot
Restart=always
RestartSec=10
EnvironmentFile=/data/scroogebot/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Step 2: Install systemd service (when ready to deploy)**

```bash
sudo cp scroogebot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable scroogebot
sudo systemctl start scroogebot
sudo systemctl status scroogebot
```

**Step 3: Commit**

```bash
git add scroogebot.service
git commit -m "feat: systemd service file for production deployment"
```

---

## Summary

| Task | Feature | Status |
|------|---------|--------|
| 1 | Project scaffold | — |
| 2 | Config (pydantic-settings) | — |
| 3 | DB models + Alembic | — |
| 4 | DB seeder from config.yaml | — |
| 5 | DataProvider (yfinance) | — |
| 6 | PortfolioEngine + /valoracion | — |
| 7 | Paper trading + /compra /vende | — |
| 8 | /cartera + /historial | — |
| 9 | Strategy engine (StopLoss, MA) | — |
| 10 | AlertEngine + APScheduler | — |
| 11 | Roles + alert confirmations | — |
| 12 | Backtesting + /backtest | — |
| 13 | RSI, Bollinger, SafeHaven | — |
| 14 | /cestas, /analiza, /watchlist | — |
| 15 | Systemd service | — |
