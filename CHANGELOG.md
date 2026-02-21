# Changelog

All notable changes to ScroogeBot are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [0.3.0] — 2026-02-21

### Added
- `src/scheduler/market_hours.py` — `is_market_open(market)` / `any_market_open()`: UTC-based open/close guard reading `scheduler.market_hours` from `config.yaml`; weekends always closed; unknown markets pass through
- `AlertEngine.scan_all_baskets` — skips entire scan when all markets are closed
- `AlertEngine._scan_basket` — skips individual assets whose market is currently closed
- `/logs [N]` — OWNER-only command listing the last *N* (default 20, max 50) command_logs entries with timestamp, user, command, and status
- 13 new tests in `tests/test_market_hours.py` (30 total, all passing)

## [0.4.0] — 2026-02-21

### Added
- `LSE` market hours in `config.yaml` (08:00–16:30 UTC)
- `metrics` section in `config.yaml` (`port: 9090`)
- `src/metrics.py` — Prometheus metrics module (singletons, `start_metrics_server(port)`)
  - `scroogebot_alert_scans_total` counter — labels: `result` (completed/skipped_closed)
  - `scroogebot_alerts_generated_total` counter — labels: `strategy`, `signal`
  - `scroogebot_scan_duration_seconds` histogram — wall-clock duration of scan runs
  - `scroogebot_market_open` gauge — 0/1 per configured market, updated each scan tick
  - `scroogebot_commands_total` counter — labels: `command`, `success` (true/false)
- `AlertEngine` instruments scan count, duration, per-strategy alert count, and market-open gauge
- `audit.log_command()` increments `scroogebot_commands_total` before writing to DB
- `bot.py run()` starts Prometheus metrics HTTP server on configured port at startup
- `prometheus-client>=0.19` added to `pyproject.toml` dependencies

## [Unreleased]

---

## [0.2.0] — 2026-02-21

### Added (Part 3 — Backtesting, Advanced Strategies, Observability)
- `/backtest [period]` — vectorbt-powered backtesting for all active basket assets; returns total return, Sharpe, max drawdown, win rate, α vs buy-and-hold
- `BacktestEngine` — rolling 60-bar signal generation with `asyncio.run_in_executor` (non-blocking)
- `RSIStrategy` — crossover-based BUY/SELL on RSI exiting oversold/overbought zones
- `BollingerStrategy` — BUY at/below lower band, SELL at/above upper band
- `SafeHavenStrategy` — SELL risky assets on drawdown ≥ threshold from peak; skips GLD/BND/TLT/SHY/VGSH
- All 3 new strategies registered in `AlertEngine.STRATEGY_MAP` and `/backtest` handler
- `scroogebot.service` — systemd unit file for production deployment
- **loguru** logging: colorised stdout + rotating `scroogebot.log` (10 MB / 30 days); stdlib `logging` intercepted via `InterceptHandler`
- `command_logs` table + Alembic migration — persists every write-command with user, timestamp, args, success flag, and outcome message
- `src/bot/audit.py` — `log_command()` async helper (never raises; audit failures logged only)
- Write commands audited: `/compra`, `/vende`, `/adduser`, `/addwatch`, `/start`, alert confirm/reject callbacks

### Fixed
- `"Annualized Return [%]"` key missing in vectorbt 0.28.4 stats — now computed manually: `((1+R)^(252/n) - 1) × 100`
- `BacktestEngine.run()` blocking asyncio event loop — wrapped in `run_in_executor`
- `sign` lambda re-defined inside loop — moved to module level

---

## [0.1.0] — 2026-02-21

### Added (Part 2 — Strategies, Alerts, Roles)
- `/cestas` — list active baskets with strategy and risk profile
- `/cesta <name>` — basket detail (assets, members, cash balance)
- `/analiza <TICKER>` — RSI(14), SMA20/50, trend, 1-day change via `ta==0.11.0`
- `/start` — user self-registration
- `/adduser @user OWNER|MEMBER <basket>` — OWNER-only role assignment
- `/watchlist` — personal watchlist (scoped to calling user)
- `/addwatch <TICKER> Name | note` — add ticker to watchlist
- `StopLossStrategy` — SELL on drop ≥ stop_loss_pct or gain ≥ take_profit_pct
- `MACrossoverStrategy` — BUY/SELL on fast-MA / slow-MA crossover
- `AlertEngine` — APScheduler-driven scan with per-basket session isolation
- Alert inline keyboard (✅ Ejecutar / ❌ Rechazar) sent to all basket members
- `CallbackQueryHandler` — executes confirmed trades via PaperTradingExecutor
- Basket membership check in callback before trade execution
- Notify-before-commit ordering to prevent orphan PENDING alerts

### Added (Part 1 — Core)
- Project scaffold: pyproject.toml, config module (pydantic-settings + YAML)
- SQLAlchemy 2.0 async ORM with 9 tables + Alembic initial migration
- Idempotent DB seeder from `config/config.yaml`
- Abstract `DataProvider` interface + `YahooDataProvider` (yfinance)
- `PortfolioEngine.get_valuation()` with EUR FX conversion
- Abstract `OrderExecutor` interface + `PaperTradingExecutor` (buy/sell)
- `/valoracion` — EUR-converted portfolio valuation per basket
- `/cartera` — open positions with quantity and avg_price
- `/historial` — recent order history
- `/compra <TICKER> <qty>` — paper-buy at live price
- `/vende <TICKER> <qty>` — paper-sell at live price

### Fixed
- `ta` library substituted for removed `pandas-ta` package
- NaN/IndexError guards in `/analiza` SMA50 trend and 1d-change calculation
- AlertEngine session isolation (per-basket sessions, no shared session across scans)
- `cmd_adduser` OWNER check no longer bypassable by unauthenticated callers
- `triggered_by=alert.strategy` passed to PaperTradingExecutor in alert callbacks
