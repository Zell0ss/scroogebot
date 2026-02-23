# Fix StopLoss avg_price + Market Hours Guard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix two paper-trading simulation bugs: StopLossStrategy using the wrong reference price, and alert confirmations executing at stale prices when markets are closed.

**Architecture:** Three files touched: `src/strategies/base.py` (ABC signature), `src/strategies/stop_loss.py` (use avg_price), `src/alerts/engine.py` (pass avg_price + expire stale alerts), `src/bot/bot.py` (market hours guard on confirm). All changes via TDD — tests first, RED verified, then minimal implementation.

**Tech Stack:** Python 3.11, pytest-asyncio, unittest.mock (AsyncMock/MagicMock), python-telegram-bot v20.

---

## Context

### Bug 1 — StopLossStrategy uses period open, not avg_price

`src/strategies/stop_loss.py:16` uses `data["Close"].iloc[0]` (first day of 3-month window) as reference price instead of the actual purchase price. `Strategy.evaluate()` doesn't receive position context.

Fix: add `avg_price: Decimal | None = None` to the ABC; `StopLossStrategy` uses it when provided, falls back to `data["Close"].iloc[0]` when not (backtest/test paths); `AlertEngine._scan_basket` passes `pos.avg_price`.

### Bug 2 — Confirm callback executes at stale price

`handle_alert_callback` in `src/bot/bot.py` does not check market hours before executing. A PENDING alert from Friday can be confirmed on Saturday at the Friday close price.

Fix A: guard in `handle_alert_callback` — if market closed, show "mercado cerrado" and keep alert PENDING.

Fix B (A+): in `_scan_basket`, when dedup finds a PENDING alert but the condition is no longer true (signal is None), mark it `EXPIRED` and commit. Prevents stale alert accumulation.

### Existing test file for AlertEngine

`tests/test_alert_engine_stoploss.py` has helpers `_make_basket`, `_make_position`, `_make_session`, `_mock_strategy`. Reuse them — **do not duplicate**.

`_make_session(position_pairs, has_pending_alert=False)` configures `session.execute` as `side_effect=[pos_result, dedup_result]`. Tests with 2+ execute calls need custom session mocks.

---

## Task 1: Extend Strategy ABC signature

**Files:**
- Modify: `src/strategies/base.py`

**Step 1: Make the change**

```python
# src/strategies/base.py
class Strategy(ABC):
    @abstractmethod
    def evaluate(
        self,
        ticker: str,
        data: pd.DataFrame,
        current_price: Decimal,
        avg_price: Decimal | None = None,
    ) -> Signal | None:
        """Return a Signal or None (hold)."""
        ...
```

No other change needed — the four other strategies inherit the new optional parameter automatically. Python doesn't require them to declare it.

**Step 2: Run existing strategy tests to confirm nothing breaks**

```bash
.venv/bin/pytest tests/test_strategies.py -v
```

Expected: all existing tests still PASS (they don't pass `avg_price`).

**Step 3: Commit**

```bash
git add src/strategies/base.py
git commit -m "refactor: add optional avg_price param to Strategy.evaluate() ABC"
```

---

## Task 2: Fix StopLossStrategy to use avg_price

**Files:**
- Modify: `tests/test_strategies.py` (add 2 tests)
- Modify: `src/strategies/stop_loss.py`

**Step 1: Write two failing tests** — append to `tests/test_strategies.py`:

```python
def test_stop_loss_uses_avg_price_when_provided():
    """StopLoss fires based on avg_price, not the first Close of the window."""
    strategy = StopLossStrategy()
    # period-open is 100 (no drop) but avg_price is 200 (big drop from actual buy)
    df = make_df([100.0] * 61)
    signal = strategy.evaluate("AAPL", df, Decimal("170"), avg_price=Decimal("200"))
    # 170 vs 200 = -15% drop, above 8% stop-loss threshold
    assert signal is not None
    assert signal.action == "SELL"
    assert "Stop-loss" in signal.reason


def test_stop_loss_falls_back_to_period_open_when_no_avg_price():
    """When avg_price is None, StopLoss falls back to data['Close'].iloc[0]."""
    strategy = StopLossStrategy()
    df = make_df([100.0] * 61)
    signal = strategy.evaluate("AAPL", df, Decimal("88"))  # 12% from period open
    assert signal is not None
    assert signal.action == "SELL"
```

**Step 2: Run to verify RED**

```bash
.venv/bin/pytest tests/test_strategies.py::test_stop_loss_uses_avg_price_when_provided -v
```

Expected: FAIL — the first test passes a `170` price vs period open `100` (a 70% gain), but currently uses period open and sees no stop-loss trigger.

**Step 3: Implement the fix** in `src/strategies/stop_loss.py`:

```python
def evaluate(
    self,
    ticker: str,
    data: pd.DataFrame,
    current_price: Decimal,
    avg_price: Decimal | None = None,
) -> Signal | None:
    if len(data) < 2:
        return None
    reference = (
        avg_price
        if avg_price and avg_price > 0
        else Decimal(str(data["Close"].iloc[0]))
    )
    if reference == 0:
        return None
    change = (current_price - reference) / reference

    if change <= -self.stop_loss_pct:
        return Signal(
            action="SELL", ticker=ticker, price=current_price,
            reason=f"Stop-loss triggered: {change*100:.1f}% drop",
            confidence=0.95,
        )
    if change >= self.take_profit_pct:
        return Signal(
            action="SELL", ticker=ticker, price=current_price,
            reason=f"Take-profit triggered: {change*100:.1f}% gain",
            confidence=0.9,
        )
    return None
```

**Step 4: Run all strategy tests**

```bash
.venv/bin/pytest tests/test_strategies.py -v
```

Expected: all PASS (5 original + 2 new = 7 tests).

**Step 5: Commit**

```bash
git add src/strategies/stop_loss.py tests/test_strategies.py
git commit -m "fix: StopLossStrategy uses avg_price when provided, falls back to period open"
```

---

## Task 3: AlertEngine passes avg_price to strategy.evaluate()

**Files:**
- Modify: `tests/test_alert_engine_stoploss.py` (add 1 test)
- Modify: `src/alerts/engine.py` (one-line change)

**Step 1: Write a failing test** — append to `tests/test_alert_engine_stoploss.py`:

```python
@pytest.mark.asyncio
async def test_scan_passes_avg_price_to_strategy():
    """AlertEngine passes pos.avg_price as the 4th arg to strategy.evaluate()."""
    basket = _make_basket(stop_loss_pct=None, strategy="rsi")
    pos, asset = _make_position(avg_price=150.0)
    current_price = Decimal("160.0")

    session_cm = _make_session([(pos, asset)])
    price_mock = MagicMock()
    price_mock.price = current_price
    hist_mock = MagicMock(data=MagicMock())

    engine = AlertEngine(telegram_app=None)
    mock_cls = _mock_strategy(return_value=None)

    with (
        patch("src.alerts.engine.async_session_factory", return_value=session_cm),
        patch.object(engine.data, "get_current_price", return_value=price_mock),
        patch.object(engine.data, "get_historical", return_value=hist_mock),
        patch("src.alerts.engine.is_market_open", return_value=True),
        patch.dict("src.alerts.engine.STRATEGY_MAP", {"rsi": mock_cls}),
    ):
        await engine._scan_basket(basket)

    instance = mock_cls.return_value
    call_args = instance.evaluate.call_args
    # 4th positional arg (index 3) or keyword 'avg_price' must be pos.avg_price
    passed_avg_price = (
        call_args.kwargs.get("avg_price")
        or (call_args.args[3] if len(call_args.args) > 3 else None)
    )
    assert passed_avg_price == pos.avg_price
```

**Step 2: Run to verify RED**

```bash
.venv/bin/pytest tests/test_alert_engine_stoploss.py::test_scan_passes_avg_price_to_strategy -v
```

Expected: FAIL — `evaluate` is called with 3 args, not 4.

**Step 3: Implement** — in `src/alerts/engine.py`, find the `strategy.evaluate` call (line ~83) and add `pos.avg_price`:

```python
# before (line ~83)
signal = strategy.evaluate(asset.ticker, historical.data, price_obj.price)

# after
signal = strategy.evaluate(asset.ticker, historical.data, price_obj.price, pos.avg_price)
```

Also add `from datetime import datetime` to the imports at the top of `engine.py` (needed for Task 5).

**Step 4: Run all alert engine tests**

```bash
.venv/bin/pytest tests/test_alert_engine_stoploss.py -v
```

Expected: all PASS (4 original + 1 new = 5 tests).

**Step 5: Commit**

```bash
git add src/alerts/engine.py tests/test_alert_engine_stoploss.py
git commit -m "fix: AlertEngine passes pos.avg_price to strategy.evaluate()"
```

---

## Task 4: Market hours guard in handle_alert_callback

**Files:**
- Create: `tests/test_bot_callback.py`
- Modify: `src/bot/bot.py`

**Step 1: Write failing test** — create `tests/test_bot_callback.py`:

```python
"""Tests for handle_alert_callback in bot.py."""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.bot import handle_alert_callback


def _make_query(data="alert:confirm:1", from_user_id=999):
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.from_user = MagicMock()
    query.from_user.id = from_user_id
    return query


def _make_update(query):
    update = MagicMock()
    update.callback_query = query
    return update


def _make_alert(alert_id=1, status="PENDING", signal="SELL", asset_id=10, basket_id=5):
    alert = MagicMock()
    alert.id = alert_id
    alert.status = status
    alert.signal = signal
    alert.asset_id = asset_id
    alert.basket_id = basket_id
    return alert


def _make_asset(market="NYSE"):
    asset = MagicMock()
    asset.ticker = "AAPL"
    asset.market = market
    return asset


def _make_session_for_callback(alert, asset, basket, user, is_member=True):
    """Build a session mock for the confirm callback flow."""
    # session.get is called 3 times: Alert, Asset, Basket
    session = MagicMock()
    session.get = AsyncMock(side_effect=[alert, asset, basket])

    # session.execute is called twice: User lookup, BasketMember check
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user

    member_result = MagicMock()
    member_result.scalar_one_or_none.return_value = MagicMock() if is_member else None

    session.execute = AsyncMock(side_effect=[user_result, member_result])
    session.commit = AsyncMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, session


@pytest.mark.asyncio
async def test_confirm_blocked_when_market_closed():
    """If asset.market is closed, confirm returns error message and alert stays PENDING."""
    query = _make_query("alert:confirm:1")
    update = _make_update(query)
    context = MagicMock()

    alert = _make_alert()
    asset = _make_asset(market="NYSE")
    basket = MagicMock()
    basket.id = 5
    user = MagicMock()
    user.id = 1

    session_cm, session = _make_session_for_callback(alert, asset, basket, user)

    with (
        patch("src.bot.bot.async_session_factory", return_value=session_cm),
        patch("src.bot.bot.is_market_open", return_value=False),
    ):
        await handle_alert_callback(update, context)

    # Must tell user market is closed
    query.edit_message_text.assert_called_once()
    msg = query.edit_message_text.call_args[0][0]
    assert "cerrado" in msg.lower() or "closed" in msg.lower()

    # Alert must NOT be committed (stays PENDING)
    session.commit.assert_not_called()
    assert alert.status == "PENDING"
```

**Step 2: Run to verify RED**

```bash
.venv/bin/pytest tests/test_bot_callback.py::test_confirm_blocked_when_market_closed -v
```

Expected: FAIL — no market hours check exists, trade would execute normally.

**Step 3: Implement** — in `src/bot/bot.py`:

Add `from src.scheduler.market_hours import is_market_open` at the top of the file (with the other src imports).

Inside `handle_alert_callback`, after retrieving `asset` and `basket` (and after the membership check), add the guard at the start of the `if action == "confirm":` block:

```python
if action == "confirm":
    # Guard: do not execute at stale prices when market is closed
    if asset.market and not is_market_open(asset.market):
        await query.edit_message_text(
            f"❌ Mercado {asset.market} cerrado ahora.\n"
            "La alerta sigue activa — confírmala cuando abra el mercado,\n"
            "o usa /compra para ejecutar manualmente."
        )
        return
    try:
        # ... rest of confirm unchanged
```

**Step 4: Run test**

```bash
.venv/bin/pytest tests/test_bot_callback.py -v
```

Expected: PASS.

**Step 5: Run full suite to check no regressions**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all existing tests still PASS.

**Step 6: Commit**

```bash
git add src/bot/bot.py tests/test_bot_callback.py
git commit -m "fix: block alert confirm when market is closed, alert stays PENDING"
```

---

## Task 5: Auto-expire stale PENDING alerts in scan loop

**Files:**
- Modify: `tests/test_alert_engine_stoploss.py` (add 2 tests)
- Modify: `src/alerts/engine.py`

### Understand the session mock shape

`_make_session` sets `session.execute = AsyncMock(side_effect=[pos_result, dedup_result])`.

For the expiry tests, the `dedup_result.scalar_one_or_none()` must return a **real MagicMock object** (not just a truthy value) so we can inspect `.status` after the call. Don't use the `_make_session` helper — build a custom one.

**Step 1: Write two failing tests** — append to `tests/test_alert_engine_stoploss.py`:

```python
@pytest.mark.asyncio
async def test_scan_expires_stale_pending_alert():
    """When strategy signal is None (condition gone), an existing PENDING alert is EXPIRED."""
    basket = _make_basket(stop_loss_pct=None, strategy="rsi")
    pos, asset = _make_position(avg_price=100.0)
    current_price = Decimal("100.0")

    # Build existing PENDING alert as a real mock we can inspect
    existing_alert = MagicMock()
    existing_alert.status = "PENDING"

    pos_result = MagicMock()
    pos_result.all.return_value = [(pos, asset)]

    dedup_result = MagicMock()
    dedup_result.scalar_one_or_none.return_value = existing_alert

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[pos_result, dedup_result])
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    price_mock = MagicMock()
    price_mock.price = current_price

    engine = AlertEngine(telegram_app=None)
    mock_cls = _mock_strategy(return_value=None)  # ← condition gone: signal = None

    with (
        patch("src.alerts.engine.async_session_factory", return_value=session_cm),
        patch.object(engine.data, "get_current_price", return_value=price_mock),
        patch.object(engine.data, "get_historical", return_value=MagicMock(data=MagicMock())),
        patch("src.alerts.engine.is_market_open", return_value=True),
        patch.dict("src.alerts.engine.STRATEGY_MAP", {"rsi": mock_cls}),
    ):
        await engine._scan_basket(basket)

    # Stale alert must have been expired
    assert existing_alert.status == "EXPIRED"
    # And persisted
    session.commit.assert_called_once()
    # No new alert was added
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_scan_keeps_pending_when_condition_still_holds():
    """When signal is not None and PENDING exists, dedup runs — alert stays PENDING, no new alert."""
    basket = _make_basket(stop_loss_pct=None, strategy="rsi")
    pos, asset = _make_position(avg_price=100.0)
    current_price = Decimal("80.0")

    existing_alert = MagicMock()
    existing_alert.status = "PENDING"

    pos_result = MagicMock()
    pos_result.all.return_value = [(pos, asset)]

    dedup_result = MagicMock()
    dedup_result.scalar_one_or_none.return_value = existing_alert

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[pos_result, dedup_result])
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    price_mock = MagicMock()
    price_mock.price = current_price

    sell_signal = Signal(action="SELL", ticker="SAN.MC", price=current_price,
                         reason="still below RSI threshold", confidence=0.7)

    engine = AlertEngine(telegram_app=None)
    mock_cls = _mock_strategy(return_value=sell_signal)  # ← condition still holds

    with (
        patch("src.alerts.engine.async_session_factory", return_value=session_cm),
        patch.object(engine.data, "get_current_price", return_value=price_mock),
        patch.object(engine.data, "get_historical", return_value=MagicMock(data=MagicMock())),
        patch("src.alerts.engine.is_market_open", return_value=True),
        patch.dict("src.alerts.engine.STRATEGY_MAP", {"rsi": mock_cls}),
    ):
        await engine._scan_basket(basket)

    # Alert was NOT expired (condition still holds)
    assert existing_alert.status == "PENDING"
    # No new alert created (dedup)
    session.add.assert_not_called()
    # No commit (nothing changed)
    session.commit.assert_not_called()
```

**Step 2: Run to verify RED**

```bash
.venv/bin/pytest tests/test_alert_engine_stoploss.py::test_scan_expires_stale_pending_alert tests/test_alert_engine_stoploss.py::test_scan_keeps_pending_when_condition_still_holds -v
```

Expected: FAIL — current code doesn't expire stale alerts.

**Step 3: Implement** — in `src/alerts/engine.py`, replace the dedup block in `_scan_basket`.

Current (around line 104–113):
```python
# Deduplicate: skip if a PENDING alert already exists
existing = await session.execute(
    select(Alert).where(
        Alert.basket_id == basket.id,
        Alert.asset_id == asset.id,
        Alert.status == "PENDING",
    )
)
if existing.scalar_one_or_none():
    continue
```

Replace with:
```python
# Deduplicate / expire stale alerts
existing = await session.execute(
    select(Alert).where(
        Alert.basket_id == basket.id,
        Alert.asset_id == asset.id,
        Alert.status == "PENDING",
    )
)
existing_alert = existing.scalar_one_or_none()
if existing_alert:
    if signal is None:
        # Condition no longer holds — expire the stale alert
        existing_alert.status = "EXPIRED"
        existing_alert.resolved_at = datetime.utcnow()
        expired_alerts.append(existing_alert)
    continue
```

Also, before the `for pos, asset in positions:` loop, declare:
```python
expired_alerts: list[Alert] = []
```

And at the end of `_scan_basket`, replace the final block:
```python
# current
if new_alerts:
    await session.flush()  # assign IDs before notify
    for alert, ticker in new_alerts:
        await self._notify(alert, basket.name, ticker)
    await session.commit()
```

With:
```python
if new_alerts:
    await session.flush()  # assign IDs before notify
    for alert, ticker in new_alerts:
        await self._notify(alert, basket.name, ticker)

if new_alerts or expired_alerts:
    await session.commit()
```

**Step 4: Run all alert engine tests**

```bash
.venv/bin/pytest tests/test_alert_engine_stoploss.py -v
```

Expected: all 7 tests PASS (4 original + 1 from Task 3 + 2 new).

**Step 5: Run full suite**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all tests PASS (previous total + 5 new = ~151 tests).

**Step 6: Commit**

```bash
git add src/alerts/engine.py tests/test_alert_engine_stoploss.py
git commit -m "fix: auto-expire stale PENDING alerts when strategy condition clears"
```

---

## Task 6: Final verification and push

**Step 1: Full test suite**

```bash
.venv/bin/pytest tests/ -v --tb=short
```

Expected: all tests PASS. Note exact count.

**Step 2: Push**

```bash
git push
```

**Step 3: Smoke check — confirm BRIEFING.md known-limitations section needs updating**

The two items documented as known limitations are now fixed. If a `BRIEFING.md` or `FUTURE.md` references them, remove or update those entries so they don't mislead future sessions.

Search:
```bash
grep -r "avg_price\|period open\|market hours\|stale" docs/ BRIEFING.md FUTURE.md 2>/dev/null | grep -i "known\|limitation\|todo\|future"
```

Update any references found.

---

## Summary of changes

| File | Change |
|------|--------|
| `src/strategies/base.py` | Add `avg_price: Decimal \| None = None` to `evaluate()` |
| `src/strategies/stop_loss.py` | Use `avg_price` if provided, fallback to `data["Close"].iloc[0]` |
| `src/alerts/engine.py` | Pass `pos.avg_price` to `evaluate()`; expire stale PENDING alerts; add `from datetime import datetime` |
| `src/bot/bot.py` | Import `is_market_open`; guard confirm if market closed |
| `tests/test_strategies.py` | +2 tests for avg_price behavior |
| `tests/test_alert_engine_stoploss.py` | +3 tests (avg_price passthrough + expire/dedup) |
| `tests/test_bot_callback.py` | New file; 1 test for market-closed guard |
