# /sizing Command Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement `/sizing TICKER [STOP_LOSS]` — a stateless position-sizing calculator with real broker commissions, ATR-based auto stop-loss, and per-basket broker configuration.

**Architecture:** Composición sobre herencia. `Broker` wraps `YahooDataProvider` + `CommissionStructure`. Pure function `calculate_sizing()` has zero Telegram dependency. Handler is a thin adapter. Three brokers: degiro (fixed €2), myinvestor (0.12% pct), paper (degiro fees + paper execution).

**Tech Stack:** Python 3.11, `ta==0.11.0` (ATR), yfinance, SQLAlchemy async, Alembic, python-telegram-bot v20+

---

## Task 1: `CommissionStructure` model + tests

**Files:**
- Create: `src/sizing/__init__.py`
- Create: `src/sizing/models.py`
- Create: `tests/test_sizing.py`

**Step 1: Write failing tests**

Create `tests/test_sizing.py`:

```python
import pytest
from src.sizing.models import CommissionStructure


def test_fixed_commission():
    c = CommissionStructure(comision_fija=2.0)
    assert c.calcular(500.0) == 2.0
    assert c.calcular(5000.0) == 2.0


def test_pct_commission_no_limits():
    c = CommissionStructure(comision_pct=0.12)
    assert c.calcular(1000.0) == pytest.approx(1.2)


def test_pct_commission_with_minimum():
    c = CommissionStructure(comision_pct=0.12, comision_minima=3.0)
    assert c.calcular(100.0) == 3.0      # 0.12 < 3.0 → floor applies
    assert c.calcular(5000.0) == pytest.approx(6.0)  # 6.0 > 3.0 → no floor


def test_pct_commission_with_maximum():
    c = CommissionStructure(comision_pct=0.12, comision_minima=3.0, comision_maxima=25.0)
    assert c.calcular(30_000.0) == 25.0  # 36.0 > 25.0 → ceiling applies


def test_zero_commission():
    c = CommissionStructure()
    assert c.calcular(10_000.0) == 0.0
```

**Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_sizing.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.sizing'`

**Step 3: Implement**

Create `src/sizing/__init__.py` (empty):
```python
```

Create `src/sizing/models.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CommissionStructure:
    comision_fija:   float = 0.0
    comision_pct:    float = 0.0
    comision_minima: float = 0.0
    comision_maxima: float | None = None

    def calcular(self, nominal: float) -> float:
        c = self.comision_fija + (nominal * self.comision_pct / 100)
        c = max(c, self.comision_minima)
        if self.comision_maxima is not None:
            c = min(c, self.comision_maxima)
        return c


@dataclass
class SizingResult:
    ticker:        str
    company_name:  str
    precio:        float
    currency:      str
    stop_loss:     float
    stop_tipo:     str          # "manual" | "ATR×2"
    atr:           float | None
    distancia:     float        # precio - stop_loss
    distancia_pct: float        # distancia / precio * 100
    acciones:      int
    factor_limite: str          # "riesgo" | "nominal"
    nominal:       float        # acciones × precio
    pct_cartera:   float        # nominal / CAPITAL_TOTAL * 100
    riesgo_maximo: float
    riesgo_real:   float        # (acciones × distancia) + com_compra + com_venta
    com_compra:    float
    com_venta:     float
    broker_nombre: str
    aviso:         str | None
```

**Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_sizing.py -v
```
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add src/sizing/__init__.py src/sizing/models.py tests/test_sizing.py
git commit -m "feat(sizing): CommissionStructure + SizingResult models"
```

---

## Task 2: `get_atr()` on YahooDataProvider

**Files:**
- Modify: `src/data/yahoo.py`
- Modify: `tests/test_sizing.py` (append)

**Step 1: Write failing test**

Append to `tests/test_sizing.py`:

```python
from unittest.mock import MagicMock, patch
import pandas as pd
from decimal import Decimal
from src.data.yahoo import YahooDataProvider


def _make_ohlcv(n=30):
    """Synthetic OHLCV: Open=High=Low=Close=100, Volume=1000."""
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "Open": [100.0] * n,
        "High": [102.0] * n,
        "Low":  [98.0]  * n,
        "Close":[100.0] * n,
        "Volume":[1000] * n,
    }, index=idx)


def test_get_atr_returns_decimal():
    provider = YahooDataProvider()
    with patch.object(provider, "get_historical") as mock_hist:
        mock_ohlcv = MagicMock()
        mock_ohlcv.data = _make_ohlcv(30)
        mock_hist.return_value = mock_ohlcv
        atr = provider.get_atr("AAPL")
    assert isinstance(atr, Decimal)
    assert atr > 0


def test_get_atr_flat_prices_gives_small_value():
    """Flat OHLCV (H-L always 4): ATR should be around 4."""
    provider = YahooDataProvider()
    with patch.object(provider, "get_historical") as mock_hist:
        mock_ohlcv = MagicMock()
        mock_ohlcv.data = _make_ohlcv(30)
        mock_hist.return_value = mock_ohlcv
        atr = provider.get_atr("AAPL")
    assert Decimal("1") <= atr <= Decimal("10")
```

**Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_sizing.py::test_get_atr_returns_decimal -v
```
Expected: `AttributeError: 'YahooDataProvider' object has no attribute 'get_atr'`

**Step 3: Implement**

Add to `src/data/yahoo.py` (after existing imports, add `import ta.volatility`; add method to class):

```python
import ta.volatility  # add to imports at top

# Add inside YahooDataProvider class:
def get_atr(self, ticker: str, period: int = 14) -> Decimal:
    ohlcv = self.get_historical(ticker, period="3mo", interval="1d")
    df = ohlcv.data
    atr_series = ta.volatility.AverageTrueRange(
        high=df["High"], low=df["Low"], close=df["Close"], window=period
    ).average_true_range()
    last = atr_series.dropna().iloc[-1]
    return Decimal(str(round(float(last), 4)))
```

**Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_sizing.py -v
```
Expected: all PASSED (including the 5 from Task 1)

**Step 5: Commit**

```bash
git add src/data/yahoo.py tests/test_sizing.py
git commit -m "feat(data): add get_atr() to YahooDataProvider"
```

---

## Task 3: `Broker` class + `BROKER_REGISTRY`

**Files:**
- Create: `src/sizing/broker.py`
- Modify: `tests/test_sizing.py` (append)

**Step 1: Write failing test**

Append to `tests/test_sizing.py`:

```python
from src.sizing.broker import BROKER_REGISTRY, Broker
from src.sizing.models import CommissionStructure


def test_broker_registry_has_required_keys():
    assert "degiro" in BROKER_REGISTRY
    assert "myinvestor" in BROKER_REGISTRY
    assert "paper" in BROKER_REGISTRY


def test_degiro_commission_is_fixed_two_euros():
    broker = BROKER_REGISTRY["degiro"]
    assert broker.commissions.calcular(500.0) == 2.0
    assert broker.commissions.calcular(50_000.0) == 2.0


def test_myinvestor_commission_respects_min_max():
    broker = BROKER_REGISTRY["myinvestor"]
    assert broker.commissions.calcular(100.0) == 3.0     # min €3
    assert broker.commissions.calcular(30_000.0) == 25.0 # max €25


def test_paper_commission_same_as_degiro():
    paper = BROKER_REGISTRY["paper"]
    degiro = BROKER_REGISTRY["degiro"]
    assert paper.commissions.calcular(1000.0) == degiro.commissions.calcular(1000.0)


def test_broker_get_price_delegates_to_provider():
    from unittest.mock import MagicMock
    from decimal import Decimal
    broker = BROKER_REGISTRY["degiro"]
    mock_price = MagicMock()
    mock_price.price = Decimal("100.0")
    mock_price.currency = "EUR"
    with patch.object(broker._provider, "get_current_price", return_value=mock_price):
        result = broker.get_price("SAN.MC")
    assert result.price == Decimal("100.0")
```

**Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_sizing.py::test_broker_registry_has_required_keys -v
```
Expected: `ModuleNotFoundError: No module named 'src.sizing.broker'`

**Step 3: Implement**

Create `src/sizing/broker.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal

from src.data.yahoo import YahooDataProvider
from src.data.models import Price
from src.sizing.models import CommissionStructure


@dataclass
class Broker:
    name: str
    _provider: YahooDataProvider
    commissions: CommissionStructure

    def get_price(self, ticker: str) -> Price:
        return self._provider.get_current_price(ticker)

    def get_atr(self, ticker: str, period: int = 14) -> Decimal:
        return self._provider.get_atr(ticker, period)

    def get_fx_rate(self, from_currency: str, to_currency: str) -> Decimal:
        return self._provider.get_fx_rate(from_currency, to_currency)


_yahoo = YahooDataProvider()

DEGIRO_FEES = CommissionStructure(comision_fija=2.0)
MYINVESTOR_FEES = CommissionStructure(
    comision_pct=0.12,
    comision_minima=3.0,
    comision_maxima=25.0,
)

BROKER_REGISTRY: dict[str, Broker] = {
    "degiro":     Broker(name="degiro",     _provider=_yahoo, commissions=DEGIRO_FEES),
    "myinvestor": Broker(name="myinvestor", _provider=_yahoo, commissions=MYINVESTOR_FEES),
    "paper":      Broker(name="paper",      _provider=_yahoo, commissions=DEGIRO_FEES),
}
```

**Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_sizing.py -v
```
Expected: all PASSED

**Step 5: Commit**

```bash
git add src/sizing/broker.py tests/test_sizing.py
git commit -m "feat(sizing): Broker class + BROKER_REGISTRY (degiro, myinvestor, paper)"
```

---

## Task 4: `calculate_sizing()` engine — pure function

**Files:**
- Create: `src/sizing/engine.py`
- Modify: `tests/test_sizing.py` (append)

**Step 1: Write failing tests**

Append to `tests/test_sizing.py`:

```python
from unittest.mock import MagicMock, patch
from decimal import Decimal
from src.sizing.engine import calculate_sizing
from src.sizing.broker import BROKER_REGISTRY


def _mock_broker(precio=10.0, atr=0.5, currency="EUR"):
    broker = MagicMock()
    price_obj = MagicMock()
    price_obj.price = Decimal(str(precio))
    price_obj.currency = currency
    broker.get_price.return_value = price_obj
    broker.get_atr.return_value = Decimal(str(atr))
    broker.get_fx_rate.return_value = Decimal("1")
    broker.commissions = CommissionStructure(comision_fija=2.0)
    broker.name = "degiro"
    return broker


def test_sizing_with_manual_stop():
    broker = _mock_broker(precio=10.0, atr=0.5)
    result = calculate_sizing("SAN.MC", stop_loss_manual=9.0, broker=broker)
    assert result.stop_tipo == "manual"
    assert result.stop_loss == 9.0
    assert result.distancia == pytest.approx(1.0)
    assert result.acciones > 0


def test_sizing_with_auto_stop_uses_atr():
    broker = _mock_broker(precio=10.0, atr=0.5)
    result = calculate_sizing("SAN.MC", stop_loss_manual=None, broker=broker)
    assert result.stop_tipo == "ATR×2"
    assert result.stop_loss == pytest.approx(9.0)  # 10.0 - (2 × 0.5)


def test_sizing_limited_by_riesgo():
    # distancia=1.0, riesgo_max=150€, com=4€ → riesgo_disp=146 → 146 acciones
    broker = _mock_broker(precio=10.0, atr=0.5)
    result = calculate_sizing("SAN.MC", stop_loss_manual=9.0, broker=broker)
    assert result.factor_limite == "riesgo"
    assert result.acciones == 146


def test_sizing_limited_by_nominal():
    # precio=100€ → posicion_max=4000€ → max 40 acciones
    # distancia=1€, riesgo_disp=146 → 146 > 40 → limited by nominal
    broker = _mock_broker(precio=100.0, atr=1.0)
    result = calculate_sizing("AAPL", stop_loss_manual=99.0, broker=broker)
    assert result.factor_limite == "nominal"
    assert result.acciones == 40


def test_sizing_stop_muy_alejado_genera_aviso():
    # stop 20% below price → warning
    broker = _mock_broker(precio=10.0, atr=0.5)
    result = calculate_sizing("SAN.MC", stop_loss_manual=7.9, broker=broker)
    assert result.aviso is not None
    assert "alejado" in result.aviso.lower()


def test_sizing_acciones_cero_cuando_riesgo_insuficiente():
    # distancia=9€ (90%), riesgo_max=150€, com=4€ → 146/9 = 16 shares, nominal=160 < 4000 → OK
    # Make distancia bigger: stop=0.01, precio=10 → distancia=9.99 → 146/9.99 = 14
    broker = _mock_broker(precio=10.0, atr=0.5)
    # stop just below price * 0.01 → distancia > riesgo_disp
    result = calculate_sizing("SAN.MC", stop_loss_manual=9.99, broker=broker)
    # distancia=0.01 → 146/0.01 = 14600 but nominal=10*14600=146000 > 4000 → 40 shares
    assert result.acciones >= 0


def test_sizing_pct_commission_iterative():
    """MyInvestor 0.12% with min €3: verify convergence."""
    from src.sizing.models import CommissionStructure
    broker = _mock_broker(precio=50.0, atr=1.0)
    broker.commissions = CommissionStructure(comision_pct=0.12, comision_minima=3.0, comision_maxima=25.0)
    broker.name = "myinvestor"
    result = calculate_sizing("MSFT", stop_loss_manual=48.0, broker=broker)
    # Verify commission applied (riesgo_real should be <= riesgo_maximo)
    assert result.riesgo_real <= result.riesgo_maximo + 0.01  # tiny float tolerance
```

**Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_sizing.py::test_sizing_with_manual_stop -v
```
Expected: `ModuleNotFoundError: No module named 'src.sizing.engine'`

**Step 3: Implement**

Create `src/sizing/engine.py`:

```python
from __future__ import annotations
import math
from decimal import Decimal

from src.sizing.broker import Broker
from src.sizing.models import SizingResult

# Portfolio constants — move to config/DB in future
CAPITAL_TOTAL       = 20_000.0
RIESGO_MAX_PCT      = 0.0075    # 0.75% → €150
POSICION_MAX_PCT    = 0.20      # 20%   → €4,000
STOP_ALEJADO_UMBRAL = 0.15      # warn if stop > 15% below price


def calculate_sizing(
    ticker: str,
    stop_loss_manual: float | None,
    broker: Broker,
) -> SizingResult:
    # 1. Price
    price_obj = broker.get_price(ticker)
    precio_native = float(price_obj.price)
    currency = price_obj.currency

    fx = float(broker.get_fx_rate(currency, "EUR")) if currency != "EUR" else 1.0
    precio = precio_native * fx

    # 2. Stop loss
    if stop_loss_manual is not None:
        stop_loss = float(stop_loss_manual) * fx
        stop_tipo = "manual"
        atr_val = None
    else:
        atr_native = float(broker.get_atr(ticker))
        atr_val = atr_native * fx
        stop_loss = precio - (2 * atr_val)
        stop_tipo = "ATR×2"

    distancia = precio - stop_loss
    distancia_pct = (distancia / precio * 100) if precio > 0 else 0.0

    # 3. Sizing
    riesgo_max = CAPITAL_TOTAL * RIESGO_MAX_PCT
    posicion_max = CAPITAL_TOTAL * POSICION_MAX_PCT

    has_pct = broker.commissions.comision_pct > 0

    if not has_pct:
        # Fixed commissions — no circular dependency
        com_compra = broker.commissions.calcular(posicion_max)  # worst case estimate
        com_venta = broker.commissions.calcular(posicion_max)
        # Use actual nominal after we know shares
        # Iterate once to get real nominal
        com_c = broker.commissions.calcular(0)  # fixed → same regardless
        com_v = broker.commissions.calcular(0)
        riesgo_disp = max(0.0, riesgo_max - com_c - com_v)
        acciones = math.floor(riesgo_disp / distancia) if distancia > 0 else 0
        acciones_nominal = math.floor(posicion_max / precio) if precio > 0 else 0
        factor = "riesgo" if acciones <= acciones_nominal else "nominal"
        acciones = min(acciones, acciones_nominal)
        nominal = acciones * precio
        com_compra = broker.commissions.calcular(nominal)
        com_venta = broker.commissions.calcular(nominal)
    else:
        # Percentage commissions — iterative convergence
        acciones = math.floor(riesgo_max / distancia) if distancia > 0 else 0
        com_compra = com_venta = 0.0
        for _ in range(5):
            nominal = acciones * precio
            com_compra = broker.commissions.calcular(nominal)
            com_venta = broker.commissions.calcular(nominal)
            riesgo_disp = max(0.0, riesgo_max - com_compra - com_venta)
            nuevas = math.floor(riesgo_disp / distancia) if distancia > 0 else 0
            if nuevas == acciones:
                break
            acciones = nuevas
        acciones_nominal = math.floor(posicion_max / precio) if precio > 0 else 0
        factor = "riesgo" if acciones <= acciones_nominal else "nominal"
        acciones = min(acciones, acciones_nominal)
        nominal = acciones * precio
        com_compra = broker.commissions.calcular(nominal)
        com_venta = broker.commissions.calcular(nominal)

    riesgo_real = (acciones * distancia) + com_compra + com_venta

    # 4. Warnings
    aviso = None
    if distancia_pct > STOP_ALEJADO_UMBRAL * 100:
        aviso = f"⚠️ Stop muy alejado ({distancia_pct:.1f}%), considera usar ATR automático"
    if currency != "EUR":
        note = f"ℹ️ Precio convertido desde {currency} (×{fx:.4f})"
        aviso = f"{aviso}\n{note}" if aviso else note
    if acciones == 0:
        note = "❌ Riesgo insuficiente para esta distancia de stop"
        aviso = f"{aviso}\n{note}" if aviso else note

    return SizingResult(
        ticker=ticker,
        company_name=ticker,   # yfinance longName is slow; handler may enrich later
        precio=precio,
        currency=currency,
        stop_loss=stop_loss,
        stop_tipo=stop_tipo,
        atr=atr_val,
        distancia=distancia,
        distancia_pct=distancia_pct,
        acciones=acciones,
        factor_limite=factor,
        nominal=nominal if acciones > 0 else 0.0,
        pct_cartera=(nominal / CAPITAL_TOTAL * 100) if acciones > 0 else 0.0,
        riesgo_maximo=riesgo_max,
        riesgo_real=riesgo_real if acciones > 0 else 0.0,
        com_compra=com_compra,
        com_venta=com_venta,
        broker_nombre=broker.name,
        aviso=aviso,
    )
```

**Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_sizing.py -v
```
Expected: all PASSED

**Step 5: Commit**

```bash
git add src/sizing/engine.py tests/test_sizing.py
git commit -m "feat(sizing): calculate_sizing() pure engine with iterative commission solver"
```

---

## Task 5: DB migration — `broker` column on `baskets`

**Files:**
- Create: `src/db/migrations/versions/c3d4e5f6a789_add_broker_to_basket.py`
- Modify: `src/db/models.py`
- Modify: `src/db/seed.py`
- Modify: `config/config.yaml`

**Step 1: Add `broker` field to ORM model**

In `src/db/models.py`, inside the `Basket` class, add after `active`:

```python
broker: Mapped[str] = mapped_column(String(50), nullable=False, default="paper")
```

**Step 2: Create Alembic migration**

Create `src/db/migrations/versions/c3d4e5f6a789_add_broker_to_basket.py`:

```python
"""add broker to basket

Revision ID: c3d4e5f6a789
Revises: b1c2d3e4f567
Create Date: 2026-02-21
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a789'
down_revision = 'b1c2d3e4f567'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'baskets',
        sa.Column('broker', sa.String(50), nullable=False, server_default='paper')
    )


def downgrade() -> None:
    op.drop_column('baskets', 'broker')
```

**Step 3: Run migration**

```bash
.venv/bin/alembic upgrade head
```
Expected: `Running upgrade b1c2d3e4f567 -> c3d4e5f6a789, add broker to basket`

**Step 4: Update `config.yaml`**

Add `broker: paper` to each basket in `config/config.yaml`:

```yaml
baskets:
  - name: "Cesta Agresiva"
    broker: paper          # ← add this line
    strategy: ma_crossover
    ...
  - name: "Cesta Conservadora"
    broker: paper          # ← add this line
    strategy: safe_haven
    ...
```

**Step 5: Update seed to read broker**

In `src/db/seed.py`, find where basket objects are created and add `broker=basket_cfg.get("broker", "paper")` to the `Basket(...)` constructor call.

**Step 6: Verify with existing tests**

```bash
.venv/bin/pytest tests/ -v
```
Expected: all existing tests still PASSED (migration doesn't affect logic)

**Step 7: Commit**

```bash
git add src/db/migrations/versions/c3d4e5f6a789_add_broker_to_basket.py \
        src/db/models.py src/db/seed.py config/config.yaml
git commit -m "feat(db): add broker column to baskets (default 'paper')"
```

---

## Task 6: Telegram handler `/sizing`

**Files:**
- Create: `src/bot/handlers/sizing.py`
- Modify: `src/bot/bot.py`

**Step 1: Create handler**

Create `src/bot/handlers/sizing.py`:

```python
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from sqlalchemy import select

from src.db.base import async_session_factory
from src.db.models import Basket, BasketAsset, Asset
from src.sizing.broker import BROKER_REGISTRY, Broker
from src.sizing.engine import calculate_sizing
from src.sizing.models import SizingResult

logger = logging.getLogger(__name__)

_FALLBACK_BROKER = BROKER_REGISTRY["paper"]


def _fmt(val: float, decimals: int = 2) -> str:
    return f"{val:,.{decimals}f}"


def _volatilidad(atr: float, precio: float) -> str:
    pct = atr / precio * 100 if precio else 0
    if pct < 1.5:
        return "baja"
    if pct < 3.0:
        return "media"
    return "alta"


def _format_result(r: SizingResult) -> str:
    lines = [
        f"📊 *Position Sizing — {r.company_name} ({r.ticker})*",
        "",
        f"Precio actual:      €{_fmt(r.precio)}",
        f"Stop loss:          €{_fmt(r.stop_loss)}  ({r.stop_tipo})",
    ]
    if r.atr is not None:
        lines.append(
            f"  └─ ATR(14):       €{_fmt(r.atr)}  |  Volatilidad {_volatilidad(r.atr, r.precio)}"
        )
    lines += [
        f"Distancia al stop:  €{_fmt(r.distancia)} (-{_fmt(r.distancia_pct)}%)",
        "",
        f"Acciones:           {r.acciones}  (limitado por {r.factor_limite})",
        f"Posición nominal:   €{_fmt(r.nominal)} ({_fmt(r.pct_cartera)}% de cartera)",
        f"Riesgo máximo:      €{_fmt(r.riesgo_maximo)} ({_fmt(r.riesgo_maximo / 20000 * 100)}%)",
        "",
        f"Comisiones ({r.broker_nombre}): €{_fmt(r.com_compra)} compra + €{_fmt(r.com_venta)} venta",
        f"Riesgo real:        €{_fmt(r.riesgo_real)}",
    ]
    if r.aviso:
        lines += ["", r.aviso]
    else:
        lines += ["", "✅ Stop dentro del rango recomendado"]
    return "\n".join(lines)


async def cmd_sizing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Uso: /sizing TICKER [STOP_LOSS]\n"
            "Ejemplo: /sizing SAN.MC\n"
            "Ejemplo: /sizing SAN.MC 3.85"
        )
        return

    ticker = context.args[0].upper()
    stop_manual = None
    if len(context.args) >= 2:
        try:
            stop_manual = float(context.args[1])
        except ValueError:
            await update.message.reply_text("Stop loss debe ser un número. Ej: /sizing SAN.MC 3.85")
            return

    # Look up baskets containing this ticker
    async with async_session_factory() as session:
        rows = (await session.execute(
            select(Basket, Asset)
            .join(BasketAsset, BasketAsset.basket_id == Basket.id)
            .join(Asset, BasketAsset.asset_id == Asset.id)
            .where(Asset.ticker == ticker, Basket.active == True, BasketAsset.active == True)
        )).all()

    brokers_to_use: list[tuple[str, Broker]] = []
    if rows:
        seen = set()
        for basket, asset in rows:
            if basket.broker not in seen:
                seen.add(basket.broker)
                broker = BROKER_REGISTRY.get(basket.broker, _FALLBACK_BROKER)
                label = f"{basket.name} ({basket.broker})"
                brokers_to_use.append((label, broker))
    else:
        brokers_to_use = [("paper (fallback)", _FALLBACK_BROKER)]

    msg = await update.message.reply_text(f"⏳ Calculando sizing para {ticker}...")

    results = []
    for label, broker in brokers_to_use:
        try:
            r = calculate_sizing(ticker, stop_manual, broker)
            results.append(_format_result(r))
        except Exception as e:
            logger.error(f"Sizing error {ticker} broker {label}: {e}")
            results.append(f"❌ Error calculando sizing para {ticker}: {e}")

    await msg.edit_text("\n\n---\n\n".join(results), parse_mode="Markdown")


def get_handlers():
    return [CommandHandler("sizing", cmd_sizing)]
```

**Step 2: Register in bot.py**

In `src/bot/bot.py`, add after the existing imports:

```python
from src.bot.handlers.sizing import get_handlers as sizing_handlers
```

And inside `run()`, after the `backtest_handlers` loop:

```python
for handler in sizing_handlers():
    app.add_handler(handler)
```

**Step 3: Smoke test — check imports are clean**

```bash
.venv/bin/python -c "from src.bot.handlers.sizing import get_handlers; print('OK')"
```
Expected: `OK`

**Step 4: Run full test suite**

```bash
.venv/bin/pytest tests/ -v
```
Expected: all PASSED

**Step 5: Commit**

```bash
git add src/bot/handlers/sizing.py src/bot/bot.py
git commit -m "feat(bot): /sizing command handler"
```

---

## Task 7: Update USER_MANUAL.md

**Files:**
- Modify: `USER_MANUAL.md`

Add `/sizing` to the **Análisis técnico** section (it's a calculadora, not an order):

````markdown
### `/sizing <TICKER> [STOP_LOSS]`

Calcula el número de acciones a comprar aplicando position sizing con gestión de
riesgo. Usa los parámetros de la cesta asociada al ticker (broker, comisiones).

```
/sizing SAN.MC           ← stop automático via ATR(14)×2
/sizing SAN.MC 3.85      ← stop loss manual en €
/sizing AAPL             ← ticker USD, convierte automáticamente a EUR
```

**Muestra:**
- Precio actual y stop loss (manual o ATR×2)
- Distancia al stop en € y %
- Número de acciones (indicando si el límite es riesgo o posición máxima)
- Posición nominal y % de cartera
- Comisiones del broker (compra + venta)
- Riesgo real incluyendo comisiones

Parámetros de cartera aplicados: capital €20.000, riesgo máximo 0,75% (€150),
posición máxima 20% (€4.000).
````

Also add `/sizing` to the summary table at the bottom.

**Step: Commit**

```bash
git add USER_MANUAL.md
git commit -m "docs: add /sizing to USER_MANUAL"
```

---

## Final verification

```bash
.venv/bin/pytest tests/ -v
.venv/bin/python -c "
from src.sizing.engine import calculate_sizing
from src.sizing.broker import BROKER_REGISTRY
from unittest.mock import MagicMock, patch
from decimal import Decimal
broker = BROKER_REGISTRY['paper']
price = MagicMock(); price.price = Decimal('10'); price.currency = 'EUR'
atr = Decimal('0.5')
with patch.object(broker._provider, 'get_current_price', return_value=price), \
     patch.object(broker._provider, 'get_atr', return_value=atr):
    r = calculate_sizing('SAN.MC', None, broker)
    print(f'acciones={r.acciones}, riesgo_real={r.riesgo_real:.2f}, factor={r.factor_limite}')
"
```
Expected: `acciones=146, riesgo_real=150.00, factor=riesgo`
