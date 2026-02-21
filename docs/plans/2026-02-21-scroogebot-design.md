# ScroogeBot — Design Document

**Date:** 2026-02-21
**Bot name:** TioGilitoBot (`Tio_IA_Gilito_bot`)
**Service name:** scroogebot

---

## Overview

ScroogeBot is a modular investment-support system operated via Telegram. It allows a group of investors to manage shared asset baskets, receive automatic alerts based on configurable strategies, execute orders via natural language, and visualize portfolio state in real time.

The PoC uses yfinance for market data and paper trading for order execution. Both are swappable via abstract interfaces without touching the rest of the system.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     TELEGRAM BOT LAYER                      │
│          Commands · Alerts · Confirmations · Roles          │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   ORCHESTRATOR / EVENT BUS                   │
│          Coordinates modules · Manages state · Schedules    │
└──────┬──────────────┬─────────────────┬─────────────────────┘
       │              │                 │
┌──────▼──────┐ ┌─────▼──────┐ ┌───────▼───────┐ ┌──────────┐
│  DATA LAYER │ │  STRATEGY  │ │   PORTFOLIO   │ │BACKTEST  │
│             │ │   ENGINE   │ │    ENGINE     │ │ ENGINE   │
│ yfinance    │ │            │ │               │ │          │
│ → Broker    │ │ Strategies │ │ Positions     │ │vectorbt  │
│             │ │ Signals    │ │ P&L · Orders  │ │          │
└──────┬──────┘ └─────┬──────┘ └───────┬───────┘ └──────────┘
       │              │                │
┌──────▼──────────────▼────────────────▼─────────────────────┐
│                     ALERT ENGINE                            │
│             Generates alerts from signals                   │
└─────────────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│                     ORDER LAYER (abstract)                   │
│          Paper Trading (PoC)  →  Real Broker (Prod)         │
└─────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
scroogebot/
├── config/
│   ├── config.yaml              # Assets, baskets, strategies, thresholds
│   └── logging.yaml
├── src/
│   ├── config.py                # pydantic-settings: loads .env + config.yaml on startup
│   ├── data/
│   │   ├── base.py              # DataProvider (ABC)
│   │   ├── yahoo.py             # YahooDataProvider (yfinance)
│   │   └── models.py            # Price, OHLCV
│   ├── db/
│   │   ├── base.py              # SQLAlchemy async engine + session factory
│   │   ├── models.py            # ORM: User, Basket, Asset, Position, Order, Alert, Watchlist
│   │   └── migrations/          # Alembic
│   ├── portfolio/
│   │   ├── engine.py            # Valuation, P&L
│   │   └── models.py            # Domain models (separate from ORM)
│   ├── orders/
│   │   ├── base.py              # OrderExecutor (ABC)
│   │   └── paper.py             # PaperTradingExecutor
│   ├── strategies/
│   │   ├── base.py              # Strategy (ABC) → Signal (BUY|SELL|HOLD)
│   │   ├── stop_loss.py
│   │   ├── ma_crossover.py
│   │   ├── rsi.py
│   │   ├── bollinger.py
│   │   └── safe_haven.py
│   ├── alerts/
│   │   └── engine.py            # Generates alerts from signals
│   ├── backtest/
│   │   └── engine.py            # vectorbt wrapper
│   └── bot/
│       ├── bot.py               # Application setup, scheduler wiring
│       └── handlers/
│           ├── portfolio.py     # /valoracion, /cartera, /historial
│           ├── orders.py        # /compra, /vende
│           ├── baskets.py       # /cestas, /cesta
│           ├── analysis.py      # /analiza
│           ├── backtest.py      # /backtest
│           └── admin.py         # /adduser, /setrole, /watchlist
├── tests/
│   ├── conftest.py              # MariaDB test session, fixtures
│   ├── test_data.py
│   ├── test_portfolio.py
│   ├── test_strategies.py
│   └── test_orders.py
├── scroogebot.py                # Entrypoint
├── pyproject.toml
├── alembic.ini
└── scroogebot.service
```

---

## Abstract Interfaces (Swap Points)

```python
# data/base.py
class DataProvider(ABC):
    @abstractmethod
    def get_current_price(self, ticker: str) -> Decimal: ...
    @abstractmethod
    def get_historical(self, ticker: str, period: str, interval: str) -> pd.DataFrame: ...

# orders/base.py
class OrderExecutor(ABC):
    @abstractmethod
    def buy(self, basket_id: int, ticker: str, quantity: Decimal, price: Decimal) -> Order: ...
    @abstractmethod
    def sell(self, basket_id: int, ticker: str, quantity: Decimal, price: Decimal) -> Order: ...

# strategies/base.py
class Strategy(ABC):
    @abstractmethod
    def evaluate(self, ticker: str, data: pd.DataFrame) -> Signal | None: ...
    # Signal: BUY | SELL | HOLD with price, reason, confidence level
```

---

## Data Model

```
users ──< basket_members >── baskets
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
        basket_assets        positions            orders
              │
           assets            alerts            watchlist
```

### User roles per basket
| Role | Capabilities |
|------|-------------|
| OWNER | Orders directly, confirms alerts, manages basket |
| MEMBER | Queries, proposes orders (executed with group notification) |

---

## Basket Model

A **Basket** (cesta) is the central entity. Each basket has an active strategy, a set of assets, and a shared capital pool among its members.

- Positions are **shared**: the basket buys/sells as a unit
- Capital is a **common pool**: individual contributions are not tracked
- Alerts reach **all members**
- Final decision is made by **OWNER**, though any member can issue orders

---

## Strategies

| Strategy | Use case | Risk | Phase |
|----------|----------|------|-------|
| Stop-loss / Take-profit | Loss control, any profile | Low | Slice 5 |
| MA Crossover (SMA 20/50) | Long trends, stable assets | Medium | Slice 5 |
| RSI Contrarian | Assets with predictable oscillations | Medium | Slice 8 |
| Bollinger Mean Reversion | Lateral markets | Medium | Slice 8 |
| Safe Haven Rotation | Conservative portfolio | Low | Slice 8 |
| Event-driven (LLM + news) | IPOs, news-sensitive assets | High | v2 |

---

## Implementation Slices (Vertical Slice Approach)

| # | Slice | Deliverable |
|---|-------|-------------|
| 1 | Scaffold + config + DB | `pyproject.toml`, `src/config.py`, Alembic schema + migrations |
| 2 | DataProvider + `/valoracion` | Bot responds with real yfinance prices |
| 3 | Paper trading + `/compra` `/vende` | Orders executed and persisted in DB |
| 4 | `/cartera` + `/historial` | Open positions and order history views |
| 5 | Strategies + AlertEngine + scheduler | Stop-loss, MA Crossover, automatic alerts via APScheduler |
| 6 | Roles + confirmations | OWNER/MEMBER enforcement, inline keyboard for alert confirmation |
| 7 | Backtesting + `/backtest` | vectorbt integration, metrics via Telegram |
| 8 | Advanced strategies + watchlist | RSI, Bollinger, Safe Haven, `/watchlist` for pending IPOs |

---

## Key Technical Decisions

- **Async throughout**: `python-telegram-bot` v20+ (async native), SQLAlchemy 2.0 async, `aiomysql` driver
- **MariaDB for all environments** (seb01): test schema prefixed or using transactions with rollback in tests
- **pydantic-settings** validates `.env` + `config.yaml` at startup — fails fast if misconfigured
- **Domain models separate from ORM models**: `portfolio/models.py` for business logic, `db/models.py` for persistence
- **APScheduler 3.x**: market-aware scheduling (IBEX 17:30 CET, NYSE 22:00 CET), polling only during active hours
- **Currency conversion**: `EURUSD=X` via yfinance for EUR portfolio valuation
- **Anthropic API key**: reserved for event-driven LLM strategy in v2, not used in PoC

---

## Environment Variables (.env schema)

```
telegram_apikey=<token>
telegram_name=<display name>
telegram_username=<bot username>
anthropic_apikey=<key>       # reserved for v2 LLM strategy
mariadb_host=<host>
mariadb_port=<port>
mariadb_database=<db>
mariadb_user=<user>
mariadb_password=<password>
```

---

## Dependencies

```toml
[project]
dependencies = [
    "python-telegram-bot>=20.0",
    "yfinance",
    "pandas-ta",
    "vectorbt",
    "sqlalchemy>=2.0",
    "aiomysql",
    "alembic",
    "apscheduler>=3.0",
    "pydantic-settings",
    "pyyaml",
]
```

---

## Deployment

Systemd service on seb01:

```ini
[Unit]
Description=ScroogeBot — Investment Telegram Bot

[Service]
Type=simple
ExecStart=/data/scroogebot/.venv/bin/python scroogebot.py
User=ubuntu
WorkingDirectory=/data/scroogebot
Restart=always
RestartSec=10
EnvironmentFile=/data/scroogebot/.env

[Install]
WantedBy=multi-user.target
```

---

## Key Flows

### Automatic alert flow
```
Scheduler (every N min during market hours)
    → DataProvider.get_current_price(ticker)
    → Strategy.evaluate(ticker, data) → None (HOLD) → end
    → Signal (BUY|SELL)
    → AlertEngine.create_alert()
    → Telegram → all basket members
    "⚠️ AAPL hit stop-loss ($170). Execute sell? [✅ Yes / ❌ No]"
    ├─► ✅ OWNER confirms → OrderExecutor.sell() → notify group
    └─► ❌ Rejected / Expired → alert.status = REJECTED/EXPIRED
```

### Direct order flow
```
User: /compra AAPL 10
    ├─► OWNER → Bot asks confirmation → ✅ → OrderExecutor.buy() → notify group
    └─► MEMBER → OrderExecutor.buy() → execute + notify group
```

---

*ScroogeBot — "Dinero que duerme es dinero que llora" 🦆*
