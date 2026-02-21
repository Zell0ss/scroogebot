# /montecarlo Command Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `/montecarlo CESTA [N_SIMS] [HORIZONTE]` command that bootstraps N future
price paths per asset and runs the basket's strategy over each, returning a distribution
of outcomes (percentiles, VaR, CVaR, prob of loss) instead of a single historical number.

**Architecture:** `MonteCarloSimulator` generates bootstrapped paths from log returns;
`MonteCarloAnalyzer` runs the existing `Strategy.evaluate()` bar-by-bar on each path
(naive loop, no vectorization) and calls vectorbt once per simulation; `MonteCarloFormatter`
produces the Telegram message. Handler in `src/bot/handlers/montecarlo.py`, engine in
`src/backtest/montecarlo.py`. No changes to `BacktestEngine` or `Strategy` ABC.

**Tech Stack:** numpy (bootstrapping, percentiles), pandas, vectorbt (portfolio simulation),
python-telegram-bot, SQLAlchemy async, yfinance.

**Design doc:** `docs/plans/2026-02-22-montecarlo-design.md`

---

## Task 1: MonteCarloSimulator — path generation

**Files:**
- Create: `src/backtest/montecarlo.py`
- Create: `tests/test_montecarlo.py`

**Step 1: Write failing test**

Create `tests/test_montecarlo.py`:

```python
import numpy as np
import pandas as pd
import pytest

from src.backtest.montecarlo import MonteCarloSimulator


def _make_hist_df(n: int = 120) -> pd.DataFrame:
    """120 bars of synthetic OHLCV data."""
    prices = pd.Series(
        [100.0 + i * 0.5 for i in range(n)],
        index=pd.date_range("2023-01-01", periods=n, freq="B"),
    )
    return pd.DataFrame({
        "Open": prices * 0.999,
        "High": prices * 1.005,
        "Low":  prices * 0.995,
        "Close": prices,
        "Volume": 1_000_000,
    })


def test_generate_paths_returns_n_paths():
    rng = np.random.default_rng(42)
    sim = MonteCarloSimulator()
    hist_df = _make_hist_df()
    paths = sim.generate_paths(hist_df, n_simulations=10, horizon=20, rng=rng)
    assert len(paths) == 10


def test_generate_paths_each_has_horizon_bars():
    rng = np.random.default_rng(42)
    sim = MonteCarloSimulator()
    hist_df = _make_hist_df()
    paths = sim.generate_paths(hist_df, n_simulations=5, horizon=30, rng=rng)
    assert all(len(p) == 30 for p in paths)


def test_generate_paths_prices_are_positive():
    rng = np.random.default_rng(42)
    sim = MonteCarloSimulator()
    hist_df = _make_hist_df()
    paths = sim.generate_paths(hist_df, n_simulations=20, horizon=90, rng=rng)
    assert all((p > 0).all() for p in paths)


def test_generate_paths_starts_near_last_real_price():
    rng = np.random.default_rng(42)
    sim = MonteCarloSimulator()
    hist_df = _make_hist_df()
    last_price = float(hist_df["Close"].iloc[-1])
    paths = sim.generate_paths(hist_df, n_simulations=50, horizon=5, rng=rng)
    first_prices = [float(p.iloc[0]) for p in paths]
    # First simulated price should be within ±30% of last real price (generous bound)
    assert all(last_price * 0.7 < fp < last_price * 1.3 for fp in first_prices)


def test_generate_paths_have_datetime_index():
    rng = np.random.default_rng(42)
    sim = MonteCarloSimulator()
    hist_df = _make_hist_df()
    paths = sim.generate_paths(hist_df, n_simulations=3, horizon=10, rng=rng)
    for p in paths:
        assert isinstance(p.index, pd.DatetimeIndex)
```

**Step 2: Run tests to verify they fail**

```bash
cd /data/scroogebot
.venv/bin/pytest tests/test_montecarlo.py -v
```

Expected: `ImportError: cannot import name 'MonteCarloSimulator'`

**Step 3: Create `src/backtest/montecarlo.py` with just the simulator**

```python
import logging
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import pandas as pd

from src.strategies.base import Strategy

logger = logging.getLogger(__name__)

LOOKBACK = 60          # bars of real history used as warmup context per simulation
HIST_PERIOD = "2y"     # how much history to fetch for the returns pool


class MonteCarloSimulator:
    def generate_paths(
        self,
        hist_df: pd.DataFrame,
        n_simulations: int,
        horizon: int,
        rng: np.random.Generator,
    ) -> list[pd.Series]:
        """Bootstrap N synthetic Close price series of length `horizon`.

        Samples log returns with replacement from the historical pool and
        reconstructs price series starting from the last real Close price.
        Synthetic index uses business-day frequency after the last real date.
        """
        close = hist_df["Close"]
        log_returns = np.log(close / close.shift(1)).dropna().values
        last_price = float(close.iloc[-1])
        last_date = close.index[-1]

        future_dates = pd.bdate_range(
            start=last_date + pd.Timedelta(days=1), periods=horizon
        )

        paths = []
        for _ in range(n_simulations):
            sampled = rng.choice(log_returns, size=horizon, replace=True)
            prices = last_price * np.exp(np.cumsum(sampled))
            path = pd.Series(prices, index=future_dates, name="Close")
            paths.append(path)
        return paths
```

**Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_montecarlo.py -v -k "simulator or generate_paths"
```

Expected: all 5 tests PASS.

**Step 5: Commit**

```bash
git add src/backtest/montecarlo.py tests/test_montecarlo.py
git commit -m "feat: MonteCarloSimulator — bootstrapped path generation"
```

---

## Task 2: AssetMonteCarloResult dataclass + profile classifier

**Files:**
- Modify: `src/backtest/montecarlo.py` (append dataclass + helper)
- Modify: `tests/test_montecarlo.py` (append tests)

**Step 1: Write failing tests — append to `tests/test_montecarlo.py`**

```python
from src.backtest.montecarlo import AssetMonteCarloResult, _profile_line


def _make_result(**overrides) -> AssetMonteCarloResult:
    defaults = dict(
        ticker="TEST", n_simulations=100, horizon=90, strategy_name="stop_loss", seed=42,
        return_median=5.0, return_mean=4.5,
        return_p10=1.0, return_p90=9.0, return_p05=-2.0,
        prob_loss=0.15,
        max_dd_median=4.0, max_dd_p95=10.0,
        sharpe_median=1.1, win_rate_median=55.0,
        var_95=-2.0, cvar_95=-3.5,
    )
    defaults.update(overrides)
    return AssetMonteCarloResult(**defaults)


def test_profile_favorable():
    r = _make_result(prob_loss=0.10, sharpe_median=0.9)
    assert "favorable" in _profile_line(r).lower()


def test_profile_desfavorable_high_prob_loss():
    r = _make_result(prob_loss=0.45, sharpe_median=0.9)
    assert "desfavorable" in _profile_line(r).lower()


def test_profile_desfavorable_low_sharpe():
    r = _make_result(prob_loss=0.10, sharpe_median=0.3)
    assert "desfavorable" in _profile_line(r).lower()


def test_profile_moderado():
    r = _make_result(prob_loss=0.25, sharpe_median=0.6)
    assert "moderado" in _profile_line(r).lower()
```

**Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_montecarlo.py -v -k "profile"
```

Expected: `ImportError: cannot import name 'AssetMonteCarloResult'`

**Step 3: Append to `src/backtest/montecarlo.py`** (after the simulator class)

```python
# Thresholds for profile classification — adjust as needed
_PROB_LOSS_LOW = 0.20
_PROB_LOSS_HIGH = 0.40
_SHARPE_GOOD = 0.8
_SHARPE_LOW = 0.4


@dataclass
class AssetMonteCarloResult:
    ticker: str
    n_simulations: int
    horizon: int
    strategy_name: str
    seed: int
    # Return distribution
    return_median: float
    return_mean: float
    return_p10: float
    return_p90: float
    return_p05: float
    prob_loss: float          # fraction of simulations with negative return
    # Drawdown
    max_dd_median: float
    max_dd_p95: float         # 95th percentile worst drawdown
    # Quality
    sharpe_median: float
    win_rate_median: float
    # Tail risk
    var_95: float             # Value at Risk (5th percentile of returns)
    cvar_95: float            # Conditional VaR / Expected Shortfall


def _profile_line(r: AssetMonteCarloResult) -> str:
    """Single-line risk profile summary with emoji."""
    if r.prob_loss < _PROB_LOSS_LOW and r.sharpe_median > _SHARPE_GOOD:
        return "✅ Perfil favorable"
    if r.prob_loss > _PROB_LOSS_HIGH or r.sharpe_median < _SHARPE_LOW:
        return "🔴 Perfil desfavorable, considerar ajustes"
    return "⚠️ Perfil moderado, revisar riesgo"
```

**Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_montecarlo.py -v -k "profile or result"
```

Expected: 4 profile tests PASS.

**Step 5: Commit**

```bash
git add src/backtest/montecarlo.py tests/test_montecarlo.py
git commit -m "feat: AssetMonteCarloResult dataclass + profile classifier"
```

---

## Task 3: MonteCarloAnalyzer — signal loop + vectorbt + percentiles

**Files:**
- Modify: `src/backtest/montecarlo.py` (append analyzer class)
- Modify: `tests/test_montecarlo.py` (append integration test)

**Step 1: Write failing integration test — append to `tests/test_montecarlo.py`**

```python
from src.backtest.montecarlo import MonteCarloAnalyzer
from src.strategies.stop_loss import StopLossStrategy


def test_run_asset_integration():
    """Integration test: StopLoss strategy on 5 simulations of 10 days."""
    hist_df = _make_hist_df(120)  # 120 bars, enough for warmup pool

    rng = np.random.default_rng(99)
    analyzer = MonteCarloAnalyzer()
    result = analyzer.run_asset(
        ticker="TEST",
        strategy=StopLossStrategy(),
        strategy_name="stop_loss",
        hist_df=hist_df,
        n_simulations=5,
        horizon=10,
        rng=rng,
        seed=99,
    )

    assert isinstance(result, AssetMonteCarloResult)
    assert result.ticker == "TEST"
    assert result.n_simulations == 5
    assert result.horizon == 10
    assert result.seed == 99
    assert 0.0 <= result.prob_loss <= 1.0
    assert result.var_95 <= result.return_median  # VaR is always <= median
    assert result.cvar_95 <= result.var_95        # CVaR <= VaR by definition
```

**Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_montecarlo.py::test_run_asset_integration -v
```

Expected: `ImportError: cannot import name 'MonteCarloAnalyzer'`

**Step 3: Append `MonteCarloAnalyzer` to `src/backtest/montecarlo.py`**

```python
class MonteCarloAnalyzer:
    """Runs a strategy over N bootstrapped price paths and aggregates metrics."""

    def __init__(self):
        self.simulator = MonteCarloSimulator()

    def run_asset(
        self,
        ticker: str,
        strategy: Strategy,
        strategy_name: str,
        hist_df: pd.DataFrame,
        n_simulations: int,
        horizon: int,
        rng: np.random.Generator,
        seed: int,
    ) -> AssetMonteCarloResult:
        import vectorbt as vbt

        warmup_df = hist_df.tail(LOOKBACK).copy()
        paths = self.simulator.generate_paths(hist_df, n_simulations, horizon, rng)

        returns: list[float] = []
        max_dds: list[float] = []
        sharpes: list[float] = []
        win_rates: list[float] = []

        for path in paths:
            path_df = path.to_frame("Close")

            entries = pd.Series(False, index=path.index)
            exits = pd.Series(False, index=path.index)

            for i in range(len(path)):
                current_price = Decimal(str(path.iloc[i]))

                # Build context: warmup tail + synthetic bars up to current
                if i < LOOKBACK:
                    ctx = pd.concat([warmup_df.iloc[-(LOOKBACK - i):], path_df.iloc[:i]])
                else:
                    ctx = path_df.iloc[i - LOOKBACK:i]

                if len(ctx) < 2:
                    continue

                try:
                    signal = strategy.evaluate(ticker, ctx, current_price)
                except Exception as exc:
                    logger.debug("Strategy raised on bar %d for %s: %s", i, ticker, exc)
                    continue

                if signal:
                    if signal.action == "BUY":
                        entries.iloc[i] = True
                    elif signal.action == "SELL":
                        exits.iloc[i] = True

            pf = vbt.Portfolio.from_signals(
                path, entries, exits, init_cash=10_000, freq="1D"
            )
            stats = pf.stats()

            returns.append(float(stats.get("Total Return [%]", 0) or 0))
            max_dds.append(float(stats.get("Max Drawdown [%]", 0) or 0))
            sharpes.append(float(stats.get("Sharpe Ratio", 0) or 0))
            win_rates.append(float(stats.get("Win Rate [%]", 0) or 0))

        arr = np.array(returns)
        var_95 = float(np.percentile(arr, 5))
        tail = arr[arr <= var_95]
        cvar_95 = float(np.mean(tail)) if len(tail) > 0 else var_95

        return AssetMonteCarloResult(
            ticker=ticker,
            n_simulations=n_simulations,
            horizon=horizon,
            strategy_name=strategy_name,
            seed=seed,
            return_median=float(np.percentile(arr, 50)),
            return_mean=float(np.mean(arr)),
            return_p10=float(np.percentile(arr, 10)),
            return_p90=float(np.percentile(arr, 90)),
            return_p05=float(np.percentile(arr, 5)),
            prob_loss=float(np.mean(arr < 0)),
            max_dd_median=float(np.percentile(max_dds, 50)),
            max_dd_p95=float(np.percentile(max_dds, 95)),
            sharpe_median=float(np.percentile(sharpes, 50)),
            win_rate_median=float(np.percentile(win_rates, 50)),
            var_95=var_95,
            cvar_95=cvar_95,
        )
```

**Step 4: Run integration test**

```bash
.venv/bin/pytest tests/test_montecarlo.py::test_run_asset_integration -v
```

Expected: PASS (may take 10–30 seconds — this calls vectorbt 5 times).

**Step 5: Run full test suite to verify nothing broken**

```bash
.venv/bin/pytest tests/ -v --tb=short
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add src/backtest/montecarlo.py tests/test_montecarlo.py
git commit -m "feat: MonteCarloAnalyzer — bar-by-bar signal loop + vectorbt metrics"
```

---

## Task 4: Arg parser + formatter

**Files:**
- Create: `src/bot/handlers/montecarlo.py`
- Modify: `tests/test_montecarlo.py` (append parser + formatter tests)

**Step 1: Write failing tests — append to `tests/test_montecarlo.py`**

```python
from src.bot.handlers.montecarlo import _parse_args, MonteCarloFormatter


def test_parse_args_name_only():
    name, n, h = _parse_args(["Cesta", "Agresiva"])
    assert name == "Cesta Agresiva"
    assert n == 100
    assert h == 90


def test_parse_args_with_n_sims():
    name, n, h = _parse_args(["Cesta", "Agresiva", "200"])
    assert name == "Cesta Agresiva"
    assert n == 200
    assert h == 90


def test_parse_args_with_n_and_horizon():
    name, n, h = _parse_args(["Cesta", "Agresiva", "200", "180"])
    assert name == "Cesta Agresiva"
    assert n == 200
    assert h == 180


def test_parse_args_caps_n_sims_at_500():
    name, n, h = _parse_args(["Cesta", "Agresiva", "9999"])
    assert n == 500


def test_parse_args_caps_horizon_at_365():
    name, n, h = _parse_args(["Cesta", "Agresiva", "100", "9999"])
    assert h == 365


def test_formatter_contains_ticker():
    fmt = MonteCarloFormatter()
    r = _make_result(ticker="AAPL")
    text = fmt.format_asset(r)
    assert "AAPL" in text


def test_formatter_contains_return_median():
    fmt = MonteCarloFormatter()
    r = _make_result(return_median=7.3)
    text = fmt.format_asset(r)
    assert "7.3" in text


def test_formatter_contains_profile():
    fmt = MonteCarloFormatter()
    r = _make_result(prob_loss=0.10, sharpe_median=0.9)
    text = fmt.format_asset(r)
    assert any(kw in text for kw in ["favorable", "moderado", "desfavorable"])
```

**Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_montecarlo.py -v -k "parse_args or formatter"
```

Expected: `ImportError: cannot import name '_parse_args'`

**Step 3: Create `src/bot/handlers/montecarlo.py`**

```python
import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Basket, BasketAsset, Asset
from src.data.yahoo import YahooDataProvider
from src.backtest.montecarlo import MonteCarloAnalyzer, AssetMonteCarloResult, _profile_line
from src.strategies.stop_loss import StopLossStrategy
from src.strategies.ma_crossover import MACrossoverStrategy
from src.strategies.rsi import RSIStrategy
from src.strategies.bollinger import BollingerStrategy
from src.strategies.safe_haven import SafeHavenStrategy

import numpy as np

logger = logging.getLogger(__name__)

STRATEGY_MAP = {
    "stop_loss": StopLossStrategy,
    "ma_crossover": MACrossoverStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerStrategy,
    "safe_haven": SafeHavenStrategy,
}

_sign = lambda v: "+" if v >= 0 else ""


def _parse_args(args: list[str]) -> tuple[str, int, int]:
    """Parse: trailing ints (in order) are N_SIMS then HORIZONTE. Rest is basket name."""
    parts = list(args)
    numerics: list[int] = []

    while parts and parts[-1].isdigit():
        numerics.insert(0, int(parts.pop()))

    n_sims = min(numerics[0], 500) if len(numerics) >= 1 else 100
    horizon = min(numerics[1], 365) if len(numerics) >= 2 else 90
    basket_name = " ".join(parts)
    return basket_name, n_sims, horizon


class MonteCarloFormatter:
    def format_header(
        self,
        basket_name: str,
        strategy: str,
        n_assets: int,
        n_sims: int,
        horizon: int,
        seed: int,
    ) -> str:
        return (
            f"🎲 *Monte Carlo — {basket_name}* "
            f"({n_sims} sims, {horizon} días, seed: {seed})\n"
            f"   Estrategia: `{strategy}` | Activos: {n_assets}\n"
        )

    def format_asset(self, r: AssetMonteCarloResult) -> str:
        s = _sign
        lines = [
            f"*{r.ticker}*",
            f"  Rentabilidad",
            f"    Mediana:          {s(r.return_median)}{r.return_median:.1f}%",
            f"    Rango 80%:        {s(r.return_p10)}{r.return_p10:.1f}% a {s(r.return_p90)}{r.return_p90:.1f}%",
            f"    Peor caso (5%):   {s(r.return_p05)}{r.return_p05:.1f}%  |  Prob. pérdida: {r.prob_loss*100:.0f}%",
            f"  Riesgo",
            f"    VaR 95%: {s(r.var_95)}{r.var_95:.1f}%  |  CVaR 95%: {s(r.cvar_95)}{r.cvar_95:.1f}%",
            f"    Max DD mediano: {r.max_dd_median:.1f}%  |  Max DD peor (5%): {r.max_dd_p95:.1f}%",
            f"  Calidad",
            f"    Sharpe mediano: {r.sharpe_median:.2f}  |  Win rate mediano: {r.win_rate_median:.0f}%",
            f"  {_profile_line(r)}",
            "",
        ]
        return "\n".join(lines)

    def format_footer(self) -> str:
        return (
            "⚠️ _Correlaciones entre activos no modeladas — el riesgo real puede ser mayor._\n"
            "_Pool de retornos: últimos 2 años. Distribución histórica asumida estacionaria._"
        )


async def cmd_montecarlo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /montecarlo CESTA [N_SIMS] [HORIZONTE]"""
    if not context.args:
        await update.message.reply_text(
            "Uso: `/montecarlo Nombre Cesta [simulaciones] [horizonte_días]`\n"
            "Ejemplo: `/montecarlo Cesta Agresiva 100 90`",
            parse_mode="Markdown",
        )
        return

    basket_name, n_sims, horizon = _parse_args(list(context.args))
    if not basket_name:
        await update.message.reply_text("Indica el nombre de la cesta.")
        return

    seed = int(np.random.default_rng().integers(0, 99_999))
    rng = np.random.default_rng(seed)

    msg = await update.message.reply_text(
        f"⏳ Monte Carlo en curso ({n_sims} simulaciones, {horizon} días)..."
        f"\nEsto puede tardar un momento."
    )

    data_provider = YahooDataProvider()
    analyzer = MonteCarloAnalyzer()
    fmt = MonteCarloFormatter()

    async with async_session_factory() as session:
        result = await session.execute(
            select(Basket).where(Basket.name == basket_name, Basket.active == True)
        )
        basket = result.scalar_one_or_none()
        if not basket:
            await msg.delete()
            await update.message.reply_text(f"Cesta '{basket_name}' no encontrada.")
            return

        strategy_cls = STRATEGY_MAP.get(basket.strategy)
        if not strategy_cls:
            await msg.delete()
            await update.message.reply_text(
                f"Estrategia `{basket.strategy}` no soportada en Monte Carlo.",
                parse_mode="Markdown",
            )
            return

        strategy = strategy_cls()

        assets_result = await session.execute(
            select(Asset)
            .join(BasketAsset, BasketAsset.asset_id == Asset.id)
            .where(BasketAsset.basket_id == basket.id, BasketAsset.active == True)
        )
        assets = assets_result.scalars().all()

        if not assets:
            await msg.delete()
            await update.message.reply_text(f"Cesta '{basket_name}' sin activos activos.")
            return

        header = fmt.format_header(
            basket_name=basket.name,
            strategy=basket.strategy,
            n_assets=len(assets),
            n_sims=n_sims,
            horizon=horizon,
            seed=seed,
        )
        await update.message.reply_text(header, parse_mode="Markdown")

        loop = asyncio.get_event_loop()
        for asset in assets:
            try:
                ohlcv = await loop.run_in_executor(
                    None,
                    lambda t=asset.ticker: data_provider.get_historical(t, period="2y", interval="1d"),
                )
                mc_result = await loop.run_in_executor(
                    None,
                    analyzer.run_asset,
                    asset.ticker, strategy, basket.strategy,
                    ohlcv.data, n_sims, horizon, rng, seed,
                )
                await update.message.reply_text(
                    fmt.format_asset(mc_result), parse_mode="Markdown"
                )
            except Exception as e:
                logger.error("Monte Carlo error %s: %s", asset.ticker, e)
                await update.message.reply_text(f"❌ {asset.ticker}: {e}")

        await update.message.reply_text(fmt.format_footer(), parse_mode="Markdown")

    await msg.delete()


def get_handlers():
    return [CommandHandler("montecarlo", cmd_montecarlo)]
```

**Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_montecarlo.py -v -k "parse_args or formatter"
```

Expected: all 8 tests PASS.

**Step 5: Run full test suite**

```bash
.venv/bin/pytest tests/ -v --tb=short
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add src/bot/handlers/montecarlo.py tests/test_montecarlo.py
git commit -m "feat: /montecarlo handler — arg parser, formatter, async command"
```

---

## Task 5: Register handler in bot.py

**Files:**
- Modify: `src/bot/bot.py`

**Step 1: Read `src/bot/bot.py` to find the handler registration pattern**

Look for lines like:
```python
from src.bot.handlers.backtest import get_handlers as backtest_handlers
# ...
for handler in backtest_handlers():
    app.add_handler(handler)
```

**Step 2: Add montecarlo import alongside the existing backtest import**

```python
from src.bot.handlers.montecarlo import get_handlers as montecarlo_handlers
```

**Step 3: Register handlers — same pattern as backtest, after backtest registration**

```python
for handler in montecarlo_handlers():
    app.add_handler(handler)
```

**Step 4: Verify bot starts without errors**

```bash
.venv/bin/python -c "from src.bot.bot import run; print('import OK')"
```

Expected: `import OK`

**Step 5: Commit**

```bash
git add src/bot/bot.py
git commit -m "feat: register /montecarlo command in bot"
```

---

## Task 6: Manual smoke test

**Step 1: Start the bot**

```bash
.venv/bin/python scroogebot.py
```

**Step 2: In Telegram, test the following**

| Input | Expected |
|---|---|
| `/montecarlo` | Usage message with example |
| `/montecarlo Cesta Inexistente` | "Cesta 'Cesta Inexistente' no encontrada." |
| `/montecarlo Cesta Agresiva` | Header + 3 asset blocks + footer (may take 1–3 min) |
| `/montecarlo Cesta Agresiva 50` | Same but 50 sims (faster) |
| `/montecarlo Cesta Agresiva 50 30` | 50 sims, 30-day horizon |

Verify for each asset block:
- Return median shown with sign
- 80% range makes sense (p10 < median < p90)
- Prob. pérdida between 0% and 100%
- Profile line present (✅ / ⚠️ / 🔴)
- Footer disclaimer at end
- Seed shown in header (reproducible)

**Step 3: Run final test suite**

```bash
.venv/bin/pytest tests/ -v --tb=short
```

Expected: all tests PASS.

**Step 4: Final commit if anything was fixed**

```bash
git add -A
git commit -m "chore: /montecarlo smoke test complete"
```

---

## Done ✅

| Task | Component |
|---|---|
| 1 | MonteCarloSimulator (path generation) |
| 2 | AssetMonteCarloResult + profile classifier |
| 3 | MonteCarloAnalyzer (signal loop + vectorbt + percentiles) |
| 4 | _parse_args + MonteCarloFormatter + cmd_montecarlo |
| 5 | Handler registered in bot.py |
| 6 | Smoke test |

**New files:** `src/backtest/montecarlo.py`, `src/bot/handlers/montecarlo.py`, `tests/test_montecarlo.py`
**Modified files:** `src/bot/bot.py` (+2 lines)
