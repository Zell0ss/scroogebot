# Diseño: Alertas enriquecidas + Explicación Sonnet

**Fecha:** 2026-02-24
**Estado:** Aprobado

---

## Objetivo

Enriquecer las alertas del AlertEngine con:
1. Datos de posición actual (cantidad, precio de entrada, P&L)
2. Cantidad sugerida para la operación
3. Confianza de la señal
4. Indicadores técnicos contextuales (SMA20, SMA50, RSI14, ATR%, tendencia)
5. Explicación en lenguaje natural (Haiku) para usuarios no-avanzados
6. Todas las `reason` de estrategias traducidas al español
7. Comando `/modo` para alternar entre modo básico (explicativo) y avanzado (técnico)

---

## Enfoque elegido: MarketContext dataclass + AsyncAnthropic

- En `_scan_basket`: computar indicadores desde `historical.data` ya disponible (0 llamadas extra)
- Empaquetar en `MarketContext` dataclass y pasarlo al tuple de alertas pendientes
- En `_notify()`: construir mensaje técnico enriquecido + llamada async a Haiku si `user.advanced_mode=False`

---

## Estructura de datos

### `MarketContext` — nuevo fichero `src/alerts/market_context.py`

```python
@dataclass
class MarketContext:
    ticker: str
    price: Decimal
    # Indicadores técnicos (calculados desde historical.data, sin llamadas extra)
    sma20: float | None
    sma50: float | None
    rsi14: float | None
    atr_pct: float | None   # ATR14 / precio * 100 — más útil que valor absoluto
    trend: str              # "alcista" | "bajista" | "lateral"
    # Posición actual
    position_qty: Decimal   # 0 si no hay posición abierta
    avg_price: Decimal | None
    pnl_pct: float | None   # None si no hay posición
    # Operación sugerida
    suggested_qty: Decimal  # BUY: 10% cash / precio; SELL: toda la posición
```

### Función `compute_market_context()`

```python
def compute_market_context(
    ticker: str,
    data: pd.DataFrame,       # historical.data ya disponible
    price: Decimal,
    pos: Position | None,
    basket_cash: Decimal,
    signal_action: str,
) -> MarketContext
```

Calcula indicadores con `ta` library (ya instalada):
- SMA20/50: `close.rolling(N).mean().iloc[-1]`
- RSI14: `ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]`
- ATR%: `ta.volatility.AverageTrueRange(..., window=14).average_true_range().iloc[-1] / price * 100`
- Tendencia: precio > SMA20 > SMA50 → "alcista" | precio < SMA20 < SMA50 → "bajista" | else → "lateral"

---

## Cambios en `AlertEngine`

### `_scan_basket` (src/alerts/engine.py)

```python
# Tipo cambia de list[tuple[Alert, str]] a list[tuple[Alert, str, MarketContext]]
new_alerts: list[tuple[Alert, str, MarketContext]] = []

# Tras strategy.evaluate():
market_ctx = compute_market_context(
    asset.ticker, historical.data, price_obj.price,
    pos, basket.cash, signal.action
)
new_alerts.append((alert, asset.ticker, market_ctx))

# En el bucle de notificaciones:
await self._notify(alert, basket.name, ticker, market_ctx)
```

### `_notify()` — nuevo formato del mensaje

**Modo básico** (`advanced_mode=False`, defecto):
```
⚠️ *NombreCesta* — rsi

🔴 VENTA: *SAN.MC*
Precio: 4.18 € | Confianza: 70%
Posición: 20 acc @ 4.32 € (P&L: −3.2%)
Cantidad sugerida: 20 acc
Razón: RSI saliendo de zona de sobrecompra (71.3)
SMA20: 4.25 | SMA50: 4.10 | RSI: 71.3 | ATR: 1.9%
Tendencia: lateral

💬 El RSI ha tocado zona de sobrecompra y empieza a ceder...
[2-3 frases de Haiku en español, fallback silencioso si falla]

¿Ejecutar venta?
[✅ Ejecutar]  [❌ Rechazar]
```

**Modo avanzado** (`advanced_mode=True`): igual pero sin el bloque 💬.

### `_build_explanation()` — llamada async a Haiku

```python
async def _build_explanation(
    self, strategy: str, signal: str, reason: str, ctx: MarketContext
) -> str | None
```

- Modelo: `claude-haiku-4-5-20251001` (más rápido/barato, suficiente para 2-3 frases)
- `max_tokens=200`
- Prompt en español: estrategia, señal, razón técnica, indicadores del MarketContext
- Returns `None` si falla (el mensaje se envía sin explicación, sin levantar excepción)

---

## DB: `User.advanced_mode`

```python
advanced_mode: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
```

- Default=False → nuevos usuarios reciben explicaciones (modo educativo por defecto)
- Alembic migration autogenerada

---

## Comando `/modo`

```
/modo             → muestra modo actual
/modo avanzado    → advanced_mode = True  (solo datos técnicos)
/modo basico      → advanced_mode = False (datos + explicación Haiku)
```

Implementado en `src/bot/handlers/admin.py`, registrado en `bot.py` y `help.py`.

---

## Traducciones al español

Todas las cadenas `reason` en:

| Fichero | Inglés → Español |
|---------|-----------------|
| `rsi.py` | "RSI exiting oversold zone (X)" → "RSI saliendo de zona de sobreventa (X)" |
| `rsi.py` | "RSI exiting overbought zone (X)" → "RSI saliendo de zona de sobrecompra (X)" |
| `ma_crossover.py` | "MA5 crossed above MA20" → "MA5 cruzó al alza MA20" |
| `ma_crossover.py` | "MA5 crossed below MA20" → "MA5 cruzó a la baja MA20" |
| `bollinger.py` | "Price at/below lower Bollinger band (X)" → "Precio en/bajo banda inferior Bollinger (X)" |
| `bollinger.py` | "Price at/above upper Bollinger band (X)" → "Precio en/sobre banda superior Bollinger (X)" |
| `stop_loss.py` | "Stop-loss triggered: X% drop" → "Stop-loss activado: caída del X%" |
| `stop_loss.py` | "Take-profit triggered: X% gain" → "Take-profit activado: subida del X%" |
| `safe_haven.py` | "Drawdown X% from peak — rotating to safe haven" → "Drawdown X% desde máximo — rotando a activo refugio" |

---

## Dependencia nueva

```toml
# pyproject.toml
"anthropic>=0.40",
```

Requiere `pip install anthropic` y `alembic upgrade head`.

---

## Tests

| Fichero | Tests |
|---------|-------|
| `tests/test_market_context.py` | `compute_market_context` con datos sintéticos: tendencia alcista/bajista/lateral, ATR%, P&L, suggested_qty BUY vs SELL |
| `tests/test_alert_notify.py` | `_notify` avanzado=True no llama Anthropic; avanzado=False sí llama; fallo Anthropic no lanza excepción |

---

## Ficheros modificados

| Fichero | Cambio |
|---------|--------|
| `src/alerts/market_context.py` | **nuevo** — MarketContext dataclass + compute_market_context() |
| `src/alerts/engine.py` | new_alerts tipo, compute_market_context() call, _notify() firma y lógica, _build_explanation() |
| `src/db/models.py` | User.advanced_mode campo |
| `src/db/migrations/` | nueva migración Alembic |
| `src/strategies/rsi.py` | reason en español |
| `src/strategies/ma_crossover.py` | reason en español |
| `src/strategies/bollinger.py` | reason en español |
| `src/strategies/stop_loss.py` | reason en español |
| `src/strategies/safe_haven.py` | reason en español |
| `src/bot/handlers/admin.py` | cmd_modo() |
| `src/bot/bot.py` | registro cmd_modo |
| `src/bot/handlers/help.py` | /modo en COMMAND_LIST |
| `pyproject.toml` | anthropic>=0.40 |
| `tests/test_market_context.py` | **nuevo** |
| `tests/test_alert_notify.py` | **nuevo** |
