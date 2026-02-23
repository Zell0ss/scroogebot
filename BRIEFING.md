# ScroogeBot — Briefing for Claude

> **Purpose**: Knowledge transfer between Claude Code and Claude Web.
> **Audience**: Claude AI and developer

---

## What is this project

ScroogeBot ("TioGilito") is an async Telegram bot for managing **shared paper-trading investment baskets**. A group of users shares baskets; strategies scan positions automatically and fire inline-keyboard alerts so the group can confirm or reject trades without leaving Telegram.

---

## How it works (data flow)

```
1. SETUP:       config.yaml → seed() → DB (baskets, assets, cash)
2. BOT START:   scroogebot.py → Application + APScheduler
3. USER CMDS:   Telegram → CommandHandler → handler → SQLAlchemy async session → reply
4. AUTO SCAN:   APScheduler (every 5min) → AlertEngine.scan_all_baskets()
                  → per-basket session → YahooDataProvider → Strategy.evaluate()
                  → Alert row flushed → _notify() → Telegram InlineKeyboard
5. CALLBACK:    User taps ✅/❌ → CallbackQueryHandler → PaperTradingExecutor
                  → Order row + Position/Cash updated → message edited
```

Detailed flow:
- On startup, `run()` in `bot.py` wires all `CommandHandler`s, registers a `CallbackQueryHandler` for `^alert:` callbacks, creates `AlertEngine` and `AsyncIOScheduler`, then calls `app.run_polling()`.
- Every `interval_minutes` (default 5), the scheduler calls `scan_all_baskets()`. For each active basket it opens a **dedicated session**, fetches positions with quantity > 0, fetches live price + 3-month OHLCV, runs the basket's strategy, deduplicates against existing PENDING alerts, flushes new `Alert` rows, calls `_notify()` (sends Telegram messages with inline keyboard), then commits. Notify-before-commit means a failed notification prevents the alert from being persisted — the next scan retries.
- When a user taps ✅ Ejecutar, `handle_alert_callback` verifies the user is a basket member, fetches live price, calls `PaperTradingExecutor.buy/sell`, marks the alert CONFIRMED, commits, and edits the message.

---

## Tech stack

- **Language**: Python 3.11 — async throughout (asyncio, async/await)
- **Main frameworks/libs**:
  - `python-telegram-bot ≥20`: native async, Application, CommandHandler, CallbackQueryHandler
  - `SQLAlchemy 2.0` async + `aiomysql`: async ORM with `async_session_factory`
  - `Alembic`: migrations; `alembic upgrade head` on deploy
  - `pydantic-settings`: Settings from `.env`; `load_app_config()` from `config/config.yaml`
  - `yfinance`: market data (fast_info for price, download for OHLCV)
  - **`ta==0.11.0`** ⚠️: technical indicators — NOT `pandas-ta` (removed from PyPI)
  - `APScheduler 3.x` (`AsyncIOScheduler`): runs on the same event loop as Telegram
- **Database**: MariaDB — multi-user concurrency, FKs, already in production for other projects
- **External APIs**: Telegram Bot API, Yahoo Finance (no key required)
- **Infrastructure**: local / VPS + systemd (Part 3)

---

## Bot commands

| Command | Role | What it does |
|---------|------|--------------|
| `/start` | Anyone | Register in DB |
| `/valoracion` | Member | EUR-converted basket valuation |
| `/cartera` | Member | Open positions per basket |
| `/historial` | Member | Recent orders |
| `/cestas` | Member | List active baskets |
| `/cesta <name>` | Member | Basket detail (assets, members, cash) |
| `/analiza <TICKER>` | Member | RSI(14), SMA20/50, trend, 1d change |
| `/compra <TICKER> <qty>` | Member | Paper-buy at live price |
| `/vende <TICKER> <qty>` | Member | Paper-sell at live price |
| `/adduser @u ROLE <basket>` | OWNER | Add/promote basket member |
| `/watchlist` | Member | View own watchlist entries |
| `/addwatch <TICKER> Name\|note` | Member | Add to watchlist |

---

## Project structure

```
scroogebot/
├── scroogebot.py          # Entry point: asyncio.run(run())
├── config/
│   ├── config.yaml        # Baskets, assets, strategies, scheduler
│   └── logging.yaml       # Logging config
├── src/
│   ├── config.py          # Settings(BaseSettings) + app_config dict
│   ├── db/
│   │   ├── models.py      # 9 ORM models (see Data Models below)
│   │   ├── base.py        # async_session_factory
│   │   ├── seed.py        # Idempotent seeder from config.yaml
│   │   └── migrations/    # Alembic
│   ├── data/
│   │   ├── base.py        # Abstract DataProvider
│   │   └── yahoo.py       # YahooDataProvider (yfinance)
│   ├── portfolio/engine.py # get_valuation() with EUR FX conversion
│   ├── orders/
│   │   ├── base.py        # Abstract OrderExecutor
│   │   └── paper.py       # PaperTradingExecutor — cash + position + Order row
│   ├── strategies/
│   │   ├── base.py        # Signal dataclass + Strategy ABC
│   │   ├── stop_loss.py   # StopLossStrategy
│   │   ├── ma_crossover.py # MACrossoverStrategy
│   │   ├── rsi.py         # RSIStrategy
│   │   ├── bollinger.py   # BollingerStrategy
│   │   └── safe_haven.py  # SafeHavenStrategy
│   ├── alerts/engine.py   # AlertEngine (scan → signal → notify → commit)
│   ├── backtest/
│   │   ├── engine.py      # BacktestEngine.run(tickers, strategy, ...) → PortfolioBacktestResult
│   │   └── montecarlo.py  # MonteCarloAnalyzer
│   └── bot/
│       ├── bot.py         # Application wiring + scheduler + callback handler
│       └── handlers/      # portfolio, orders, baskets, analysis, admin, backtest, montecarlo
└── tests/                 # 152 tests
```

**Key modules**:
- **`alerts/engine.py`**: Core automation. Each basket scan runs in its own session. Notify-before-commit ensures no orphan PENDING alerts. STRATEGY_MAP maps basket.strategy string to concrete class.
- **`strategies/`**: Clean ABC — implement `evaluate(ticker, data, price, avg_price=None) → Signal | None`. `avg_price` is the position's actual purchase price; `StopLossStrategy` uses it, others ignore it. Adding a strategy = one file + one line in STRATEGY_MAP.
- **`orders/paper.py`**: `buy/sell(session, basket_id, asset_id, user_id, ticker, qty, price, triggered_by="MANUAL")` — updates cash, position avg_price, inserts Order row.
- **`backtest/engine.py`**: `BacktestEngine.run(tickers: list[str], strategy, strategy_name, period, stop_loss_pct) → PortfolioBacktestResult`. Synchronous (vectorbt); called via `run_in_executor`. Runs portfolio-level simulation with `cash_sharing=True, group_by=True`. Returns aggregate stats + `per_asset: dict[str, BacktestResult]` for per-ticker breakdown.

---

## Critical design decisions

### Vertical slices over horizontal layers

**Why**: Get a working bot faster; each slice is independently deployable and testable.

**Discarded alternatives**: Traditional phases (all models → all services → all handlers); big-bang delivery.

**Trade-off accepted**: Some cross-cutting concerns (error handling, auth) are not unified until later slices.

---

### ta==0.11.0 instead of pandas-ta

**Why**: `pandas-ta` was removed from PyPI mid-project. `ta==0.11.0` provides equivalent RSI and Bollinger Bands with a class-based API.

**Impact**: All indicator code uses `ta.momentum.RSIIndicator(close=series, window=14).rsi()` — NOT `ta.rsi()`. Part 3 Bollinger: `ta.volatility.BollingerBands(close=series, window=20, window_dev=2)`.

**Trade-off**: Slightly more verbose API; no functional difference.

---

### Notify-before-commit in AlertEngine

**Why**: If Telegram send fails after a DB commit, the alert stays PENDING forever — deduplication blocks all future retries. Notifying first means a failed send prevents the commit, and the next scheduler tick retries cleanly.

**Discarded alternatives**: commit-then-notify (standard); separate retry queue.

**Trade-off**: A partial Telegram failure (some members notified, then error) causes no DB write — those members received a keyboard for a non-existent alert. Pressing buttons shows "Esta alerta ya fue procesada."

---

### Per-basket session isolation in AlertEngine

**Why**: A single shared session + commit inside a position loop causes SQLAlchemy to expire all objects after each commit (DetachedInstanceError on next iteration). Also, one basket failure taints the shared session for all subsequent baskets.

**Pattern**: `scan_all_baskets` materializes the basket list and closes the session. Each `_scan_basket` call opens its own session.

---

## Data models

**9 tables**: `users`, `baskets`, `basket_members`, `assets`, `basket_assets`, `positions`, `orders`, `alerts`, `watchlist`

Key relationships:
- `Basket` 1→N `Position` (via basket_id), `Order`, `Alert`, `BasketMember`, `BasketAsset`
- `Asset` 1→N `Position`, `Order`, `Alert`, `BasketAsset`
- `User` 1→N `Order`, `BasketMember`, `Watchlist`
- `Position`: (basket_id, asset_id) unique — tracks quantity + avg_price
- `Alert`: status ∈ {PENDING, CONFIRMED, REJECTED, EXPIRED}; strategy + signal + price + reason. EXPIRED = condition cleared before user confirmed.

---

## Configuration

**Required `.env`**:
- `TELEGRAM_APIKEY`: BotFather token
- `DATABASE_URL`: `mysql+aiomysql://user:pass@host/db`
- `DATABASE_URL_SYNC`: `mysql+pymysql://user:pass@host/db` (Alembic)

**`config/config.yaml`** keys used in code:
- `scheduler.interval_minutes` → APScheduler interval
- `strategies.stop_loss.{stop_loss_pct, take_profit_pct}` → StopLossStrategy thresholds
- `strategies.ma_crossover.{fast_period, slow_period}` → MACrossoverStrategy periods
- `baskets[]` → seeder input (name, strategy, risk_profile, cash, assets)

---

## Current state

**Version**: 0.1.0 | **Last update**: February 2026

✅ **Implemented** (Parts 1, 2 & 3 partial):
- Full DB schema + Alembic migration + seeder
- YahooDataProvider (price + OHLCV)
- PortfolioEngine with EUR FX conversion
- PaperTradingExecutor (buy/sell with cash/position tracking)
- All bot commands (portfolio, orders, baskets, analysis, admin, watchlist)
- StopLossStrategy + MACrossoverStrategy + RSIStrategy + BollingerStrategy + SafeHavenStrategy
- AlertEngine + APScheduler with per-basket session isolation + market-hours guard
- Inline keyboard alert confirmations (confirm → execute trade, reject → dismiss)
- OWNER/MEMBER role system
- **Portfolio-level backtest** (`/backtest`): `BacktestEngine.run(tickers)` with shared cash, CARTERA + DESGLOSE output
- MonteCarloAnalyzer (`/montecarlo`), position sizing (`/sizing`), ticker search (`/buscar`)
- `stop_loss_pct` as per-basket risk layer (independent of entry strategy)

**Previously known limitations (now fixed)**:
- ~~StopLossStrategy uses `data["Close"].iloc[0]` (period open) as reference, NOT `Position.avg_price`~~ — fixed in e3774e5 / f7f663e: strategy now uses `avg_price` when provided, AlertEngine passes `pos.avg_price`
- ~~No market-hours guard: confirm callback could execute at stale Friday-close price on weekend~~ — fixed in bea5550: `handle_alert_callback` blocks execution when market is closed; stale PENDING alerts auto-expire in f8d59b9
- No tests for handlers or AlertEngine (manual testing only per plan) — partially resolved: `test_alert_engine_stoploss.py` and `test_bot_callback.py` added

---

## Typical use cases

### Case 1: Morning portfolio check

**Goal**: See current valuation and open positions

```
/valoracion  → EUR-converted total per basket
/cartera     → positions with quantity and avg_price
```

### Case 2: Manual trade + analysis

**Goal**: Analyse a ticker and paper-buy

```
/analiza NVDA   → RSI, SMA trend, 1d change
/compra NVDA 5  → paper-buy 5 shares at live price
```

### Case 3: Respond to an automatic alert

**Goal**: Strategy triggers; group decides to execute

```
Bot sends: "⚠️ Cesta Agresiva — ma_crossover\n🔴 VENTA: AAPL\n..."
          [✅ Ejecutar] [❌ Rechazar]
User taps ✅ → bot executes sell at live price, edits message ✅
```

---

## Notes for Claude Web

**Context for architecture discussions**:
- Telegram's event loop and APScheduler must share the same asyncio loop — `AsyncIOScheduler` is the correct choice
- Session isolation pattern (one session per basket scan) is intentional and important
- The notify-before-commit decision is a deliberate trade-off against the conventional commit-then-notify

**Pending decisions / remaining Part 3**:
- ~~vectorbt backtest: sync API in an async bot~~ — resolved: `run_in_executor` (ThreadPoolExecutor)
- ~~Market hours~~ — resolved: `is_market_open(asset.market)` guard in AlertEngine scan + callback
- systemd service file

---

## Notes for Claude Code

**Conventions**:
- All handlers: `async def cmd_X(update, context: ContextTypes.DEFAULT_TYPE) -> None`
- Session: always `async with async_session_factory() as session:`
- `get_handlers()` at bottom of each handler file returns list of `CommandHandler`
- Register new handler group in `src/bot/bot.py` `run()` function

**ta library API** (critical — NOT pandas-ta):
```python
ta.momentum.RSIIndicator(close=series, window=14).rsi()           # → pd.Series
ta.volatility.BollingerBands(close=series, window=20, window_dev=2)
  .bollinger_hband()  # upper band
  .bollinger_lband()  # lower band
  .bollinger_mavg()   # middle band
```

**Python 3.11 AsyncMock** (test gotcha):
```python
execute_result = MagicMock()          # NOT AsyncMock
execute_result.scalar_one_or_none.return_value = obj
session.execute = AsyncMock(return_value=execute_result)
```

**Adding a new strategy** (see `docs/HOW-TO-ADD-STRATEGY.md`):
1. Create `src/strategies/your_strategy.py` extending `Strategy`
2. Add to `STRATEGY_MAP` in `src/alerts/engine.py`
3. Add strategy params to `config/config.yaml`
4. Write tests in `tests/test_strategies.py`

---

*Last updated: February 2026*
*Generated from: commit 50a2001*
