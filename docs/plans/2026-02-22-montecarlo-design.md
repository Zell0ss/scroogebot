# ScroogeBot — /montecarlo Command Design

**Date:** 2026-02-22
**Status:** Approved

---

## Goal

Add `/montecarlo CESTA [N_SIMS] [HORIZONTE]` command that generates N bootstrapped
future price paths per asset and runs the basket's strategy over each, returning
a distribution of outcomes instead of a single historical number.

Complements the existing `/backtest` (historical, deterministic) with a
forward-looking probabilistic view.

---

## Command Syntax

```
/montecarlo Cesta Agresiva
/montecarlo Cesta Agresiva 200
/montecarlo Cesta Agresiva 200 180
```

- **CESTA** — basket name (may contain spaces); matched by exact name in DB
- **N_SIMS** — number of simulations (default: 100, max: 500)
- **HORIZONTE** — days to simulate forward (default: 90)

**Arg parsing:** scan args right-to-left; trailing integers are HORIZONTE then
N_SIMS; everything before is the basket name.

---

## Simulation Method: Bootstrapped Returns

For each asset in the basket:

1. Fetch 2 years of daily historical data via `YahooDataProvider.get_historical()`
2. Compute log returns: `log(close_t / close_{t-1})`
3. For each simulation k of N:
   - Sample `horizon` log returns randomly with replacement from the historical pool
   - Reconstruct price series: `price_t = last_real_price * exp(cumsum(sampled_returns))`
4. Result: N synthetic `pd.Series` of Close prices per asset

**Assumptions stated to user in output:**
- Returns distribution assumed stationary (future resembles past)
- Correlations between assets NOT modeled — diversification benefit overstated

---

## Warmup for Indicator-Based Strategies

Strategies need prior data to compute indicators (MA, RSI, Bollinger).
Use the last 60 real bars as warmup context (matches BacktestEngine's `window=60`).

For each bar `i` of the synthetic horizon, build context window:
```python
if i < lookback:                                      # early bars of path
    ctx = pd.concat([warmup_df.iloc[-(lookback-i):], path.iloc[:i]])
else:                                                 # fully synthetic context
    ctx = path.iloc[i - lookback:i]
signal = strategy.evaluate(ticker, ctx, current_price)
```

The vectorbt portfolio is simulated only on the `horizon` synthetic bars
(not on warmup), so warmup days do not contaminate return metrics.

---

## No Over-Engineering Decision

**Strategy ABC is NOT modified.** No `vectorize()` method added.
Signal generation uses the existing bar-by-bar `evaluate()` loop (same as
BacktestEngine). This means:

- 100 sims × 90 bars = 9,000 `strategy.evaluate()` calls per asset
- Execution time: ~30–60s for a basket with 3 assets, 100 sims
- Acceptable: Monte Carlo is not a real-time command

`BacktestEngine` is also NOT modified — MonteCarloAnalyzer owns its own
signal loop (~20 lines, near-identical to BacktestEngine's inner loop).

---

## Metrics

Computed from the distribution of N simulation results:

```python
# Returns
return_median  = np.percentile(returns, 50)
return_mean    = np.mean(returns)
return_p10     = np.percentile(returns, 10)
return_p90     = np.percentile(returns, 90)
return_p05     = np.percentile(returns, 5)
prob_loss      = np.mean(np.array(returns) < 0)

# Risk
max_dd_median  = np.percentile(max_dds, 50)
max_dd_p95     = np.percentile(max_dds, 95)

# Quality
sharpe_median  = np.percentile(sharpes, 50)
win_rate_median = np.percentile(win_rates, 50)

# VaR / CVaR
var_95         = np.percentile(returns, 5)
cvar_95        = np.mean([r for r in returns if r <= var_95])
```

---

## Profile Classification

Thresholds implemented as constants (configurable):

| Condition | Profile |
|---|---|
| prob_loss < 0.20 AND sharpe_median > 0.8 | ✅ Perfil favorable |
| prob_loss 0.20–0.40 OR sharpe_median 0.4–0.8 | ⚠️ Perfil moderado |
| prob_loss > 0.40 OR sharpe_median < 0.4 | 🔴 Perfil desfavorable |

---

## Output Format (per asset within basket)

```
🎲 Monte Carlo — Cesta Agresiva (100 sims, 90 días, seed: 42731)
   Estrategia: ma_crossover | Activos: 3

*AAPL*
  Rentabilidad
    Mediana:             +4.2%
    Rango 80%:           -3.1% a +12.8%
    Peor caso (5%):      -8.4%  |  Prob. pérdida: 24%
  Riesgo
    VaR 95%: -8.4%  |  CVaR 95%: -11.2%
    Max DD mediano: 6.3%  |  Max DD peor (5%): 14.1%
  Calidad
    Sharpe mediano: 0.58  |  Win rate mediano: 48%
  ⚠️ Perfil moderado, revisar riesgo

*MSFT*
  ...

⚠️ Correlaciones entre activos no modeladas — el riesgo real puede ser mayor.
   Pool de retornos: últimos 2 años. Asume distribución histórica estacionaria.
```

Seed is shown so the user can reproduce exact results if desired.

---

## Architecture

### Files to create

**`src/backtest/montecarlo.py`**
```
MonteCarloSimulator
  .generate_paths(hist_df, last_price, n_sims, horizon, rng) → list[pd.Series]

AssetMonteCarloResult (dataclass)
  ticker, n_sims, horizon, strategy_name, seed
  return_median, return_mean, return_p10, return_p90, return_p05
  prob_loss, max_dd_median, max_dd_p95
  sharpe_median, win_rate_median
  var_95, cvar_95

MonteCarloAnalyzer
  .run_asset(ticker, strategy, strategy_name, hist_df, n_sims, horizon, rng)
    → AssetMonteCarloResult
  (owns: path generation, warmup context, signal loop, vbt calls, percentiles)
```

**`src/bot/handlers/montecarlo.py`**
```
_parse_args(args) → (basket_name, n_sims, horizon)
MonteCarloFormatter.format_asset(result) → str
cmd_montecarlo(update, context) → None
  - parse args
  - DB: basket + assets + strategy
  - send "⏳ procesando..." message
  - run_in_executor: MonteCarloAnalyzer.run_asset() per asset
  - reply per asset, delete processing message
get_handlers() → [CommandHandler]
```

### Files to modify

**`src/bot/bot.py`** — add import + register handler (same pattern as backtest)

### No other files modified

---

## Key Implementation Details

### Reproducible seed
```python
import numpy as np
seed = rng.integers(0, 99999) if no seed provided
rng = np.random.default_rng(seed)
```
Show seed in output for reproducibility.

### Synthetic DataFrame for strategy context
Strategies only use `data["Close"]`. Synthetic paths are `pd.Series` with
`DatetimeIndex` starting the business day after the last real date.
Warmup context from real OHLCV provides all columns; synthetic context
provides only Close (sufficient for all current strategies).

### vectorbt call per simulation
```python
import vectorbt as vbt
pf = vbt.Portfolio.from_signals(
    close_synthetic,   # pd.Series, horizon bars
    entries,           # pd.Series[bool]
    exits,             # pd.Series[bool]
    init_cash=10_000,
    freq="1D",
)
stats = pf.stats()
```
N separate vbt calls per asset (one per simulation). Simple, correct, slow — acceptable.

### Async execution
```python
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(None, analyzer.run_asset, ...)
```
Same pattern as `/backtest` handler.

---

## What is NOT in scope

- Correlations between assets — v2
- GBM or block-bootstrap — v2
- Persistent results / caching — v2
- LLM interpretation — never
- Vectorized Strategy interface — only if perf becomes a problem

---

## Strategy Warmup Reference

| Strategy | Min bars needed | Notes |
|---|---|---|
| StopLossStrategy | 2 | trivial |
| MACrossoverStrategy | 51 | slow_period=50 from config |
| RSIStrategy | 16 | period=14 from config |
| BollingerStrategy | 20 | period=20 from config |
| SafeHavenStrategy | 2 | trivial |

Lookback = 60 (BacktestEngine constant) covers all strategies comfortably.
