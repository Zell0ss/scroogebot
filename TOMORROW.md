# TOMORROW — Next Session

## Status: Part 2 Complete ✅, Part 3 Ready to Start

## What Was Done (Parts 1 & 2)

### Part 1 — Core infrastructure
- Config module (pydantic-settings + YAML)
- SQLAlchemy async models (9 tables) + Alembic migration
- DB seeder from config.yaml (2 baskets, 6 assets)
- YahooDataProvider (abstract DataProvider)
- PortfolioEngine with EUR FX conversion
- PaperTradingExecutor (buy/sell with cash tracking)
- Bot commands: /valoracion, /cartera, /historial, /compra, /vende

### Part 2 — Strategies, alerts, roles
- Bot commands: /cestas, /cesta, /analiza (RSI+SMA)
- Strategy framework: StopLossStrategy + MACrossoverStrategy (ta lib API)
- AlertEngine with APScheduler (5min scan, per-basket session isolation, notify-before-commit)
- Bot commands: /start, /adduser (OWNER role), /watchlist, /addwatch
- Alert inline keyboard (✅ Ejecutar / ❌ Rechazar) with PaperTradingExecutor callback

## Next Task: Part 3

**Plan file:** `docs/plans/2026-02-21-part3-backtest-advanced.md`

Part 3 tasks:
1. **Backtest engine** — `src/backtest/engine.py` using vectorbt
2. **RSI + Bollinger Bands strategies** — `src/strategies/rsi.py`, `src/strategies/bollinger.py`
3. **SafeHaven strategy** — rotate to GLD/TLT on VIX spike
4. **/backtest command** — `src/bot/handlers/backtest.py`
5. **Market-hours scheduler** — skip scans outside NYSE/LSE/BME hours
6. **systemd service** — `scroogebot.service` for production deployment

Install vectorbt first: `pip install ".[backtest]"` (already in pyproject.toml)

## Important Notes for Next Session

- `ta` library (NOT pandas-ta): `ta.momentum.RSIIndicator(close=series, window=14).rsi()`
- `ta.volatility.BollingerBands(close=series, window=20, window_dev=2).bollinger_hband()` etc.
- Python 3.11 AsyncMock: use `MagicMock()` for `execute_result`, not `AsyncMock()`
- All tests: `.venv/bin/pytest tests/ -v` (13 passing)
- DB: MariaDB on seb01, user `sebastian_user`

## Open Issues / Known Limitations

- StopLossStrategy uses `data["Close"].iloc[0]` (3-month window open) as reference price, NOT `Position.avg_price`. Fine for demo, should be revisited if real money ever involved.
- No market-hours guard on scheduler yet (added in Part 3 Task 5)
- No tests for AlertEngine, handlers (plan only requires manual test for those)
