# ScroogeBot — Claude Project Memory

## Working with the User

**El usuario tiene conocimientos técnicos (Python, backend) pero poca experiencia en finanzas e inversión.**

- Si pide algo que financieramente no tiene sentido (p.ej. una métrica mal aplicada, una estrategia incoherente con el objetivo de la cesta, un parámetro absurdo), **discutirlo antes de implementar**, no hacer lo que se pide sin más.
- Explicar conceptos financieros cuando sean relevantes (Sharpe, alpha, drawdown, etc.) de forma breve y en español.
- Si hay una forma mejor o más estándar de hacer lo que pide, proponerla como alternativa.

## Project Overview

ScroogeBot ("TioGilito") is a Telegram investment bot for shared paper-trading baskets with automatic strategy alerts.

**Entry point:** `scroogebot.py` → `asyncio.run(run())` → `src/bot/bot.py`

## Tech Stack

- Python 3.11, async throughout
- python-telegram-bot v20+ (native async)
- SQLAlchemy 2.0 async + aiomysql driver (MariaDB)
- Alembic migrations
- pydantic-settings (`.env` + `config/config.yaml`)
- yfinance for market data
- `ta==0.11.0` for indicators (**NOT** pandas-ta — removed from PyPI)
- APScheduler 3.x (AsyncIOScheduler)

## Critical Notes

Project has a .venv: remember to activate it for any python, pip, etc.

### ta library API (NOT pandas-ta)
```python
# RSI
ta.momentum.RSIIndicator(close=series, window=14).rsi()

# Bollinger Bands (for Part 3)
ta.volatility.BollingerBands(close=series, window=20, window_dev=2)
```

### Python 3.11 AsyncMock gotcha
`AsyncMock` children are also `AsyncMock`. For test sessions, always use `MagicMock()` for execute results:
```python
execute_result = MagicMock()
execute_result.scalar_one_or_none.return_value = some_value
session.execute = AsyncMock(return_value=execute_result)
```

### Database
- MariaDB, user `sebastian_user` needs `CREATE` privileges
- `sudo mysql` required to create DB and grant privileges
- Run migrations: `alembic upgrade head`
- Seed: `python -c "import asyncio; from src.db.seed import seed; asyncio.run(seed())"`

### Virtual env
`.venv/bin/python` and `.venv/bin/pytest`

## Source Tree

```
src/
├── config.py              # Settings(BaseSettings) + load_app_config()
├── db/
│   ├── models.py          # 9 ORM models: User, Basket, BasketMember, Asset,
│   │                      #   BasketAsset, Position, Order, Alert, Watchlist
│   ├── base.py            # async_session_factory
│   ├── seed.py            # seeds baskets+assets from config.yaml
│   └── migrations/        # Alembic
├── data/
│   ├── base.py            # abstract DataProvider
│   └── yahoo.py           # YahooDataProvider
├── portfolio/engine.py    # PortfolioEngine.get_valuation() with EUR FX
├── orders/
│   ├── base.py            # abstract OrderExecutor
│   └── paper.py           # PaperTradingExecutor.buy()/sell()
├── strategies/
│   ├── base.py            # Signal dataclass + Strategy ABC
│   ├── stop_loss.py       # StopLossStrategy (reads app_config)
│   └── ma_crossover.py    # MACrossoverStrategy (reads app_config)
├── alerts/engine.py       # AlertEngine — scans, deduplicates, notifies
└── bot/
    ├── bot.py             # Application + APScheduler + CallbackQueryHandler
    └── handlers/
        ├── portfolio.py   # /valoracion /cartera /historial
        ├── orders.py      # /compra /vende
        ├── baskets.py     # /cestas /cesta
        ├── analysis.py    # /analiza (RSI + SMA)
        └── admin.py       # /start /adduser /watchlist /addwatch
```

## Key Design Decisions

- **Vertical slices** — each bot feature is a complete slice (handler → engine → DB)
- **Abstract interfaces** — DataProvider, OrderExecutor, Strategy are swappable
- **AlertEngine session isolation** — each basket scan uses its own session; notify-before-commit so orphan PENDING alerts can't accumulate
- **notify-before-commit ordering** — `flush()` → `_notify()` → `commit()`: if notify fails, alert is not persisted and next scan retries
- **`PaperTradingExecutor.buy/sell` signature**: `(session, basket_id, asset_id, user_id, ticker, qty, price, triggered_by="MANUAL")`

## Config

`config/config.yaml` keys used in code:
- `app_config["strategies"]["stop_loss"]` → `stop_loss_pct`, `take_profit_pct`
- `app_config["strategies"]["ma_crossover"]` → `fast_period`, `slow_period`
- `app_config["scheduler"]["interval_minutes"]`
- `app_config["baskets"]` → list of basket dicts

## Running Tests

```bash
.venv/bin/pytest tests/ -v
```

Currently: 13 tests across config, data, orders, strategies.

## Implementation Status

- **Part 1** ✅ — Scaffold, config, DB models, seeder, DataProvider, PortfolioEngine, PaperTrading, /compra /vende /valoracion /cartera /historial
- **Part 2** ✅ — /cestas /cesta /analiza, StopLoss + MACrossover strategies, AlertEngine + APScheduler, /start /adduser roles, alert inline keyboard confirmations, /watchlist /addwatch
- **Part 3** ⏳ — Backtest engine (vectorbt), RSI/Bollinger/SafeHaven strategies, /backtest command, market-hours scheduler, systemd service

See `docs/plans/2026-02-21-part3-backtest-advanced.md` for Part 3 spec.
