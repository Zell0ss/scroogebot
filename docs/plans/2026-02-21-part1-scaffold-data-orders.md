# ScroogeBot — Part 1: Scaffold, Data & Orders

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Slices 1-3 — working bot that scaffolds the project, fetches real market data, and executes paper trading orders via `/valoracion`, `/compra`, `/vende`.

**Architecture:** pydantic-settings for config, SQLAlchemy 2.0 async + aiomysql for MariaDB, YahooDataProvider for prices, PaperTradingExecutor for orders.

**Tech Stack:** Python 3.11, python-telegram-bot v20+, SQLAlchemy 2.0, aiomysql, Alembic, yfinance, pydantic-settings, PyYAML.

---

## Environment

All credentials are in `/data/scroogebot/.env`. Never hardcode them.
Run all commands from `/data/scroogebot/`. Venv: `.venv/bin/python`.

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
    "pymysql>=1.1",
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

**Step 4: Write `scroogebot.py`**

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

**Step 5: Write `src/__init__.py`** (empty file)

**Step 6: Install dependencies**

```bash
.venv/bin/pip install -e ".[dev]"
```

Expected: packages install without errors.

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
from typing import Any

import yaml
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

**Step 2: Write `tests/__init__.py`** (empty file)

**Step 3: Write `tests/test_config.py`**

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

**Step 4: Run tests**

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
- Create: `alembic.ini` (via `alembic init`)
- Edit: `src/db/migrations/env.py`

**Step 1: Write `src/db/__init__.py`** (empty file)

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
```

**Step 4: Initialize Alembic**

```bash
.venv/bin/alembic init src/db/migrations
```

**Step 5: Replace contents of `src/db/migrations/env.py`**

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

**Step 6: Generate and apply migration**

```bash
.venv/bin/alembic revision --autogenerate -m "initial schema"
.venv/bin/alembic upgrade head
```

Expected: no errors, tables created in MariaDB.

**Step 7: Verify tables**

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

Expected: prints all 9 table names.

**Step 8: Commit**

```bash
git add src/db/ alembic.ini
git commit -m "feat: SQLAlchemy models and Alembic initial migration"
```

---

## Task 4: DB Seeder

**Files:**
- Create: `src/db/seed.py`

**Step 1: Write `src/db/seed.py`**

```python
"""Seed baskets and assets from config/config.yaml. Idempotent."""
import asyncio
from src.config import app_config
from src.db.base import async_session_factory
from src.db.models import Asset, Basket, BasketAsset
from sqlalchemy import select


async def seed() -> None:
    async with async_session_factory() as session:
        for basket_cfg in app_config["baskets"]:
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
git commit -m "feat: DB seeder from config.yaml"
```

---

## Task 5: DataProvider (yfinance)

**Files:**
- Create: `src/data/__init__.py`
- Create: `src/data/models.py`
- Create: `src/data/base.py`
- Create: `src/data/yahoo.py`
- Create: `tests/test_data.py`

**Step 1: Write `src/data/__init__.py`** (empty)

**Step 2: Write `src/data/models.py`**

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

**Step 3: Write `src/data/base.py`**

```python
from abc import ABC, abstractmethod
from decimal import Decimal
from src.data.models import Price, OHLCV


class DataProvider(ABC):
    @abstractmethod
    def get_current_price(self, ticker: str) -> Price: ...

    @abstractmethod
    def get_historical(self, ticker: str, period: str = "3mo", interval: str = "1d") -> OHLCV: ...

    def get_fx_rate(self, from_currency: str, to_currency: str) -> Decimal:
        if from_currency == to_currency:
            return Decimal("1")
        fx_ticker = f"{from_currency}{to_currency}=X"
        return self.get_current_price(fx_ticker).price
```

**Step 4: Write `src/data/yahoo.py`**

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
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return OHLCV(ticker=ticker, data=df)
```

**Step 5: Write `tests/test_data.py`**

```python
"""Integration tests — requires network access."""
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

**Step 6: Run tests**

```bash
.venv/bin/pytest tests/test_data.py -v
```

Expected: 3 tests PASS.

**Step 7: Commit**

```bash
git add src/data/ tests/test_data.py
git commit -m "feat: DataProvider abstraction with YahooDataProvider"
```

---

## Task 6: PortfolioEngine + `/valoracion`

**Files:**
- Create: `src/portfolio/__init__.py`
- Create: `src/portfolio/models.py`
- Create: `src/portfolio/engine.py`
- Create: `src/bot/__init__.py`
- Create: `src/bot/handlers/__init__.py`
- Create: `src/bot/handlers/portfolio.py`
- Create: `src/bot/bot.py`

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
```

**Step 3: Write `src/bot/handlers/portfolio.py`**

```python
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Basket, Position, Asset, Order
from src.data.yahoo import YahooDataProvider
from src.portfolio.engine import PortfolioEngine

logger = logging.getLogger(__name__)
_provider = YahooDataProvider()
_engine = PortfolioEngine(_provider)


def _fmt(val, decimals=2) -> str:
    return f"{val:,.{decimals}f}"


def _arrow(pnl) -> str:
    return "📈" if pnl >= 0 else "📉"


async def cmd_valoracion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(Basket).where(Basket.active == True))
        baskets = result.scalars().all()
        if not baskets:
            await update.message.reply_text("No hay cestas configuradas.")
            return
        if context.args:
            name_filter = " ".join(context.args).lower()
            baskets = [b for b in baskets if name_filter in b.name.lower()]

        for basket in baskets:
            msg = await update.message.reply_text(f"⏳ Calculando {basket.name}...")
            try:
                val = await _engine.get_valuation(session, basket.id)
                tickers = ",".join(p.ticker for p in val.positions)
                finviz_url = f"https://finviz.com/screener.ashx?v=111&t={tickers}" if tickers else ""
                sign = lambda v: "+" if v >= 0 else ""
                lines = [
                    f"📊 *{val.basket_name}* — {datetime.now().strftime('%d %b %Y %H:%M')}",
                    "",
                    f"💼 Capital invertido: {_fmt(val.total_invested)}€",
                    f"💰 Valor actual:      {_fmt(val.total_value)}€",
                    f"{_arrow(val.total_pnl)} P&L total: {sign(val.total_pnl)}{_fmt(val.total_pnl)}€ ({sign(val.total_pnl_pct)}{_fmt(val.total_pnl_pct)}%)",
                    "", "─" * 33,
                ]
                for p in val.positions:
                    sym = p.currency if p.currency != "EUR" else "€"
                    lines.append(
                        f"{p.ticker:<8} {_fmt(p.quantity, 0)} × {sym}{_fmt(p.current_price)} = {_fmt(p.market_value)}€  {_arrow(p.pnl)} {sign(p.pnl_pct)}{_fmt(p.pnl_pct)}%"
                    )
                lines += ["─" * 33, f"💵 Cash disponible: {_fmt(val.cash)}€"]
                if finviz_url:
                    lines.append(f"\n🔍 [Detalle Finviz]({finviz_url})")
                await msg.edit_text("\n".join(lines), parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Valuation error basket {basket.id}: {e}")
                await msg.edit_text(f"❌ Error calculando {basket.name}: {e}")


async def cmd_cartera(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(Basket).where(Basket.active == True))
        for basket in result.scalars().all():
            rows = (await session.execute(
                select(Position, Asset).join(Asset, Position.asset_id == Asset.id)
                .where(Position.basket_id == basket.id, Position.quantity > 0)
            )).all()
            if not rows:
                await update.message.reply_text(f"*{basket.name}*: sin posiciones.", parse_mode="Markdown")
                continue
            lines = [f"💼 *{basket.name}*\n"]
            for pos, asset in rows:
                lines.append(f"{asset.ticker:<8} {_fmt(pos.quantity, 4)} acc @ {_fmt(pos.avg_price)}")
            lines.append(f"\n💵 Cash: {_fmt(basket.cash)}€")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(Basket).where(Basket.active == True))
        for basket in result.scalars().all():
            rows = (await session.execute(
                select(Order, Asset).join(Asset, Order.asset_id == Asset.id)
                .where(Order.basket_id == basket.id)
                .order_by(Order.created_at.desc()).limit(10)
            )).all()
            if not rows:
                await update.message.reply_text(f"*{basket.name}*: sin órdenes.", parse_mode="Markdown")
                continue
            lines = [f"📋 *{basket.name}* — Últimas 10 órdenes\n"]
            for order, asset in rows:
                icon = "🟢" if order.type == "BUY" else "🔴"
                dt = order.created_at.strftime("%d/%m %H:%M")
                lines.append(f"{icon} {dt} {order.type} {_fmt(order.quantity, 2)} {asset.ticker} @ {_fmt(order.price)}")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def get_handlers():
    return [
        CommandHandler("valoracion", cmd_valoracion),
        CommandHandler("cartera", cmd_cartera),
        CommandHandler("historial", cmd_historial),
    ]
```

**Step 4: Write `src/bot/bot.py`** (minimal, grows with each slice)

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

**Step 5: Write `src/bot/__init__.py`** and `src/bot/handlers/__init__.py`** (both empty)

**Step 6: Test manually**

```bash
.venv/bin/python scroogebot.py
```

Send `/valoracion` to the bot in Telegram. Expected: "No hay cestas" or valuation if seed was run.
Stop with Ctrl+C.

**Step 7: Commit**

```bash
git add src/portfolio/ src/bot/
git commit -m "feat: PortfolioEngine + /valoracion, /cartera, /historial"
```

---

## Task 7: Paper Trading + `/compra` `/vende`

**Files:**
- Create: `src/orders/__init__.py`
- Create: `src/orders/base.py`
- Create: `src/orders/paper.py`
- Create: `src/bot/handlers/orders.py`
- Create: `tests/test_orders.py`

**Step 1: Write `src/orders/__init__.py`** (empty)

**Step 2: Write `src/orders/base.py`**

```python
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
async def test_buy_deducts_cash(executor):
    basket = MagicMock(cash=Decimal("10000"), id=1)
    session = AsyncMock()
    session.get.return_value = basket
    session.execute.return_value.scalar_one_or_none.return_value = None

    await executor.buy(
        session, basket_id=1, asset_id=1, user_id=1,
        ticker="AAPL", quantity=Decimal("10"), price=Decimal("150"),
    )
    assert basket.cash == Decimal("8500")


@pytest.mark.asyncio
async def test_buy_insufficient_cash_raises(executor):
    basket = MagicMock(cash=Decimal("100"), id=1)
    session = AsyncMock()
    session.get.return_value = basket
    session.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(ValueError, match="Insufficient cash"):
        await executor.buy(
            session, basket_id=1, asset_id=1, user_id=1,
            ticker="AAPL", quantity=Decimal("10"), price=Decimal("150"),
        )


@pytest.mark.asyncio
async def test_sell_no_position_raises(executor):
    session = AsyncMock()
    session.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(ValueError, match="Insufficient position"):
        await executor.sell(
            session, basket_id=1, asset_id=1, user_id=1,
            ticker="AAPL", quantity=Decimal("5"), price=Decimal("150"),
        )
```

**Step 4: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_orders.py -v
```

Expected: ImportError — `PaperTradingExecutor` not yet written.

**Step 5: Write `src/orders/paper.py`**

```python
import logging
from datetime import datetime, timezone
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
```

**Step 6: Run tests**

```bash
.venv/bin/pytest tests/test_orders.py -v
```

Expected: 3 tests PASS.

**Step 7: Write `src/bot/handlers/orders.py`**

```python
import logging
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Asset, Basket, User
from src.data.yahoo import YahooDataProvider
from src.orders.paper import PaperTradingExecutor

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


async def _handle_order(update: Update, context, order_type: str) -> None:
    if len(context.args) < 2:
        await update.message.reply_text(f"Uso: /{order_type.lower()} TICKER cantidad")
        return
    ticker = context.args[0].upper()
    try:
        quantity = Decimal(context.args[1])
    except InvalidOperation:
        await update.message.reply_text("Cantidad inválida.")
        return
    if quantity <= 0:
        await update.message.reply_text("Cantidad debe ser positiva.")
        return

    try:
        price_obj = _provider.get_current_price(ticker)
    except Exception as e:
        await update.message.reply_text(f"Error obteniendo precio de {ticker}: {e}")
        return

    async with async_session_factory() as session:
        asset_result = await session.execute(select(Asset).where(Asset.ticker == ticker))
        asset = asset_result.scalar_one_or_none()
        if not asset:
            await update.message.reply_text(f"Ticker {ticker} no está en ninguna cesta.")
            return

        basket_result = await session.execute(select(Basket).where(Basket.active == True))
        basket = basket_result.scalars().first()
        if not basket:
            await update.message.reply_text("No hay cestas activas.")
            return

        user = await _get_or_create_user(session, update.effective_user)
        try:
            if order_type == "BUY":
                await _executor.buy(session, basket.id, asset.id, user.id, ticker, quantity, price_obj.price)
            else:
                await _executor.sell(session, basket.id, asset.id, user.id, ticker, quantity, price_obj.price)
            verb = "Compra" if order_type == "BUY" else "Venta"
            await update.message.reply_text(
                f"✅ *{verb} ejecutada*\n"
                f"{quantity} {ticker} × {price_obj.price:.2f} {price_obj.currency}\n"
                f"Total: {quantity * price_obj.price:.2f} {price_obj.currency}",
                parse_mode="Markdown",
            )
        except ValueError as e:
            await update.message.reply_text(f"❌ {e}")


async def cmd_compra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_order(update, context, "BUY")


async def cmd_vende(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_order(update, context, "SELL")


def get_handlers():
    return [
        CommandHandler("compra", cmd_compra),
        CommandHandler("vende", cmd_vende),
    ]
```

**Step 8: Register orders handlers in `src/bot/bot.py`**

```python
from src.bot.handlers.orders import get_handlers as order_handlers
# In run(), add after portfolio_handlers loop:
for handler in order_handlers():
    app.add_handler(handler)
```

**Step 9: Test manually**

```bash
.venv/bin/python scroogebot.py
```

Send `/compra AAPL 5` → expect confirmation. Send `/valoracion` → expect updated position.

**Step 10: Run all tests**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all tests PASS.

**Step 11: Commit**

```bash
git add src/orders/ src/bot/handlers/orders.py src/bot/bot.py tests/test_orders.py
git commit -m "feat: PaperTradingExecutor + /compra and /vende commands — Part 1 complete"
```

---

## Part 1 Done ✅

| Task | Feature |
|------|---------|
| 1 | Project scaffold |
| 2 | Config (pydantic-settings + YAML) |
| 3 | DB models + Alembic migration |
| 4 | DB seeder from config.yaml |
| 5 | DataProvider (yfinance) |
| 6 | PortfolioEngine + /valoracion, /cartera, /historial |
| 7 | PaperTradingExecutor + /compra, /vende |

**Next:** [Part 2 — Strategies, AlertEngine, Roles](2026-02-21-part2-strategies-alerts-roles.md)
