# Design: /sizing command — Position Sizing with Risk Management

**Date:** 2026-02-21
**Status:** Approved

---

## Problem

Users need to know how many shares to buy before executing an order. The answer
depends on: current price, stop-loss distance, portfolio risk parameters, and
broker commissions. Today this is done manually outside the bot.

---

## Goals

- `/sizing TICKER [STOP_LOSS]` → instant position sizing in Telegram
- Commission-aware: real brokerage fees reduce the risk budget before sizing
- Each basket has an associated broker (DEGIRO, MyInvestor, paper)
- Stateless: no DB writes, pure calculator
- Reusable: sizing engine has no Telegram dependency

## Non-goals (deferred to FUTURE.md)

- Commission-aware backtest (needs `CommissionStructure` from this design)
- Real broker API execution (buy/sell stubs prepared but not implemented)
- Per-user configurable capital/risk parameters

---

## Architecture: Approach C — Composition over inheritance

`Broker` wraps a `DataProvider` + `CommissionStructure`. It is a concrete class,
not an ABC. The existing `DataProvider` hierarchy is untouched except for adding
`get_atr()` to `YahooDataProvider`.

```
DataProvider (ABC) — unchanged
    └── YahooDataProvider  ← +get_atr(ticker, period=14) → Decimal

Broker (concrete class)
    ├── name: str
    ├── _provider: YahooDataProvider
    └── commissions: CommissionStructure

BROKER_REGISTRY: dict[str, Broker]
    ├── "degiro"      → fixed €2/op
    ├── "myinvestor"  → 0.12%, min €3, max €25
    └── "paper"       → DEGIRO fees + PaperTradingExecutor buy/sell
```

`PaperBroker` (broker name `"paper"`) uses real commission rates (configurable,
defaults to DEGIRO) so sizing calculations remain realistic, while buy/sell
delegate to the existing `PaperTradingExecutor`. Baskets start with
`broker = "paper"`. Switching to a real broker in future means changing one
field in the DB — no code changes to sizing or backtest.

---

## File structure

```
src/
├── data/
│   └── yahoo.py          # + get_atr(ticker, period=14) → Decimal
│
├── sizing/
│   ├── __init__.py
│   ├── models.py         # CommissionStructure, SizingResult dataclasses
│   ├── broker.py         # Broker class, BROKER_REGISTRY
│   └── engine.py         # calculate_sizing() pure function + portfolio constants
│
└── bot/handlers/
    └── sizing.py         # cmd_sizing handler + get_handlers()

src/db/
└── migrations/versions/
    └── XXXX_add_broker_to_basket.py   # broker VARCHAR(50) NOT NULL DEFAULT 'paper'

config/config.yaml        # broker: paper added to each basket entry
```

---

## Data models

```python
# src/sizing/models.py

@dataclass
class CommissionStructure:
    comision_fija:   float = 0.0   # € fixed per operation
    comision_pct:    float = 0.0   # % of nominal
    comision_minima: float = 0.0   # floor
    comision_maxima: float | None = None  # ceiling (None = unlimited)

    def calcular(self, nominal: float) -> float:
        c = self.comision_fija + (nominal * self.comision_pct / 100)
        c = max(c, self.comision_minima)
        if self.comision_maxima is not None:
            c = min(c, self.comision_maxima)
        return c


@dataclass
class SizingResult:
    ticker:         str
    company_name:   str
    precio:         float
    currency:       str
    stop_loss:      float
    stop_tipo:      str         # "manual" | "ATR×2"
    atr:            float | None
    distancia:      float       # precio - stop_loss
    distancia_pct:  float       # distancia / precio * 100
    acciones:       int
    factor_limite:  str         # "riesgo" | "nominal"
    nominal:        float       # acciones × precio
    pct_cartera:    float       # nominal / CAPITAL_TOTAL * 100
    riesgo_maximo:  float       # CAPITAL_TOTAL × RIESGO_MAX_PCT
    riesgo_real:    float       # (acciones × distancia) + com_compra + com_venta
    com_compra:     float
    com_venta:      float
    broker_nombre:  str
    aviso:          str | None  # warning text, never blocks
```

---

## Broker registry

```python
# src/sizing/broker.py

# Known commission structures
DEGIRO_FEES = CommissionStructure(comision_fija=2.0)
MYINVESTOR_FEES = CommissionStructure(
    comision_pct=0.12, comision_minima=3.0, comision_maxima=25.0
)

BROKER_REGISTRY: dict[str, Broker] = {
    "degiro":     Broker("degiro",     YahooDataProvider(), DEGIRO_FEES),
    "myinvestor": Broker("myinvestor", YahooDataProvider(), MYINVESTOR_FEES),
    "paper":      Broker("paper",      YahooDataProvider(), DEGIRO_FEES),
    # paper uses DEGIRO fees so sizing is realistic; buy/sell → PaperTradingExecutor
}
```

---

## Portfolio constants

```python
# src/sizing/engine.py

CAPITAL_TOTAL       = 20_000.0   # € — move to config/DB in future
RIESGO_MAX_PCT      = 0.0075     # 0.75% → €150
POSICION_MAX_PCT    = 0.20       # 20%   → €4,000
STOP_ALEJADO_UMBRAL = 0.15       # warn if stop > 15% from price
```

---

## Sizing algorithm

### Fixed commissions (DEGIRO, paper)
No circular dependency — commissions don't depend on nominal:
```
riesgo_max       = CAPITAL_TOTAL × RIESGO_MAX_PCT
riesgo_disp      = riesgo_max - com_compra - com_venta
acciones_riesgo  = floor(riesgo_disp / distancia)
acciones_nominal = floor(posicion_max / precio)
acciones         = min(acciones_riesgo, acciones_nominal)
```

### Percentage commissions (MyInvestor)
Circular dependency (commission depends on nominal, nominal depends on shares,
shares depend on risk budget which depends on commission). Resolve iteratively:
```
acciones = floor(riesgo_max / distancia)   # seed estimate, no commissions
for _ in range(5):
    nominal    = acciones × precio
    com_compra = commissions.calcular(nominal)
    com_venta  = commissions.calcular(nominal)
    riesgo_disp = riesgo_max - com_compra - com_venta
    nuevas     = floor(riesgo_disp / distancia)
    if nuevas == acciones: break
    acciones   = nuevas
acciones_nominal = floor(posicion_max / precio)
acciones         = min(acciones, acciones_nominal)
```
Always floor (never ceil) to guarantee risk budget is never exceeded.

### ATR calculation (auto stop-loss)
Uses `ta.volatility.AverageTrueRange` on 3-month daily OHLCV from `YahooDataProvider`:
```python
stop_loss = precio - (2 × ATR14)
```

### FX conversion
If ticker currency ≠ EUR, convert via `broker.get_fx_rate(currency, "EUR")`,
which reuses the existing `DataProvider.get_fx_rate()` implementation.

---

## Command behaviour

```
/sizing TICKER [STOP_LOSS]

/sizing SAN.MC             → auto stop via ATR×2
/sizing SAN.MC 3.85        → manual stop
/sizing AAPL               → USD ticker, auto-converts to EUR
/sizing AAPL 180           → manual stop in USD
```

**Lookup:** query DB for active baskets containing the ticker via `BasketAsset`.
- Found in one basket → use that basket's broker
- Found in multiple baskets → show one block per basket (different brokers)
- Not found in any basket → use `"paper"` as fallback (it's a calculator, not an order)

**Warnings** (never block):
- `stop > precio × 1.15` → "⚠️ Stop muy alejado, considera ATR automático"
- currency ≠ EUR → "ℹ️ Precio convertido desde {currency}"
- `acciones == 0` → "❌ Riesgo insuficiente para esta distancia de stop"

---

## Response format

```
📊 Position Sizing — Banco Santander (SAN.MC)

Precio actual:      €3.98
Stop loss:          €3.65  (ATR×2)
  └─ ATR(14):       €0.17  |  Volatilidad media
Distancia al stop:  €0.33  (-8.3%)

Acciones:           136  (limitado por riesgo)
Posición nominal:   €541.28  (2.7% de cartera)
Riesgo máximo:      €150.00  (0.75%)

Comisiones (DEGIRO): €2.00 compra + €2.00 venta
Riesgo real:         €146.88

✅ Stop dentro del rango recomendado
```

---

## DB migration

New column on `baskets` table:
```sql
ALTER TABLE baskets
  ADD COLUMN broker VARCHAR(50) NOT NULL DEFAULT 'paper';
```

Alembic migration file: `src/db/migrations/versions/XXXX_add_broker_to_basket.py`

`config.yaml` updated: add `broker: paper` to each basket entry.
`src/db/models.py` updated: add `broker: str` field to `Basket` ORM model.
`src/db/seed.py` updated: read `broker` from config and set on basket.

---

## Testing

- `test_commission_structure.py` — `calcular()` for fixed, pct, min, max cases
- `test_sizing_engine.py` — pure function tests with mock broker (no network):
  - fixed commissions: verify floor, riesgo vs nominal limit, factor_limite label
  - pct commissions: verify iterative convergence
  - stop > 15% threshold triggers aviso
  - acciones == 0 edge case
- No Telegram integration tests needed (handler is thin wrapper)

---

## Integration checklist

1. `YahooDataProvider.get_atr()` added
2. `src/sizing/` module created (models, broker, engine)
3. Alembic migration + model + seed updated
4. `config.yaml` baskets get `broker: paper`
5. `src/bot/handlers/sizing.py` created + registered in `bot.py`
6. Tests written and passing
7. `USER_MANUAL.md` updated with `/sizing` command docs
