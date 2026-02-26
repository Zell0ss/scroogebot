# TOMORROW — ScroogeBot next session context

## Status: Parts 1, 2, 3 + extras COMPLETE ✅

All features implemented, tested (173/173 pass), committed and pushed to
https://github.com/Zell0ss/scroogebot

---

## What was done today (2026-02-26 session)

### Basket name normalization (main feature):
- `src/utils/text.py`: `normalize_basket_name()` — NFKD + combining-char strip + lowercase + whitespace collapse
- `Basket.name_normalized`: new DB column (`unique=True`, `nullable=False`), migration `a621def3cced`
- `src/db/seed.py`: updated to populate `name_normalized`
- All 11 basket lookup sites in 5 handlers updated to use `Basket.name_normalized == normalize_basket_name(var)`
- `/crearcesta` dup check covers all baskets (active + inactive), global uniqueness
- `/eliminarcesta` now mangles both `basket.name` AND `basket.name_normalized` on soft-delete (consistent reuse)
- 8 unit tests in `tests/test_normalize.py`

### Bug fixes:
- **`/estado` counters showed 0**: prometheus_client strips `_total` from `mf.name` in `collect()` but preserves it in `sample.name`. Fixed: `mf.name == "scroogebot_commands"` (not `"scroogebot_commands_total"`).
- **Stale DB connections**: `create_async_engine` had no pool health options. Added `pool_pre_ping=True` + `pool_recycle=3600` in `src/db/base.py`. Prevents `OperationalError: (2013, 'Lost connection to MySQL server')` after idle periods.

### Enriched alerts (completed this session — was in progress from previous):
- `src/alerts/market_context.py`: `MarketContext` dataclass + `compute_market_context()`
- `AlertEngine._notify()`: enriched message with SMA20/50, RSI14, ATR%, trend, confidence, P&L, suggested_qty
- Claude Haiku educational explanation for non-advanced users
- `/modo [avanzado|basico]`: toggle `User.advanced_mode` (default=False)
- Migration for `User.advanced_mode` boolean column

---

## Metrics port
Port **9010** (configured in `config/config.yaml`). Access: `curl http://localhost:9010/metrics`

---

## Deploy steps (production)
```bash
alembic upgrade head      # applies basket name_normalized + User.advanced_mode migrations
sudo systemctl restart scroogebot
```

---

## Possible next improvements (from FUTURE.md)
- Commission-aware backtest (`fees=` param to vectorbt)
- Backtest warmup period fix (extra data before eval window)
- `/cestas_archivadas` admin command to list soft-deleted baskets
- Prometheus + Grafana Docker Compose stack
- LSE market hours edge case (UTC+1 in summer)
- Additional metrics: `scroogebot_positions_total`, `scroogebot_portfolio_value_eur`
