# Design: Fix StopLoss avg_price + Market Hours Guard

**Date**: 2026-02-23
**Status**: Approved

## Problem summary

Two semantic bugs that break paper-trading simulation fidelity:

### Bug 1 — StopLossStrategy uses period open, not avg_price

`StopLossStrategy.evaluate()` calculates the return from `data["Close"].iloc[0]`
(first day of the 3-month lookback window) instead of the position's real entry
price. For positions bought outside the window this can trigger at completely
wrong moments. The independent stop-loss layer in `AlertEngine` already uses
`pos.avg_price` correctly — only the strategy class is broken.

Root cause: `Strategy.evaluate()` signature has no position context.

### Bug 2 — Confirm callback executes at stale price when market is closed

The alert scanner already respects market hours (two-level guard: scan-wide +
per-asset). The bug is in `handle_alert_callback`: it fetches the "current"
price and executes without checking whether the market is open. A PENDING alert
from Friday can be confirmed on Saturday at Friday's close price.

Additionally, when a strategy condition no longer holds (price recovered,
MA re-crossed, etc.) the old PENDING alert lingers forever until manually
rejected or confirmed.

## Design

### Fix 1 — Pass avg_price through Strategy interface

**Files**: `src/strategies/base.py`, `src/strategies/stop_loss.py`,
`src/alerts/engine.py`

Add optional `avg_price: Decimal | None = None` to `Strategy.evaluate()`.
Only `StopLossStrategy` uses it; all other strategies ignore it.

```python
# base.py
@abstractmethod
def evaluate(
    self,
    ticker: str,
    data: pd.DataFrame,
    current_price: Decimal,
    avg_price: Decimal | None = None,
) -> Signal | None: ...
```

```python
# stop_loss.py
def evaluate(self, ticker, data, current_price, avg_price=None):
    reference = avg_price if avg_price and avg_price > 0 \
                else Decimal(str(data["Close"].iloc[0]))
    change = (current_price - reference) / reference
    # rest unchanged
```

```python
# alerts/engine.py — _scan_basket()
signal = strategy.evaluate(asset.ticker, historical.data, price_obj.price, pos.avg_price)
```

Fallback to `data["Close"].iloc[0]` preserved when `avg_price` is None
(backtest path, tests without a real position).

### Fix 2A — Market hours guard in handle_alert_callback

**File**: `src/bot/bot.py`

Before executing on `action == "confirm"`, check if the asset's market is open:

```python
if asset.market and not is_market_open(asset.market):
    await query.edit_message_text(
        f"❌ Mercado {asset.market} cerrado ahora.\n"
        "La alerta sigue activa — confírmala cuando abra el mercado,\n"
        "o usa /compra para ejecutar manualmente."
    )
    return   # alert stays PENDING
```

Import `is_market_open` at the top of `bot.py`.

### Fix 2B — Auto-expire stale PENDING alerts in the scan loop

**File**: `src/alerts/engine.py` — `_scan_basket()`

New status value: `"EXPIRED"` (no migration needed — `Alert.status` is
`String(20)`, no enum constraint).

Current dedup logic skips when PENDING alert exists regardless of whether the
condition still holds. Replace with:

```
if existing PENDING alert for this asset/basket:
    if signal is None (condition no longer holds):
        mark alert EXPIRED, resolved_at = now
        # do NOT skip — allow a new alert if condition re-triggers next scan
    else:
        skip (condition still holds, alert already notified)
        continue
```

This ensures PENDING alerts reflect the *current* market state and do not
accumulate over weekends or after conditions reverse.

## Tests

| File | Test name | What it verifies |
|------|-----------|-----------------|
| `tests/test_strategies.py` | `test_stop_loss_uses_avg_price_when_provided` | StopLoss fires on avg_price drop, not period open |
| `tests/test_strategies.py` | `test_stop_loss_falls_back_to_period_open_when_no_avg_price` | avg_price=None falls back correctly |
| `tests/test_alert_engine.py` | `test_scan_passes_avg_price_to_strategy` | Engine calls evaluate with pos.avg_price |
| `tests/test_alert_engine.py` | `test_scan_expires_stale_pending_alert` | Scan marks EXPIRED when condition gone |
| `tests/test_alert_engine.py` | `test_scan_keeps_pending_when_condition_still_holds` | Dedup unchanged when still triggered |
| `tests/test_bot.py` | `test_confirm_blocked_when_market_closed` | Callback returns closed-market message, alert stays PENDING |

## Out of scope

- No changes to `src/db/models.py` (no new column, `EXPIRED` is a string value)
- No Alembic migration needed
- Backtest and Monte Carlo paths unaffected (they don't use the live Strategy
  evaluate loop)
- Other four strategies (`ma_crossover`, `rsi`, `bollinger`, `safe_haven`)
  receive `avg_price` in their signature but ignore it — no behaviour change
