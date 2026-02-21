# 🦆 ScroogeBot — Especificación del Proyecto

> Bot de inversión en bolsa para Telegram con gestión de cestas compartidas, alertas automáticas y backtesting de estrategias.
> Nombre Telegram: **TioGilitoBot** · Repo/Servicio: **scroogebot**

---

## 1. Visión General

ScroogeBot es un sistema modular de apoyo a la inversión bursátil operado vía Telegram. Permite a un grupo de inversores gestionar cestas de valores compartidas, recibir alertas automáticas basadas en estrategias configurables, ejecutar órdenes mediante lenguaje natural, y visualizar el estado de sus carteras en tiempo real.

El sistema está diseñado con una separación estricta entre el PoC y el entorno de producción: los puntos de integración con servicios externos (fuentes de datos y ejecución de órdenes) son interfaces abstractas que permiten el swap sin afectar al resto del sistema.

```
PoC                          Producción
──────────────────────────   ──────────────────────────
yfinance (datos gratuitos) → Broker de intradía (API)
Paper trading (simulado)   → Ejecución real de órdenes
```

---

## 2. Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                     TELEGRAM BOT LAYER                      │
│          Comandos · Alertas · Confirmaciones · Roles        │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                   ORCHESTRATOR / EVENT BUS                   │
│          Coordina módulos · Gestiona estado · Agenda        │
└──────┬──────────────┬─────────────────┬─────────────────────┘
       │              │                 │
┌──────▼──────┐ ┌─────▼──────┐ ┌───────▼───────┐ ┌──────────┐
│  DATA LAYER │ │  STRATEGY  │ │   PORTFOLIO   │ │BACKTEST  │
│             │ │   ENGINE   │ │    ENGINE     │ │ ENGINE   │
│ yfinance    │ │            │ │               │ │          │
│ → Broker    │ │ Estrategias│ │ Posiciones    │ │vectorbt  │
│             │ │ Señales    │ │ P&L · Órdenes │ │          │
└──────┬──────┘ └─────┬──────┘ └───────┬───────┘ └──────────┘
       │              │                │
┌──────▼──────────────▼────────────────▼─────────────────────┐
│                     ALERT ENGINE                            │
│             Genera alertas desde señales                    │
└─────────────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│                     ORDER LAYER (abstracto)                  │
│          Paper Trading (PoC)  →  Broker Real (Prod)         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Estructura del Proyecto

```
scroogebot/
├── config/
│   ├── config.yaml              # Assets, cestas, estrategias, thresholds
│   └── logging.yaml
├── src/
│   ├── data/
│   │   ├── base.py              # Interface abstracta DataProvider
│   │   ├── yahoo.py             # Implementación yfinance
│   │   └── models.py            # Price, OHLCV, etc.
│   ├── portfolio/
│   │   ├── engine.py            # Valoración, P&L, posiciones
│   │   └── models.py            # Basket, Position, Order
│   ├── strategies/
│   │   ├── base.py              # Interface abstracta Strategy
│   │   ├── stop_loss.py         # Stop-loss / Take-profit
│   │   ├── ma_crossover.py      # Media móvil cruzada
│   │   ├── rsi.py               # RSI Contrarian
│   │   ├── bollinger.py         # Bollinger Bands
│   │   └── safe_haven.py        # Rotación a valores refugio
│   ├── orders/
│   │   ├── base.py              # Interface abstracta OrderExecutor
│   │   └── paper.py             # Paper trading
│   ├── alerts/
│   │   └── engine.py            # Genera alertas desde señales
│   ├── backtest/
│   │   └── engine.py            # Wrapper vectorbt
│   ├── bot/
│   │   ├── handlers/
│   │   │   ├── portfolio.py     # /valoracion, /cartera, /posicion
│   │   │   ├── orders.py        # /compra, /vende
│   │   │   ├── baskets.py       # /cestas, /cesta
│   │   │   ├── analysis.py      # /analiza
│   │   │   └── admin.py         # /adduser, /setrole
│   │   └── bot.py
│   └── db/
│       ├── models.py            # SQLAlchemy models
│       └── migrations/          # Alembic
├── tests/
├── scroogebot.service           # Systemd unit file
└── pyproject.toml
```

---

## 4. Interfaces Abstractas — Puntos de Swap PoC → Producción

Estas tres interfaces son el núcleo de la modularidad. Cambiar de PoC a producción es únicamente cuestión de implementar nuevas clases que las satisfagan.

```python
# data/base.py
class DataProvider(ABC):
    @abstractmethod
    def get_current_price(self, ticker: str) -> Decimal: ...

    @abstractmethod
    def get_historical(self, ticker: str, period: str, interval: str) -> pd.DataFrame: ...


# orders/base.py
class OrderExecutor(ABC):
    @abstractmethod
    def buy(self, basket_id: int, ticker: str, quantity: Decimal, price: Decimal) -> Order: ...

    @abstractmethod
    def sell(self, basket_id: int, ticker: str, quantity: Decimal, price: Decimal) -> Order: ...


# strategies/base.py
class Strategy(ABC):
    @abstractmethod
    def evaluate(self, ticker: str, data: pd.DataFrame) -> Signal | None: ...
    # Signal: BUY | SELL | HOLD con precio, razón y nivel de confianza
```

---

## 5. Modelo de Datos

```
┌──────────┐     ┌───────────────┐     ┌─────────┐
│  users   │────<│ basket_members│>────│ baskets │
│          │     │               │     │         │
│ id       │     │ basket_id     │     │ id      │
│ tg_id    │     │ user_id       │     │ name    │
│ username │     │ role          │     │ strategy│
└──────────┘     └───────────────┘     │ profile │
                                       └────┬────┘
                                            │
                    ┌───────────────────────┼──────────────────┐
                    │                       │                  │
              ┌─────▼──────┐        ┌───────▼──────┐   ┌──────▼──────┐
              │basket_assets│       │  positions   │   │   orders    │
              │            │        │              │   │             │
              │ basket_id  │        │ basket_id    │   │ basket_id   │
              │ asset_id   │        │ asset_id     │   │ asset_id    │
              │ active     │        │ quantity     │   │ type        │
              └─────┬──────┘        │ avg_price    │   │ quantity    │
                    │               └──────────────┘   │ price       │
              ┌─────▼──────┐                           │ status      │
              │   assets   │        ┌──────────────┐   │ triggered_by│
              │            │        │    alerts    │   └─────────────┘
              │ ticker     │        │              │
              │ name       │        │ basket_id    │   ┌─────────────┐
              │ market     │        │ strategy     │   │  watchlist  │
              │ currency   │        │ signal       │   │             │
              └────────────┘        │ status       │   │ ticker      │
                                    └──────────────┘   │ note        │
                                                       │ status      │
                                                       └─────────────┘
```

### Roles de usuario por cesta

| Rol | Capacidades |
|-----|------------|
| **OWNER** | Ordena directamente, confirma alertas, gestiona la cesta |
| **MEMBER** | Consulta, propone órdenes (se ejecutan notificando al grupo) |

---

## 6. Modelo de Cestas

La **Cesta** es la entidad central del sistema. Cada cesta tiene una estrategia activa, un conjunto de assets y un pool de capital compartido entre sus miembros.

```
┌─────────────────────────────────────────────┐
│                   CESTA                     │
│                                             │
│  nombre:    "Cesta Agresiva"                │
│  estrategia: MomentumStrategy               │
│  miembros:  [Josem (OWNER), Paco (MEMBER)]  │
│  assets:    [AAPL, MSFT, SAN.MC]            │
│  capital:   10.000€ (pool común)            │
│  perfil:    aggressive                      │
└─────────────────────────────────────────────┘
```

- Las posiciones son **compartidas**: la cesta compra/vende como unidad
- El capital es un **pool común**: no se distingue la aportación individual
- Las alertas llegan a **todos los miembros**
- La decisión final la toma el **OWNER**, aunque cualquier miembro puede emitir órdenes

---

## 7. Estrategias de Inversión

| Estrategia | Caso de uso | Riesgo | Estado |
|-----------|------------|--------|--------|
| **Stop-loss / Take-profit** | Control de pérdidas, cualquier perfil | Bajo | PoC v1 |
| **MA Crossover** (SMA 20/50) | Tendencias largas, valores estables | Medio | PoC v1 |
| **RSI Contrarian** | Valores con oscilaciones predecibles | Medio | PoC v1 |
| **Bollinger Mean Reversion** | Mercados laterales | Medio | PoC v1 |
| **Safe Haven Rotation** | Cartera conservadora con refugio automático | Bajo | PoC v1 |
| **Event-driven (LLM + noticias)** | IPOs, valores con ruido noticioso | Alto | v2 |

### Configuración de estrategia en YAML

```yaml
strategies:
  stop_loss:
    stop_loss_pct: 8.0        # Vender si baja más de un 8%
    take_profit_pct: 15.0     # Vender si sube más de un 15%
    safe_haven_tickers:       # Hacia dónde mover el capital
      - GLD
      - BND

  rsi:
    period: 14
    oversold_threshold: 30
    overbought_threshold: 70

baskets:
  - name: "Cesta Agresiva"
    strategy: ma_crossover
    assets:
      - AAPL
      - MSFT
      - NVDA
    risk_profile: aggressive

  - name: "Cesta Conservadora"
    strategy: safe_haven
    assets:
      - SAN.MC
      - IBE.MC
      - GLD
    risk_profile: conservative
```

---

## 8. Flujos Principales

### 8.1 Flujo de alerta automática

```
Scheduler (cada N min durante horario de mercado)
    │
    ▼
DataProvider.get_current_price(ticker)
    │
    ▼
Strategy.evaluate(ticker, data) ──► None (HOLD) → fin
    │
    ▼ Signal (BUY|SELL)
AlertEngine.create_alert()
    │
    ▼
Telegram → todos los miembros de la cesta
"⚠️ AAPL ha alcanzado stop-loss ($170). ¿Ejecutar venta? [✅ Sí / ❌ No]"
    │
    ├─► ✅ OWNER confirma → OrderExecutor.sell() → notifica grupo
    └─► ❌ Rechazada / Expirada → alert.status = REJECTED/EXPIRED
```

### 8.2 Flujo de orden directa

```
Usuario: /compra AAPL 10

    ├─► OWNER → Bot pide confirmación
    │          "¿Confirmas compra de 10 AAPL a ~$185? [✅/❌]"
    │          ✅ → OrderExecutor.buy() → notifica grupo
    │
    └─► MEMBER → OrderExecutor.buy() → ejecuta + notifica grupo
               "[Paco] ha ordenado compra de 10 AAPL. Ejecutado."
```

### 8.3 Flujo de valoración

```
Usuario: /valoracion cesta1

    ▼
PortfolioEngine.get_valuation(basket_id)
    │  DataProvider.get_current_price() para cada asset
    ▼
Telegram:

📊 Cesta Agresiva — 21 Feb 2026 18:42

💼 Capital invertido: 8.450€
💰 Valor actual:      9.123€
📈 P&L total:        +673€ (+7.96%)

─────────────────────────────
AAPL    10 acc × $185.3  = $1.853  📈 +4.2%
MSFT     5 acc × $412.1  = $2.060  📈 +1.8%
SAN.MC 200 acc × 4.21€  =   842€  📉 -0.9%
─────────────────────────────
💵 Cash disponible: 1.550€

🔍 Detalle: https://finviz.com/screener.ashx?v=111&t=AAPL,MSFT,SAN.MC
```

---

## 9. Comandos del Bot

| Comando | Descripción | Rol mínimo |
|---------|-------------|-----------|
| `/valoracion [cesta]` | Valoración actual con link Finviz | MEMBER |
| `/cartera [cesta]` | Posiciones abiertas | MEMBER |
| `/historial [cesta]` | Últimas órdenes ejecutadas | MEMBER |
| `/analiza TICKER` | Análisis técnico del valor | MEMBER |
| `/compra TICKER cantidad` | Orden de compra | MEMBER |
| `/vende TICKER cantidad` | Orden de venta | MEMBER |
| `/cestas` | Lista de cestas disponibles | MEMBER |
| `/backtest cesta periodo` | Lanza backtesting | OWNER |
| `/estrategia cesta nombre` | Cambia estrategia activa | OWNER |
| `/adduser @user rol cesta` | Añade usuario a una cesta | OWNER |
| `/watchlist` | Muestra valores en espera (IPOs) | MEMBER |

---

## 10. Módulo de Backtesting

```
Seleccionar cesta y estrategia
    │
    ▼
DataProvider.get_historical(ticker, period)
    │
    ▼
vectorbt engine (backtest vectorizado)
    │
    ▼
Métricas:
  - Rentabilidad total y anualizada
  - Sharpe ratio
  - Máximo drawdown
  - Nº de operaciones, % acierto
  - Comparativa vs benchmark (índice)
    │
    ▼
Resumen vía Telegram + link Finviz para el período analizado
```

El flujo de validación de cualquier estrategia nueva será siempre:

```
Definir estrategia → Backtest → Revisar métricas → Paper trading → Real
```

---

## 11. Stack Tecnológico

| Capa | Tecnología | Justificación |
|------|-----------|---------------|
| Datos de mercado | `yfinance` | Estable, swap limpio a broker real |
| Indicadores técnicos | `pandas-ta` | Sin dependencias C, bien mantenido |
| Backtesting | `vectorbt` | Moderno, vectorizado, métricas completas |
| Bot Telegram | `python-telegram-bot` v20+ | Async nativo |
| Base de datos | MariaDB (seb01) | Infraestructura existente |
| ORM + migraciones | `SQLAlchemy` + `alembic` | Migraciones limpias desde el día 1 |
| Scheduler | `APScheduler` 3.x | Integración simple con async, horarios por mercado |
| Configuración | YAML + `pydantic-settings` | Validación en arranque, no en runtime |
| Deployment | systemd (seb01) | Consistente con Sebastian |

---

## 12. Servicio Systemd

```ini
[Unit]
Description=ScroogeBot — Investment Telegram Bot

[Service]
Type=simple
ExecStart=/home/user/data/scroogebot/.venv/bin/python scroogebot.py
User=user
Group=group
WorkingDirectory=/home/user/data/scroogebot
Restart=always
RestartSec=10
EnvironmentFile=/home/user/data/scroogebot/.env

[Install]
WantedBy=multi-user.target
```

---

## 13. Consideraciones de Mercado

- **Horarios múltiples**: IBEX cierra 17:30 CET, NYSE 22:00 CET. El scheduler debe conocer el mercado de cada asset y solo hacer polling en horario activo.
- **Divisas**: La cartera se valora en EUR. Se usa `EURUSD=X` vía yfinance para la conversión.
- **IPOs en watchlist**: Assets como Anthropic (aún sin cotizar) se mantienen en una watchlist con estado `PENDING`. El bot monitoriza periódicamente si el ticker aparece en el mercado.
- **Fuera de horario**: El bot sigue respondiendo a comandos de consulta. Las alertas de estrategia se suspenden.

---

## 14. Fases de Desarrollo

```
FASE A — Core de datos y portfolio          ← EMPEZAMOS AQUÍ
├── DataProvider (yfinance)
├── PortfolioEngine (posiciones, P&L)
├── OrderExecutor (paper trading)
└── Schema de BD + migraciones Alembic

FASE B — Bot de Telegram
├── Comandos básicos (/valoracion, /compra, /vende)
├── Sistema de roles OWNER/MEMBER
├── Alertas y flujo de confirmación
└── Generación de URL Finviz

FASE C — Backtesting y estrategias avanzadas
├── Wrapper vectorbt
├── Implementación de todas las estrategias
├── Comando /backtest
└── Watchlist de IPOs

PRODUCCIÓN (futuro)
├── Swap DataProvider → Broker real
├── Swap OrderExecutor → Broker real
└── Websockets en lugar de polling
```

---

*ScroogeBot — "Dinero que duerme es dinero que llora" 🦆*