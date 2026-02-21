# How to Add a New Strategy

## Goal

By the end of this guide you will have a new strategy that ScroogeBot evaluates automatically on every scheduler tick.

## Context

Use this when you want the bot to scan positions using a custom signal — e.g., RSI oversold, Bollinger squeeze, safe-haven rotation. Strategies are decoupled from the alert engine via the `Strategy` ABC.

---

## Steps

### 1. Create `src/strategies/your_strategy.py`

```python
from decimal import Decimal
import pandas as pd
import ta.momentum  # or ta.volatility, etc.

from src.strategies.base import Strategy, Signal
from src.config import app_config


class YourStrategy(Strategy):
    def __init__(self):
        cfg = app_config["strategies"]["your_strategy"]
        self.threshold = cfg["threshold"]  # read params from config

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        if len(data) < 20:  # guard: not enough history
            return None

        close = data["Close"]
        # your indicator logic here — use ta library, NOT pandas-ta
        # Example: RSI
        rsi = ta.momentum.RSIIndicator(close=close, window=14).rsi()
        rsi_val = rsi.iloc[-1]
        if pd.isna(rsi_val):
            return None

        if rsi_val < self.threshold:
            return Signal(
                action="BUY",
                ticker=ticker,
                price=current_price,
                reason=f"RSI oversold: {rsi_val:.1f}",
                confidence=0.8,
            )
        return None
```

**Why**: The `Strategy` ABC enforces the `evaluate()` contract. Any class that doesn't implement it raises `TypeError` at instantiation — fail-fast.

**ta library API** (critical — NOT `pandas-ta`):
```python
ta.momentum.RSIIndicator(close=series, window=14).rsi()           # pd.Series
ta.volatility.BollingerBands(close=series, window=20, window_dev=2)
    .bollinger_hband() / .bollinger_lband() / .bollinger_mavg()
ta.trend.SMAIndicator(close=series, window=50).sma_indicator()
```

---

### 2. Add to `STRATEGY_MAP` in `src/alerts/engine.py`

```python
from src.strategies.your_strategy import YourStrategy

STRATEGY_MAP: dict[str, type[Strategy]] = {
    "stop_loss": StopLossStrategy,
    "ma_crossover": MACrossoverStrategy,
    "your_strategy": YourStrategy,   # ← add this line
}
```

---

### 3. Add parameters to `config/config.yaml`

```yaml
strategies:
  your_strategy:
    threshold: 30   # RSI oversold level, for example
```

---

### 4. Assign strategy to a basket in `config/config.yaml`

```yaml
baskets:
  - name: "Mi Cesta"
    strategy: your_strategy   # ← matches STRATEGY_MAP key
    risk_profile: moderate
    cash: 5000.0
    assets: [AAPL, MSFT]
```

Re-seed if the basket is new:
```bash
python -c "import asyncio; from src.db.seed import seed; asyncio.run(seed())"
```

---

### 5. Write tests

Add to `tests/test_strategies.py`:

```python
from src.strategies.your_strategy import YourStrategy

def test_your_strategy_buys_on_oversold():
    strategy = YourStrategy()
    prices = [100.0 - i * 0.5 for i in range(80)]  # declining prices → low RSI
    df = make_df(prices)
    signal = strategy.evaluate("AAPL", df, Decimal("60"))
    if signal:
        assert signal.action == "BUY"
```

```bash
.venv/bin/pytest tests/test_strategies.py -v
```

**Expected output**:
```
PASSED tests/test_strategies.py::test_your_strategy_buys_on_oversold
```

---

### 6. Verify

Restart the bot and check logs after the first scheduler tick:

```bash
python scroogebot.py
# After 5 minutes:
# INFO alerts.engine - Alert scan started
# INFO alerts.engine - ALERT [BUY] AAPL in Mi Cesta: RSI oversold: 28.3
```

---

## Troubleshooting

### Problem: Strategy silently ignored for a basket

**Cause**: Key in `STRATEGY_MAP` doesn't match `basket.strategy` in the DB.

**Solution**: Run `/cesta <basket-name>` in Telegram to see the stored strategy string, then match it exactly in `STRATEGY_MAP`.

### Problem: `KeyError: 'your_strategy'`

**Cause**: `app_config["strategies"]["your_strategy"]` missing from `config.yaml`.

**Solution**: Add the section to `config/config.yaml` and restart the bot.

### Problem: `TypeError: Can't instantiate abstract class`

**Cause**: `evaluate()` method is missing from your strategy class.

**Solution**: Make sure your class defines `def evaluate(self, ticker, data, current_price)`.
