# Changelog

All notable changes to ScroogeBot are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [Unreleased]

### Planned (Part 3)
- `/backtest <TICKER> <strategy>` — vectorbt-powered backtesting
- RSIStrategy, BollingerBandsStrategy, SafeHavenStrategy
- Market-hours-aware scheduler (skip scans outside NYSE/LSE/BME hours)
- systemd service file

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
