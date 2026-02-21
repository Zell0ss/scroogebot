# TioGilito — Manual de Usuario

Bot de Telegram para paper-trading de cestas compartidas con alertas automáticas de estrategia.

---

## Índice

1. [Primeros pasos](#primeros-pasos)
2. [Portfolio](#portfolio)
3. [Cestas](#cestas)
4. [Órdenes](#órdenes)
5. [Análisis técnico](#análisis-técnico)
6. [Backtest](#backtest)
7. [Administración](#administración-solo-owner)
8. [Roles](#roles)
9. [Alertas automáticas](#alertas-automáticas)

---

## Primeros pasos

### `/start`

Registra tu cuenta en el bot o muestra el mensaje de bienvenida si ya estás registrado.

Si no estás pre-registrado, el bot te mostrará tu **ID de Telegram** y **username** para que se los pases al administrador.

```
/start
```

> El administrador debe pre-registrarte primero con `/register` (ver sección Administración). Una vez hecho, `/start` completa el registro automáticamente.

---

## Portfolio

### `/valoracion [nombre_cesta]`

Muestra la valoración actual de todas las cestas activas: capital invertido, valor de mercado, P&L total y detalle por posición. Incluye enlace a Finviz.

```
/valoracion
/valoracion Conservadora
```

**Ejemplo de salida:**
```
📊 Conservadora — 21 Feb 2026 09:30
💼 Capital invertido: 10.250,00€
💰 Valor actual:      11.430,00€
📈 P&L total: +1.180,00€ (+11,51%)
─────────────────────────────────
AAPL     10 × $185,32 = 1.853,20€  📈 +5,12%
MSFT      5 × $420,10 = 2.100,50€  📉 -1,30%
─────────────────────────────────
💵 Cash disponible: 2.500,00€
```

---

### `/cartera`

Muestra las posiciones abiertas de todas las cestas: cantidad de acciones y precio medio de entrada.

```
/cartera
```

**Ejemplo de salida:**
```
💼 Conservadora

AAPL      10.0000 acc @ 176.20
MSFT       5.0000 acc @ 425.00

💵 Cash: 2.500,00€
```

---

### `/historial`

Muestra las últimas 10 órdenes ejecutadas en cada cesta, ordenadas de más reciente a más antigua.

```
/historial
```

**Ejemplo de salida:**
```
📋 Conservadora — Últimas 10 órdenes

🟢 21/02 09:15 BUY  10.00 AAPL @ 185.32
🔴 18/02 14:30 SELL  5.00 MSFT @ 430.10
```

---

## Cestas

### `/cestas`

Lista todas las cestas activas con su estrategia y perfil de riesgo.

```
/cestas
```

**Ejemplo de salida:**
```
🗂 Cestas disponibles

• Conservadora — estrategia: stop_loss (low)
• Crecimiento   — estrategia: ma_crossover (medium)
```

---

### `/cesta <nombre_cesta>`

Muestra el detalle completo de una cesta: activos que la componen, miembros y cash disponible.

```
/cesta Conservadora
```

**Ejemplo de salida:**
```
🗂 Conservadora
Estrategia: stop_loss | Perfil: low
Cash: 2.500,00€

Assets:
  • AAPL (NASDAQ)
  • MSFT (NASDAQ)

Miembros:
  • @admin [OWNER]
  • @ElParra72 [MEMBER]
```

---

## Órdenes

> Las órdenes se ejecutan al precio de mercado actual (paper trading).

### `/compra <TICKER> <cantidad>`

Compra acciones de un activo que esté en alguna cesta activa.

```
/compra AAPL 10
/compra MSFT 5.5
```

- La cantidad puede ser decimal.
- El bot descuenta el importe del cash de la cesta.
- Falla si no hay cash suficiente.

---

### `/vende <TICKER> <cantidad>`

Vende acciones de un activo en cartera.

```
/vende AAPL 5
/vende MSFT 2.5
```

- Falla si no hay suficientes acciones en posición.

---

## Análisis técnico

### `/buscar <texto>`

Busca tickers por nombre de empresa o símbolo. Primero busca entre los activos
de tus cestas (resultados marcados con 📌), y si hay pocos resultados consulta
también Yahoo Finance.

```
/buscar santander
/buscar banco santander
/buscar NVDA
```

**Muestra:**
- Activos en tus cestas que coincidan (con la cesta a la que pertenecen)
- Resultados adicionales de Yahoo Finance si hay menos de 3 locales
- Ticker, nombre, exchange y tipo (Equity, ETF, etc.)
- Sugerencia de comandos para el primer resultado

---

### `/analiza <TICKER>`

Obtiene el análisis técnico de cualquier ticker (no tiene que estar en una cesta). Usa datos de los últimos 3 meses.

```
/analiza AAPL
/analiza EURUSD=X
```

**Muestra:**
- Precio actual
- Cambio en el día (%)
- SMA 20 y SMA 50
- Tendencia (alcista/bajista)
- RSI(14) con etiqueta: sobrecomprado >70, sobrevendido <30, neutral
- Enlace a Finviz

**Ejemplo de salida:**
```
📊 Análisis: AAPL
💰 Precio: 185.32 USD
📅 Cambio 1d: +1.23%

SMA 20: 182.40
SMA 50: 178.90
Tendencia: 📈 Alcista
RSI (14): 62.4 — neutral ⚪

🔍 Finviz
```

---

### `/sizing <TICKER> [STOP_LOSS]`

Calcula el número de acciones a comprar aplicando position sizing con gestión de riesgo. Usa los parámetros del broker asociado a la cesta que contiene el ticker.

```
/sizing SAN.MC           ← stop automático via ATR(14)×2
/sizing SAN.MC 3.85      ← stop loss manual en €
/sizing AAPL             ← ticker USD, convierte automáticamente a EUR
/sizing AAPL 180         ← stop manual en USD
```

**Muestra:**
- Precio actual y stop loss (manual o ATR×2, con volatilidad si es automático)
- Distancia al stop en € y %
- Número de acciones y factor limitante (riesgo o posición máxima)
- Posición nominal y % de cartera
- Comisiones del broker (compra + venta)
- Riesgo real incluyendo comisiones

**Parámetros de cartera:** capital €20.000 · riesgo máximo 0,75% (€150) · posición máxima 20% (€4.000)

> Si el ticker no está en ninguna cesta, usa el broker `paper` como fallback. No ejecuta ninguna orden — es solo una calculadora.

---

## Backtest

### `/backtest [período]`

Ejecuta un backtest histórico de cada cesta activa con su estrategia configurada. Compara la rentabilidad de la estrategia frente a buy & hold.

```
/backtest
/backtest 6mo
/backtest 2y
```

**Períodos válidos:** `1mo` `3mo` `6mo` `1y` (defecto) `2y`

**Muestra por activo:**
- Rentabilidad de la estrategia vs. B&H y alpha (α)
- Ratio de Sharpe
- Máximo drawdown
- Número de operaciones y win rate

**Ejemplo de salida:**
```
📊 Backtest: Conservadora (1y)

AAPL
  Rentabilidad: +18.4%  (B&H: +14.2%,  α: +4.2%)
  Sharpe: 1.34  |  Max DD: -8.6%
  Operaciones: 12  |  Win rate: 67%
```

> El backtest puede tardar unos segundos dependiendo del número de activos.

---

## Administración (solo OWNER)

Los siguientes comandos requieren ser OWNER de al menos una cesta.

---

### `/register <tg_id> <username>`

Pre-registra a un nuevo usuario en el sistema. El usuario debe enviarte su ID y username usando `/start` en el bot.

```
/register 1035608410 ElParra72
```

> Después de hacer esto, el usuario debe enviar `/start` para completar el registro.

---

### `/adduser <@username> <OWNER|MEMBER> <nombre_cesta>`

Asigna a un usuario ya registrado a una cesta con un rol. El usuario debe haber completado el registro (haber hecho `/start`) antes de poder añadirlo.

```
/adduser @ElParra72 MEMBER Conservadora
/adduser @ElParra72 OWNER Crecimiento
```

También acepta el rol al final:
```
/adduser @ElParra72 Conservadora MEMBER
```

---

### `/watchlist`

Muestra tu lista personal de activos en seguimiento.

```
/watchlist
```

**Ejemplo de salida:**
```
👀 Watchlist

🔴 NVDA NVIDIA Corporation — revisar en Q2
🟢 META Meta Platforms
```

---

### `/addwatch <TICKER> [Nombre] [| nota]`

Añade un activo a tu watchlist. El nombre y la nota son opcionales; separa la nota con `|`.

```
/addwatch NVDA
/addwatch NVDA NVIDIA Corporation
/addwatch NVDA NVIDIA Corporation | revisar tras resultados Q1
```

---

### `/logs [N]`

Muestra los últimos N comandos del registro de auditoría (máximo 50). Por defecto muestra 20.

```
/logs
/logs 50
```

**Ejemplo de salida:**
```
📋 Últimos 20 comandos

✅ 21/02 09:15 @admin — /compra
✅ 21/02 09:10 @ElParra72 — /valoracion
❌ 20/02 18:30 @ElParra72 — /vende
```

---

## Roles

| Rol    | Puede ver portfolio | Puede operar | Puede añadir usuarios | Puede ver logs |
|--------|--------------------|--------------|-----------------------|----------------|
| MEMBER | Sí                 | Sí           | No                    | No             |
| OWNER  | Sí                 | Sí           | Sí                    | Sí             |

Un usuario puede ser OWNER en una cesta y MEMBER en otra.

---

## Alertas automáticas

El bot ejecuta un escáner automático periódico sobre todas las cestas activas. Cuando una estrategia genera una señal (por ejemplo, stop loss alcanzado o cruce de medias), el bot envía una notificación directamente al chat con botones de acción:

- **Confirmar** — ejecuta la orden sugerida
- **Ignorar** — descarta la alerta sin operar

Las alertas no se repiten hasta que cambie el estado del activo.

---

## Resumen de comandos

| Comando | Descripción | Requiere |
|---------|-------------|----------|
| `/start` | Registrarse / bienvenida | — |
| `/valoracion [cesta]` | Valoración de cestas | Registrado |
| `/cartera` | Posiciones abiertas | Registrado |
| `/historial` | Últimas 10 órdenes | Registrado |
| `/cestas` | Lista de cestas activas | Registrado |
| `/cesta <nombre>` | Detalle de una cesta | Registrado |
| `/compra <TICKER> <qty>` | Comprar acciones | Registrado |
| `/vende <TICKER> <qty>` | Vender acciones | Registrado |
| `/analiza <TICKER>` | Análisis técnico (RSI, SMA) | Registrado |
| `/buscar <texto>` | Buscar tickers por nombre | Registrado |
| `/sizing <TICKER> [STOP_LOSS]` | Position sizing con comisiones | Registrado |
| `/backtest [período]` | Backtest de estrategias | Registrado |
| `/register <id> <user>` | Pre-registrar usuario | OWNER |
| `/adduser <@user> <ROL> <cesta>` | Añadir usuario a cesta | OWNER |
| `/watchlist` | Ver watchlist personal | OWNER |
| `/addwatch <TICKER> [nombre\|nota]` | Añadir a watchlist | OWNER |
| `/logs [N]` | Registro de auditoría | OWNER |
