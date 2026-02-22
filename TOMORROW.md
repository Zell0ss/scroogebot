# TOMORROW — ScroogeBot next session context

## Status: Parts 1, 2, 3 + extras COMPLETE ✅

All features implemented, tested (91/91 pass), committed and pushed to
https://github.com/Zell0ss/scroogebot

---

## What was done today (2026-02-22)

### Added this session:
- `/montecarlo` — registered in bot.py (was missing, all implementation was already done)
- `/estrategia <cesta> [estrategia]` — view or change basket strategy (OWNER to change)
- `/nuevacesta <nombre> <estrategia>` — create basket, creator becomes OWNER, €10k cash
- `/eliminarcesta <nombre>` — soft-delete basket if no open positions (OWNER only)
- **5 cestas modelo** in config.yaml — one per strategy (stop_loss, ma_crossover, rsi, bollinger, safe_haven), shared 6-asset universe (AAPL, MSFT, NVDA, SAN.MC, IBE.MC, GLD) for benchmarking real cestas
- **Makefile** — `make run/seed/migrate/test/test-v/test-cov/db-setup/install/lint/logs/push`
- Help and USER_MANUAL updated with new basket management commands
- 11 new tests in `tests/test_basket_admin.py` (91 total)

### Previous sessions:
- `/help`, `/montecarlo`, `/buscar`, `/register`, improved `/start` and `/adduser`
- BacktestEngine, RSI/Bollinger/SafeHaven strategies, market-hours guard
- `/logs`, systemd service, loguru, command_logs audit table

---

## Deploy steps (when going to production)
1. `alembic upgrade head`
2. `make seed`  ← creates the 5 cestas modelo (idempotent)
3. `sudo cp scroogebot.service /etc/systemd/system/`
4. `sudo systemctl daemon-reload && sudo systemctl enable --now scroogebot`

---

## Possible next improvements
- Add assets to cestas modelo via bot (currently no assets — need `/compra` or seed expansion)
- Commission-aware backtest (see FUTURE.md)
- Prometheus metrics endpoint
- LSE market hours in config.yaml
