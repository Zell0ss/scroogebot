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

> **Gestión de cestas** (`/estrategia`, `/nuevacesta`, `/eliminarcesta`) está documentada al final de la sección [Cestas](#cestas).

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
Estrategia: stop_loss | Stop-loss: 8.0% | Perfil: low
Cash: 2.500,00€

Assets:
  • AAPL (NASDAQ)
  • MSFT (NASDAQ)

Miembros:
  • @admin [OWNER]
  • @ElParra72 [MEMBER]
```

---

### `/estrategia <nombre_cesta> [estrategia] [stop_loss_%]`

**Sin argumentos extra:** muestra la estrategia actual y el stop loss configurado.

```
/estrategia Cesta Agresiva
→ 📊 Cesta Agresiva usa estrategia: ma_crossover
  Stop-loss: 8.0% (desde precio de compra)
  Disponibles: stop_loss, ma_crossover, rsi, bollinger, safe_haven
```

**Cambiar estrategia** (solo OWNER):
```
/estrategia Cesta Agresiva rsi
```

**Cambiar stop loss** (solo OWNER):
```
/estrategia Cesta Agresiva 10        ← establece stop loss al 10%
/estrategia Cesta Agresiva 0         ← desactiva el stop loss
```

**Cambiar estrategia y stop loss a la vez** (solo OWNER):
```
/estrategia Cesta Agresiva rsi 8     ← estrategia RSI con stop loss al 8%
```

> El stop loss se aplica por encima de cualquier estrategia: si una posición cae ≥ el porcentaje configurado desde el precio de compra, el bot genera una alerta de venta automáticamente, independientemente de lo que diga la estrategia.

---

### `/nuevacesta <nombre> <estrategia> [stop_loss_%]`

Crea una nueva cesta de paper trading. Cualquier usuario registrado puede crear una cesta; el creador se convierte automáticamente en **OWNER**.

```
/nuevacesta TechGrowth rsi          ← sin stop loss
/nuevacesta TechGrowth rsi 8        ← con stop loss al 8%
```

- El nombre puede tener varias palabras; la estrategia es siempre el penúltimo token (antes del % opcional).
- El stop loss es opcional. Se puede configurar después con `/estrategia`.
- Falla si ya existe una cesta activa con ese nombre.
- Estrategias válidas: `stop_loss`, `ma_crossover`, `rsi`, `bollinger`, `safe_haven`.
- La cesta se crea con €10.000 de cash inicial. Para añadir activos opera con `/compra`.

---

### `/eliminarcesta <nombre>`

Desactiva (soft-delete) una cesta. Solo el **OWNER** puede hacerlo, y únicamente si la cesta no tiene posiciones abiertas.

```
/eliminarcesta TechGrowth
→ ✅ Cesta "TechGrowth" desactivada.

/eliminarcesta Cesta Agresiva   ← con posiciones abiertas
→ ❌ No se puede eliminar: Cesta Agresiva tiene posiciones abiertas (AAPL, MSFT).
```

> La cesta desaparece de `/cestas` y deja de ser escaneada por las alertas automáticas. Los datos históricos se conservan.

---

### `/liquidarcesta <nombre>`

Vende todas las posiciones abiertas de una cesta al precio de mercado actual. Solo el **OWNER** puede ejecutarlo. El nombre de la cesta es obligatorio.

```
/liquidarcesta TechGrowth
```

**Ejemplo de salida:**
```
💰 Liquidación: TechGrowth

✅ AAPL: 10 × 185.32  (+5.2% vs entrada 176.20)
✅ MSFT: 5 × 420.10  (-1.3% vs entrada 425.70)
❌ NVDA: error obteniendo precio

💵 Cash recuperado: 3.953,70
```

- Si alguna venta falla (error de precio, etc.), el resto continúa igualmente.
- Una vez liquidada, la cesta queda con posiciones a cero y puede eliminarse con `/eliminarcesta`.

---

## Órdenes

> Las órdenes se ejecutan al precio de mercado actual (paper trading).
> **Requieren tener una cesta activa seleccionada** con `/sel`.

### `/sel [nombre_cesta]`

Selecciona la cesta sobre la que operarán `/compra` y `/vende`. Actúa como el "prompt" del bot: indica el contexto activo en todas las respuestas de órdenes.

```
/sel                    ← muestra la cesta actualmente seleccionada
/sel Cesta Agresiva     ← selecciona "Cesta Agresiva" como activa
```

La selección se guarda en base de datos y persiste entre reinicios del bot.

**Respuesta:**
```
🗂 Cesta activa: Cesta Agresiva
```

---

### `/compra <TICKER> <cantidad> [@cesta]`

Compra acciones usando la cesta activa. El argumento `@cesta` es un override puntual que no cambia la selección.

```
/compra AAPL 10                    ← usa cesta activa
/compra MSFT 5.5
/compra AAPL 10 @Cesta Agresiva    ← override sin cambiar /sel
```

**Respuesta:**
```
🗂 Cesta Agresiva
✅ Compra ejecutada
10 AAPL × 185.32 USD
Total: 1.853,20 USD
```

- La cantidad puede ser decimal.
- El bot descuenta el importe del cash de la cesta.
- Falla si no hay cash suficiente o no hay cesta seleccionada.

---

### `/vende <TICKER> <cantidad> [@cesta]`

Vende acciones de un activo usando la cesta activa (o override con `@cesta`).

```
/vende AAPL 5
/vende MSFT 2.5 @Cesta Agresiva
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

### `/sizing <TICKER> [STOP_LOSS [CAPITAL]]`

Calcula el número de acciones a comprar aplicando position sizing con gestión de riesgo. Usa el broker de la cesta que contiene el ticker y el **cash de la cesta activa** (`/sel`) como capital base.

```
/sizing SAN.MC              ← stop automático ATR(14)×2, capital de la cesta activa
/sizing SAN.MC 3.85         ← stop loss manual en €, capital de la cesta activa
/sizing AAPL                ← ticker USD, convierte automáticamente a EUR
/sizing AAPL 180            ← stop manual en USD
/sizing SAN.MC 3.85 8000    ← stop manual + capital explícito de €8.000
```

**Muestra:**
- Cesta activa y capital usado para el cálculo
- Precio actual y stop loss (manual o ATR×2, con volatilidad si es automático)
- Distancia al stop en € y %
- Número de acciones y factor limitante (riesgo o posición máxima)
- Posición nominal y % de cartera
- Comisiones del broker (compra + venta)
- Riesgo real incluyendo comisiones

**Parámetros de riesgo:** riesgo máximo 0,75% del capital · posición máxima 20% del capital

> El capital base es el `cash` de la cesta activa. Si no hay cesta activa, usa €20.000 como referencia. Si el ticker no está en ninguna cesta, usa el broker `paper` como fallback. No ejecuta ninguna orden — es solo una calculadora.

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

**Muestra un resumen agregado de la cartera y después el desglose por activo:**

- Rentabilidad media igual-ponderada vs. B&H y alpha (α)
- Ratio de Sharpe medio · Máximo drawdown (peor activo)
- Total de operaciones (suma de todos los activos)
- Por activo: rentabilidad, Sharpe, drawdown, operaciones y win rate

**Ejemplo de salida:**
```
📊 Backtest: Conservadora (1y)
   Estrategia: ma_crossover

CARTERA (3 activos)
  Rentabilidad: +12.1%  (B&H: +10.3%,  α: +1.8%)
  Sharpe: 0.89  |  Max DD: -11.4%
  Operaciones: 18

DESGLOSE
AAPL
  Rentabilidad: +18.4%  (B&H: +14.2%,  α: +4.2%)
  Sharpe: 1.34  |  Max DD: -8.6%
  Operaciones: 8  |  Win rate: 67%

MSFT
  Rentabilidad: +9.2%  (B&H: +8.1%,  α: +1.1%)
  Sharpe: 0.71  |  Max DD: -11.4%
  Operaciones: 6  |  Win rate: 50%
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
| `/sel [nombre]` | Ver o seleccionar cesta activa | Registrado |
| `/compra <TICKER> <qty> [@cesta]` | Comprar acciones | Registrado |
| `/vende <TICKER> <qty> [@cesta]` | Vender acciones | Registrado |
| `/analiza <TICKER>` | Análisis técnico (RSI, SMA) | Registrado |
| `/buscar <texto>` | Buscar tickers por nombre | Registrado |
| `/sizing <TICKER> [STOP [CAPITAL]]` | Position sizing con capital de la cesta activa | Registrado |
| `/backtest [período]` | Backtest de estrategias | Registrado |
| `/estrategia <cesta> [estrategia] [%]` | Ver o cambiar estrategia / stop loss | Registrado / OWNER |
| `/nuevacesta <nombre> <estrategia> [%]` | Crear nueva cesta (stop loss opcional) | Registrado |
| `/eliminarcesta <nombre>` | Desactivar cesta | OWNER |
| `/liquidarcesta <nombre>` | Vender todas las posiciones de una cesta | OWNER |
| `/register <id> <user>` | Pre-registrar usuario | OWNER |
| `/adduser <@user> <ROL> <cesta>` | Añadir usuario a cesta | OWNER |
| `/watchlist` | Ver watchlist personal | OWNER |
| `/addwatch <TICKER> [nombre\|nota]` | Añadir a watchlist | OWNER |
| `/logs [N]` | Registro de auditoría | OWNER |
