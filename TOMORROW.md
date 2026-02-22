# TOMORROW — ScroogeBot next session context

## Status: Parts 1, 2, 3 + extras COMPLETE ✅

All features implemented, tested (144/144 pass), committed and pushed to
https://github.com/Zell0ss/scroogebot

---

## What was done today (2026-02-22 session 2)

### Stop-loss as independent per-basket risk layer (TDD, 144 tests):
- **`stop_loss_pct` field** on `Basket` model — Alembic migration `47858283c702` applied ✅
- **AlertEngine**: position-based stop-loss layer using `pos.avg_price` (not `data.iloc[0]`)
  — overrides any strategy signal when position is down ≥ threshold
- **BacktestEngine + MonteCarloAnalyzer**: pass `sl_stop=pct/100` to vectorbt
- **`/estrategia` extended**:
  - `/estrategia MiCesta rsi 8` → change strategy AND stop-loss
  - `/estrategia MiCesta 10` → change only stop-loss
  - `/estrategia MiCesta 0` → disable stop-loss
  - view mode shows current stop_loss_pct
- **`/nuevacesta` extended**: `/nuevacesta MiCesta rsi 8` → create with stop-loss
- **`/cesta`**: shows `Stop-loss: X%` in strategy line if configured
- **config.yaml**: model baskets get stop_loss_pct (StopLoss:8, MACrossover:8, RSI:10, Bollinger:12, SafeHaven:6%)
- **seed.py**: reads and stores `stop_loss_pct` from config
- New test files: `test_alert_engine_stoploss.py`, `test_backtest_engine.py`, `test_backtest_handler.py`, `test_cesta_handler.py`

### Previous session (2026-02-22 session 1):
- `/montecarlo` — registered in bot.py
- `/estrategia`, `/nuevacesta`, `/eliminarcesta`
- 5 cestas modelo, Makefile, `/sel`, fixed /compra /vende

### Earlier sessions:
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
