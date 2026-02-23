# Changelog

All notable changes to ScroogeBot are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [Unreleased] — 2026-02-23

### Changed
- **`/backtest` now operates at portfolio level**: `BacktestEngine.run()` accepts `list[str]` tickers, runs vectorbt with `cash_sharing=True, group_by=True` (shared 10k EUR pool), returns `PortfolioBacktestResult` (aggregate + per-asset breakdown). Output split into CARTERA (portfolio aggregate stats) and DESGLOSE (per-ticker detail with win rate).
- Per-asset stats use proportional `init_cash = 10_000 / n_tickers` to match the shared-cash capital allocation

---

## [Unreleased] — 2026-02-22

### Added
- `stop_loss_pct` field on `Basket` — optional per-basket risk floor, independent of entry strategy; Alembic migration `47858283c702`
- **AlertEngine stop-loss layer**: after `strategy.evaluate()`, if `basket.stop_loss_pct` is set and position is down ≥ threshold from `pos.avg_price`, signal is overridden to SELL (fixes bug: old `StopLossStrategy` used `data.iloc[0]`, not actual entry price)
- **BacktestEngine + MonteCarloAnalyzer**: `stop_loss_pct` param passed as `sl_stop=pct/100` to vectorbt
- `/estrategia <cesta> [strategy] [stop_loss_%]` — extended to accept trailing numeric as stop_loss_pct; `/estrategia Cesta rsi 8` sets both; `/estrategia Cesta 10` sets only stop_loss; `/estrategia Cesta 0` disables it; view mode shows current stop_loss_pct
- `/nuevacesta <nombre> <strategy> [stop_loss_%]` — optional trailing numeric arg
- `/cesta` — shows `Stop-loss: X%` in strategy line when configured
- `config.yaml` — model baskets get strategy-appropriate stop_loss_pct (StopLoss:8%, MACrossover:8%, RSI:10%, Bollinger:12%, SafeHaven:6%)
- `seed.py` — reads and persists `stop_loss_pct` from config (create + update paths)
- `/montecarlo` position fallback: personal baskets without `BasketAsset` rows now fall back to open positions (same logic as `/backtest`)
- 46 new tests; 146 total

### Fixed
- `/montecarlo` returning "sin activos activos" for personal baskets (e.g. `Mi_Apuesta_jmc`) — now falls back to `Position` rows like `/backtest` does

---

## [0.5.0] — 2026-02-22

### Added
- `/montecarlo <cesta> [sims] [días]` — Monte Carlo simulator; N bootstrap-resampled price paths per asset; statistics: median return, p10/p90 range, VaR 95%, CVaR 95%, max drawdown, Sharpe, win rate, profile label (🟢/🟡/🔴); seeded RNG for reproducibility; max 500 sims / 365 days
- `MonteCarloAnalyzer` in `src/backtest/montecarlo.py` — vectorbt-backed path simulation
- `/buscar <texto>` — search tickers by name or symbol; local basket assets first (📌 marked), Yahoo Finance fallback for <3 local results
- `/register <tg_id> <username>` — admin pre-registration of new users
- `/estrategia <cesta> [nueva_estrategia]` — view or change basket strategy (OWNER only to change)
- `/nuevacesta <nombre> <estrategia>` — create basket with €10k cash; creator becomes OWNER
- `/eliminarcesta <nombre>` — soft-delete basket (OWNER only; blocked if open positions); name mangled to allow reuse
- `/sel [nombre]` — persistent basket selection saved in `users.active_basket_id`; survives restarts; used by `/compra`, `/vende`, `/backtest`, `/sizing`
- `/sizing <TICKER> [STOP [CAPITAL]]` — position sizing with ATR(14)×2 auto stop or manual stop; respects max-risk 0.75% and max-position 20%; broker commission model (paper/degiro/myinvestor); USD→EUR conversion
- 5 cestas modelo in `config.yaml` — one per strategy, shared 6-asset universe (AAPL, MSFT, NVDA, SAN.MC, IBE.MC, GLD) for cross-strategy benchmarking
- Makefile — `make run/seed/migrate/test/test-v/test-cov/lint/logs/push`
- DB migration `d4e5f6a7b890` — `active_basket_id` FK on `users` table
- DB migration `e5f6a7b8c901` — drop unique constraint on `baskets.name` (to allow soft-deleted names to be reused with mangling)

### Fixed
- `/compra` and `/vende`: were using first active basket at random; now use `caller.active_basket_id` + `@cesta` inline override
- `/backtest`: `MultipleResultsFound` when basket name matched multiple rows — now filters by `active=True`
- `/backtest`: always-invested fallback for exit-only strategies (`_make_entries_for_exit_only`): enter at warmup bar, re-enter day after each exit
- `/backtest`: NaN/Inf values in stats now shown as `N/A` instead of crashing
- `/backtest`: Max DD was displayed as positive (e.g. `+7.5%`) — fixed to negative (`-7.5%`)
- `/backtest`: strategy name added to output header

---

## [0.4.0] — 2026-02-21

### Added
- `LSE` market hours in `config.yaml` (08:00–16:30 UTC)
- `metrics` section in `config.yaml` (`port: 9010`)
- `src/metrics.py` — Prometheus metrics module
  - `scroogebot_alert_scans_total` counter — labels: `result` (completed/skipped_closed)
  - `scroogebot_alerts_generated_total` counter — labels: `strategy`, `signal`
  - `scroogebot_scan_duration_seconds` histogram
  - `scroogebot_market_open` gauge — 0/1 per market, updated each tick
  - `scroogebot_commands_total` counter — labels: `command`, `success`
- `AlertEngine` instruments scan count, duration, per-strategy alert count, market-open gauge
- `audit.log_command()` increments `scroogebot_commands_total` before writing to DB
- `bot.py run()` starts Prometheus HTTP server on configured port at startup
- `prometheus-client>=0.19` added to `pyproject.toml`

---

## [0.3.0] — 2026-02-21

### Added
- `src/scheduler/market_hours.py` — `is_market_open(market)` / `any_market_open()`: UTC-based open/close guard reading `scheduler.market_hours` from `config.yaml`; weekends always closed
- `AlertEngine.scan_all_baskets` — skips entire scan when all markets are closed
- `AlertEngine._scan_basket` — skips individual assets whose market is currently closed
- `/logs [N]` — OWNER-only command; last N command_logs entries (default 20, max 50)
- 13 new tests in `tests/test_market_hours.py`

---

## [0.2.0] — 2026-02-21

### Added
- `/backtest [cesta] [period]` — vectorbt backtesting per asset; total return, Sharpe, max drawdown, win rate, α vs buy-and-hold; periods: `1mo` `3mo` `6mo` `1y` `2y`
- `BacktestEngine` in `src/backtest/engine.py`
- `RSIStrategy` — BUY on RSI(14) < 30; SELL on RSI(14) > 70
- `BollingerStrategy` — BUY at/below lower band; SELL at/above upper band
- `SafeHavenStrategy` — SELL risky assets on drawdown ≥ threshold from 52w high; skips safe-haven tickers (GLD, BND, TLT, SHY, VGSH)
- All 3 strategies registered in `AlertEngine.STRATEGY_MAP`
- `scroogebot.service` — systemd unit file
- **loguru** logging: colorised stdout + rotating `scroogebot.log` (10 MB / 30 days); stdlib `logging` intercepted via `InterceptHandler`
- `command_logs` table + Alembic migration — every write-command logged with user, timestamp, args, success flag
- `src/bot/audit.py` — `log_command()` async helper

### Fixed
- `"Annualized Return [%]"` key missing in vectorbt 0.28.4 — computed manually
- `BacktestEngine.run()` blocking event loop — wrapped in `run_in_executor`

---

## [0.1.0] — 2026-02-21

### Added (Part 2 — Strategies, Alerts, Roles)
- `/cestas` — list active baskets with strategy and risk profile
- `/cesta <name>` — basket detail: assets, members, cash balance
- `/analiza <TICKER>` — RSI(14), SMA20/50, trend, 1-day change (via `ta==0.11.0`)
- `/start` — self-registration; fills in first_name/username from Telegram
- `/adduser @user OWNER|MEMBER <basket>` — OWNER-only role assignment
- `/watchlist` — personal watchlist (scoped to calling user)
- `/addwatch <TICKER> [Name | note]` — add ticker to watchlist
- `StopLossStrategy` — SELL on drop ≥ stop_loss_pct; SELL on gain ≥ take_profit_pct (from period-open)
- `MACrossoverStrategy` — BUY/SELL on fast-MA(20) / slow-MA(50) crossover
- `AlertEngine` — APScheduler-driven scan; per-basket session isolation; deduplication
- Alert inline keyboard (✅ Ejecutar / ❌ Rechazar) sent to all basket members
- `CallbackQueryHandler` — executes confirmed trades via PaperTradingExecutor
- Notify-before-commit ordering (`flush → notify → commit`)

### Added (Part 1 — Core)
- Project scaffold: `pyproject.toml`, config module (pydantic-settings + YAML)
- SQLAlchemy 2.0 async ORM, 9 tables, Alembic initial migration
- Idempotent DB seeder from `config/config.yaml`
- Abstract `DataProvider` + `YahooDataProvider` (yfinance)
- `PortfolioEngine.get_valuation()` with EUR FX conversion
- Abstract `OrderExecutor` + `PaperTradingExecutor` (buy/sell)
- `/valoracion [cesta]` — EUR-converted portfolio valuation per basket
- `/cartera` — open positions with quantity and avg_price
- `/historial` — recent order history (last 10 per basket)
- `/compra <TICKER> <qty>` — paper-buy at live price
- `/vende <TICKER> <qty>` — paper-sell at live price

### Fixed
- `ta` library substituted for removed `pandas-ta`
- NaN/IndexError guards in `/analiza` SMA50 and 1d-change
- AlertEngine session isolation (`DetachedInstanceError` on shared session)
- `cmd_adduser` OWNER check not bypassable by unauthenticated callers
