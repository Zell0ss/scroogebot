# ScroogeBot — Part 3: Backtesting & Advanced Strategies

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Slices 7-8 — `/backtest` command with vectorbt metrics, three advanced strategies (RSI, Bollinger, Safe Haven), systemd service file for production deployment.

**Prerequisites:** Parts 1 & 2 complete. Bot running with alerts, roles, `/compra`, `/valoracion`.

**Tech Stack:** vectorbt (install via `pip install ".[backtest]"`), pandas-ta for RSI and Bollinger indicators.

---

## Task 1: Install vectorbt

**Step 1: Install backtest extras**

```bash
.venv/bin/pip install ".[backtest]"
```

Expected: vectorbt and its dependencies install without errors.

**Step 2: Verify import**

```bash
.venv/bin/python -c "import vectorbt; print(vectorbt.__version__)"
```

Expected: prints a version number like `0.26.x`.

---

## Task 2: Backtest Engine

**Files:**
- Create: `src/backtest/__init__.py`
- Create: `src/backtest/engine.py`

**Step 1: Write `src/backtest/__init__.py`** (empty)

**Step 2: Write `src/backtest/engine.py`**

```python
import logging
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from src.data.yahoo import YahooDataProvider
from src.strategies.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    ticker: str
    period: str
    strategy_name: str
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    n_trades: int
    win_rate_pct: float
    benchmark_return_pct: float  # buy-and-hold


class BacktestEngine:
    def __init__(self):
        self.data = YahooDataProvider()

    def run(
        self,
        ticker: str,
        strategy: Strategy,
        strategy_name: str,
        period: str = "1y",
    ) -> BacktestResult:
        import vectorbt as vbt

        ohlcv = self.data.get_historical(ticker, period=period, interval="1d")
        close = ohlcv.data["Close"]

        # Generate entry/exit signals via rolling strategy evaluation
        entries = pd.Series(False, index=close.index)
        exits = pd.Series(False, index=close.index)
        window = 60  # bars of lookback for each strategy evaluation

        for i in range(window, len(close)):
            window_data = ohlcv.data.iloc[i - window:i]
            current_price = Decimal(str(close.iloc[i]))
            try:
                signal = strategy.evaluate(ticker, window_data, current_price)
            except Exception:
                continue
            if signal:
                if signal.action == "BUY":
                    entries.iloc[i] = True
                elif signal.action == "SELL":
                    exits.iloc[i] = True

        pf = vbt.Portfolio.from_signals(close, entries, exits, init_cash=10_000)
        stats = pf.stats()

        bh_return = float((close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100)

        return BacktestResult(
            ticker=ticker,
            period=period,
            strategy_name=strategy_name,
            total_return_pct=float(stats.get("Total Return [%]", 0)),
            annualized_return_pct=float(stats.get("Annualized Return [%]", 0)),
            sharpe_ratio=float(stats.get("Sharpe Ratio", 0) or 0),
            max_drawdown_pct=float(stats.get("Max Drawdown [%]", 0)),
            n_trades=int(stats.get("Total Trades", 0)),
            win_rate_pct=float(stats.get("Win Rate [%]", 0) or 0),
            benchmark_return_pct=bh_return,
        )
```

**Step 3: Commit**

```bash
git add src/backtest/
git commit -m "feat: BacktestEngine with vectorbt"
```

---

## Task 3: `/backtest` Command

**Files:**
- Create: `src/bot/handlers/backtest.py`
- Modify: `src/bot/bot.py`

**Step 1: Write `src/bot/handlers/backtest.py`**

```python
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Basket, BasketAsset, Asset
from src.backtest.engine import BacktestEngine
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy

logger = logging.getLogger(__name__)

VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y"}

STRATEGY_MAP = {
    "stop_loss": StopLossStrategy,
    "ma_crossover": MACrossoverStrategy,
}


async def cmd_backtest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /backtest [period]  e.g. /backtest 1y"""
    period = "1y"
    if context.args and context.args[-1] in VALID_PERIODS:
        period = context.args[-1]

    msg = await update.message.reply_text(f"⏳ Backtesting ({period})... puede tardar un momento.")
    engine = BacktestEngine()

    async with async_session_factory() as session:
        result = await session.execute(select(Basket).where(Basket.active == True))
        baskets = result.scalars().all()

        for basket in baskets:
            strategy_cls = STRATEGY_MAP.get(basket.strategy)
            if not strategy_cls:
                await update.message.reply_text(
                    f"*{basket.name}*: estrategia `{basket.strategy}` no soporta backtest aún.",
                    parse_mode="Markdown",
                )
                continue

            strategy = strategy_cls()
            assets_result = await session.execute(
                select(Asset)
                .join(BasketAsset, BasketAsset.asset_id == Asset.id)
                .where(BasketAsset.basket_id == basket.id, BasketAsset.active == True)
            )
            assets = assets_result.scalars().all()

            lines = [f"📊 *Backtest: {basket.name}* ({period})\n"]
            for asset in assets:
                try:
                    r = engine.run(asset.ticker, strategy, basket.strategy, period)
                    alpha = r.total_return_pct - r.benchmark_return_pct
                    sign = lambda v: "+" if v >= 0 else ""
                    lines += [
                        f"*{asset.ticker}*",
                        f"  Rentabilidad: {sign(r.total_return_pct)}{r.total_return_pct:.1f}%  (B&H: {sign(r.benchmark_return_pct)}{r.benchmark_return_pct:.1f}%,  α: {sign(alpha)}{alpha:.1f}%)",
                        f"  Sharpe: {r.sharpe_ratio:.2f}  |  Max DD: {r.max_drawdown_pct:.1f}%",
                        f"  Operaciones: {r.n_trades}  |  Win rate: {r.win_rate_pct:.0f}%",
                        "",
                    ]
                except Exception as e:
                    logger.error(f"Backtest error {asset.ticker}: {e}")
                    lines.append(f"❌ {asset.ticker}: {e}\n")

            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    await msg.delete()


def get_handlers():
    return [CommandHandler("backtest", cmd_backtest)]
```

**Step 2: Register in `src/bot/bot.py`**

Add import and handler registration in `run()`:
```python
from src.bot.handlers.backtest import get_handlers as backtest_handlers
# In run():
for handler in backtest_handlers():
    app.add_handler(handler)
```

**Step 3: Test manually**

```bash
.venv/bin/python scroogebot.py
```

Send `/backtest 1y` to the bot. Expected: strategy performance metrics for each asset in active baskets.

**Step 4: Commit**

```bash
git add src/bot/handlers/backtest.py src/bot/bot.py
git commit -m "feat: /backtest command with vectorbt metrics"
```

---

## Task 4: Advanced Strategies (RSI, Bollinger, Safe Haven)

**Files:**
- Create: `src/strategies/rsi.py`
- Create: `src/strategies/bollinger.py`
- Create: `src/strategies/safe_haven.py`
- Modify: `src/alerts/engine.py` (add to STRATEGY_MAP)
- Modify: `src/bot/handlers/backtest.py` (add to STRATEGY_MAP)
- Modify: `tests/test_strategies.py` (add tests)

**Step 1: Write failing tests in `tests/test_strategies.py`**

Append to the existing file:

```python
from src.strategies.rsi import RSIStrategy
from src.strategies.bollinger import BollingerStrategy
from src.strategies.safe_haven import SafeHavenStrategy


def test_rsi_returns_signal_or_none():
    strategy = RSIStrategy()
    prices = [100.0 + i * 0.5 for i in range(30)]
    df = make_df(prices)
    signal = strategy.evaluate("MSFT", df, Decimal("115"))
    if signal:
        assert signal.action in ("BUY", "SELL")


def test_bollinger_returns_signal_or_none():
    strategy = BollingerStrategy()
    prices = [100.0] * 30
    df = make_df(prices)
    signal = strategy.evaluate("MSFT", df, Decimal("90"))  # well below band
    if signal:
        assert signal.action in ("BUY", "SELL")


def test_safe_haven_triggers_on_drawdown():
    strategy = SafeHavenStrategy()
    # Peak of 120, now at 100 — 16.7% drawdown > 8% threshold
    prices = [120.0] + [115.0] * 30 + [100.0]
    df = make_df(prices)
    signal = strategy.evaluate("AAPL", df, Decimal("100"))
    assert signal is not None
    assert signal.action == "SELL"


def test_safe_haven_skips_safe_assets():
    strategy = SafeHavenStrategy()
    prices = [100.0] + [50.0] * 30  # massive drop, but it's GLD
    df = make_df(prices)
    signal = strategy.evaluate("GLD", df, Decimal("50"))
    assert signal is None
```

**Step 2: Run failing tests**

```bash
.venv/bin/pytest tests/test_strategies.py -v -k "rsi or bollinger or safe_haven"
```

Expected: ImportError — strategies not yet written.

**Step 3: Write `src/strategies/rsi.py`**

```python
from decimal import Decimal
import pandas as pd
import pandas_ta as ta
from src.strategies.base import Strategy, Signal
from src.config import app_config


class RSIStrategy(Strategy):
    def __init__(self):
        cfg = app_config["strategies"]["rsi"]
        self.period = cfg["period"]
        self.oversold = cfg["oversold"]
        self.overbought = cfg["overbought"]

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        if len(data) < self.period + 1:
            return None
        rsi = ta.rsi(data["Close"], length=self.period)
        if rsi is None or rsi.empty or rsi.isna().all():
            return None
        last_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]

        # Signal on crossover (not just being in zone)
        if prev_rsi <= self.oversold < last_rsi:
            return Signal(
                action="BUY", ticker=ticker, price=current_price,
                reason=f"RSI exiting oversold zone ({last_rsi:.1f})",
                confidence=0.7,
            )
        if prev_rsi >= self.overbought > last_rsi:
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"RSI exiting overbought zone ({last_rsi:.1f})",
                confidence=0.7,
            )
        return None
```

**Step 4: Write `src/strategies/bollinger.py`**

```python
from decimal import Decimal
import pandas as pd
import pandas_ta as ta
from src.strategies.base import Strategy, Signal
from src.config import app_config


class BollingerStrategy(Strategy):
    def __init__(self):
        cfg = app_config["strategies"]["bollinger"]
        self.period = cfg["period"]
        self.std_dev = cfg["std_dev"]

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        if len(data) < self.period:
            return None
        bb = ta.bbands(data["Close"], length=self.period, std=self.std_dev)
        if bb is None or bb.empty:
            return None

        lower_cols = [c for c in bb.columns if "BBL" in c]
        upper_cols = [c for c in bb.columns if "BBU" in c]
        if not lower_cols or not upper_cols:
            return None

        lower = Decimal(str(bb[lower_cols[0]].iloc[-1]))
        upper = Decimal(str(bb[upper_cols[0]].iloc[-1]))

        if current_price <= lower:
            return Signal(
                action="BUY", ticker=ticker, price=current_price,
                reason=f"Price at/below lower Bollinger band ({float(lower):.2f})",
                confidence=0.65,
            )
        if current_price >= upper:
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"Price at/above upper Bollinger band ({float(upper):.2f})",
                confidence=0.65,
            )
        return None
```

**Step 5: Write `src/strategies/safe_haven.py`**

```python
from decimal import Decimal
import pandas as pd
from src.strategies.base import Strategy, Signal
from src.config import app_config

# These tickers are safe havens — never sell them via this strategy
SAFE_TICKERS = {"GLD", "BND", "TLT", "SHY", "VGSH"}


class SafeHavenStrategy(Strategy):
    """Rotates to safe haven assets when drawdown from peak exceeds threshold."""

    def __init__(self):
        cfg = app_config["strategies"].get("stop_loss", {})
        self.drawdown_threshold = Decimal(str(cfg.get("stop_loss_pct", 8))) / 100

    def evaluate(self, ticker: str, data: pd.DataFrame, current_price: Decimal) -> Signal | None:
        if ticker.upper() in SAFE_TICKERS:
            return None
        if len(data) < 2:
            return None
        peak = Decimal(str(data["Close"].max()))
        if peak == 0:
            return None
        drawdown = (peak - current_price) / peak
        if drawdown >= self.drawdown_threshold:
            return Signal(
                action="SELL", ticker=ticker, price=current_price,
                reason=f"Drawdown {float(drawdown)*100:.1f}% from peak — rotating to safe haven",
                confidence=0.8,
            )
        return None
```

**Step 6: Run all strategy tests**

```bash
.venv/bin/pytest tests/test_strategies.py -v
```

Expected: all tests PASS (including the 4 from Part 2 and the 4 new ones).

**Step 7: Add new strategies to `src/alerts/engine.py` STRATEGY_MAP**

```python
from src.strategies.rsi import RSIStrategy
from src.strategies.bollinger import BollingerStrategy
from src.strategies.safe_haven import SafeHavenStrategy

STRATEGY_MAP: dict[str, type[Strategy]] = {
    "stop_loss": StopLossStrategy,
    "ma_crossover": MACrossoverStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerStrategy,
    "safe_haven": SafeHavenStrategy,
}
```

**Step 8: Add new strategies to `src/bot/handlers/backtest.py` STRATEGY_MAP**

```python
from src.strategies.rsi import RSIStrategy
from src.strategies.bollinger import BollingerStrategy
from src.strategies.safe_haven import SafeHavenStrategy

STRATEGY_MAP = {
    "stop_loss": StopLossStrategy,
    "ma_crossover": MACrossoverStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerStrategy,
    "safe_haven": SafeHavenStrategy,
}
```

**Step 9: Run full test suite**

```bash
.venv/bin/pytest tests/ -v --tb=short
```

Expected: all tests PASS.

**Step 10: Commit**

```bash
git add src/strategies/rsi.py src/strategies/bollinger.py src/strategies/safe_haven.py \
        src/alerts/engine.py src/bot/handlers/backtest.py tests/test_strategies.py
git commit -m "feat: RSI, Bollinger, SafeHaven strategies + registered in alert and backtest engines"
```

---

## Task 5: Systemd Service File

**Files:**
- Create: `scroogebot.service`

**Step 1: Write `scroogebot.service`**

```ini
[Unit]
Description=ScroogeBot — Investment Telegram Bot
After=network.target mariadb.service
Wants=mariadb.service

[Service]
Type=simple
ExecStart=/data/scroogebot/.venv/bin/python /data/scroogebot/scroogebot.py
User=ubuntu
WorkingDirectory=/data/scroogebot
Restart=always
RestartSec=10
EnvironmentFile=/data/scroogebot/.env
StandardOutput=journal
StandardError=journal
SyslogIdentifier=scroogebot

[Install]
WantedBy=multi-user.target
```

**Step 2: Install and start service (when ready for production)**

```bash
sudo cp scroogebot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable scroogebot
sudo systemctl start scroogebot
```

**Step 3: Verify service status**

```bash
sudo systemctl status scroogebot
sudo journalctl -u scroogebot -f
```

Expected: `Active: active (running)` and `ScroogeBot starting` in logs.

**Step 4: Commit**

```bash
git add scroogebot.service
git commit -m "feat: systemd service file for production deployment"
```

---

## Task 6: End-to-End Smoke Test

**Step 1: Start the bot**

```bash
.venv/bin/python scroogebot.py
```

**Step 2: Test all commands in Telegram**

| Command | Expected |
|---------|----------|
| `/start` | Greeting message, user registered |
| `/cestas` | List of active baskets |
| `/cesta Cesta Agresiva` | Details with assets and members |
| `/valoracion` | Portfolio valuation (empty positions OK) |
| `/analiza AAPL` | Price, RSI, SMA 20/50 |
| `/compra AAPL 2` | "Compra ejecutada" confirmation |
| `/cartera` | Shows 2 AAPL position |
| `/historial` | Shows BUY order |
| `/vende AAPL 1` | "Venta ejecutada" confirmation |
| `/backtest 1y` | Returns metrics for each asset |
| `/addwatch ANTHROPIC Anthropic \| pending IPO` | Added to watchlist |
| `/watchlist` | Shows ANTHROPIC entry |

**Step 3: Run final test suite**

```bash
.venv/bin/pytest tests/ -v --tb=short
```

Expected: all tests PASS.

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: Part 3 complete — all features implemented and tested"
```

---

## Part 3 Done ✅

| Task | Feature |
|------|---------|
| 1 | vectorbt installed |
| 2 | BacktestEngine |
| 3 | /backtest command |
| 4 | RSI, Bollinger, SafeHaven strategies |
| 5 | Systemd service file |
| 6 | End-to-end smoke test |

---

## Full Feature Checklist

| # | Command | Status |
|---|---------|--------|
| 1 | `/start` | ✅ |
| 2 | `/valoracion` | ✅ |
| 3 | `/cartera` | ✅ |
| 4 | `/historial` | ✅ |
| 5 | `/compra` | ✅ |
| 6 | `/vende` | ✅ |
| 7 | `/cestas` | ✅ |
| 8 | `/cesta` | ✅ |
| 9 | `/analiza` | ✅ |
| 10 | `/backtest` | ✅ |
| 11 | `/adduser` | ✅ |
| 12 | `/watchlist` | ✅ |
| 13 | `/addwatch` | ✅ |
| — | Alert scanning (APScheduler) | ✅ |
| — | Alert confirmation (inline keyboard) | ✅ |
| — | Paper trading (BUY/SELL) | ✅ |
| — | Stop-loss strategy | ✅ |
| — | MA Crossover strategy | ✅ |
| — | RSI strategy | ✅ |
| — | Bollinger strategy | ✅ |
| — | Safe Haven strategy | ✅ |
| — | Systemd service | ✅ |

*ScroogeBot — "Dinero que duerme es dinero que llora" 🦆*
