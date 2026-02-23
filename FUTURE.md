# FUTURE — ScroogeBot notes and known issues

Ideas, improvement notes, and known bugs to fix eventually.

---

## Known bugs

### `/eliminarcesta` — `p.ticker` en Position no existe

`src/bot/handlers/admin.py`, función `cmd_eliminarcesta`, en el bloque de posiciones abiertas:

```python
tickers = ", ".join(p.ticker for p in open_positions)
```

`Position` no tiene campo `ticker` — solo `asset_id`. Este código nunca se ejecuta en la práctica
porque el comando bloquea antes de llegar ahí (la cesta con posiciones abiertas no se puede eliminar),
pero si algún día se refactoriza hay que cambiarlo a un join con `Asset`.

Fix: cambiar la query a `select(Position, Asset).join(Asset, ...)` y usar `asset.ticker`.

---

## Observability roadmap

## What is implemented today

`src/metrics.py` starts a Prometheus-compatible HTTP server (port 9090 by default)
when the bot launches. Five metrics are exposed:

| Metric | Type | Labels | What it measures |
|---|---|---|---|
| `scroogebot_alert_scans_total` | Counter | `result` | Scan runs: `completed` vs `skipped_closed` |
| `scroogebot_alerts_generated_total` | Counter | `strategy`, `signal` | Alerts fired per strategy (BUY/SELL) |
| `scroogebot_scan_duration_seconds` | Histogram | — | Wall-clock time for a full scan run |
| `scroogebot_market_open` | Gauge | `market` | 1 = open, 0 = closed (updated every tick) |
| `scroogebot_commands_total` | Counter | `command`, `success` | Write-commands executed via Telegram |

**Verify it works** (while the bot is running):

```bash
curl http://localhost:9090/metrics | grep scroogebot
```

Example output:

```
scroogebot_alert_scans_total{result="completed"} 12.0
scroogebot_alert_scans_total{result="skipped_closed"} 48.0
scroogebot_alerts_generated_total{signal="BUY",strategy="rsi"} 2.0
scroogebot_scan_duration_seconds_sum 4.37
scroogebot_market_open{market="NYSE"} 1.0
scroogebot_market_open{market="IBEX"} 0.0
scroogebot_market_open{market="LSE"} 1.0
scroogebot_commands_total{command="/compra",success="true"} 3.0
```

---

## Near-term: quick wins

### 1. `/estado` Telegram command

A read-only command that pulls the current metric values directly from the
running counters — no Prometheus server needed:

```
/estado

📊 ScroogeBot — estado actual

🔄 Escaneos: 60 completados · 240 omitidos (mercados cerrados)
⚠️  Alertas generadas hoy: 4 (rsi·BUY x2, safe_haven·SELL x2)
⏱️  Último escaneo: 0.34 s
🟢 NYSE: abierto · 🔴 IBEX: cerrado · 🟢 LSE: abierto
📋 Comandos hoy: /compra x3 · /vende x1 · /backtest x2
```

Implementation: read from prometheus_client's internal registry via
`REGISTRY.get_sample_value()` — no HTTP round-trip needed.

---

### 2. Additional metrics worth adding

| Metric | Type | Rationale |
|---|---|---|
| `scroogebot_positions_total` | Gauge | Active positions per basket (snapshot on each scan) |
| `scroogebot_portfolio_value_eur` | Gauge | Total portfolio in EUR per basket |
| `scroogebot_yfinance_errors_total` | Counter | Track data-provider failures |
| `scroogebot_scan_assets_evaluated` | Counter | Assets checked per scan run |

---

## Medium-term: Prometheus + Grafana stack

To get time-series charts, set up a local scrape stack with Docker Compose.

### `docker-compose.monitoring.yml`

```yaml
version: "3.8"
services:
  prometheus:
    image: prom/prometheus:latest
    ports: ["9091:9090"]
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - grafana_data:/var/lib/grafana
    restart: unless-stopped

volumes:
  grafana_data:
```

### `config/prometheus.yml`

```yaml
global:
  scrape_interval: 60s

scrape_configs:
  - job_name: scroogebot
    static_configs:
      - targets: ["host.docker.internal:9090"]  # or your server IP
```

Start: `docker compose -f docker-compose.monitoring.yml up -d`
Grafana: `http://localhost:3000` (admin / admin)

### Useful Grafana panels

- **Scan throughput**: `rate(scroogebot_alert_scans_total[1h])`
- **Market uptime ratio**: `scroogebot_market_open{market="NYSE"}`
- **Alerts per strategy**: `increase(scroogebot_alerts_generated_total[24h])`
- **Average scan duration**: `scroogebot_scan_duration_seconds_sum / scroogebot_scan_duration_seconds_count`
- **Command usage**: `increase(scroogebot_commands_total[24h])`

---

## Medium-term: Alertmanager rules

If the bot goes silent, Alertmanager can page you. Example rule:

```yaml
# config/alert_rules.yml
groups:
  - name: scroogebot
    rules:
      - alert: BotNotScanning
        expr: increase(scroogebot_alert_scans_total[15m]) == 0
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "ScroogeBot has not run a scan in 15 minutes"

      - alert: HighYfinanceErrors
        expr: increase(scroogebot_yfinance_errors_total[1h]) > 10
        labels:
          severity: warning
        annotations:
          summary: "More than 10 yfinance errors in the last hour"
```

---

## Backtest commission-aware

Una vez implementado el módulo `src/sizing/` con `CommissionStructure` y el `BROKER_REGISTRY`,
conectar las comisiones reales al backtest es pasar un parámetro adicional a vectorbt:

```python
# src/backtest/engine.py — mejora futura
pf = vbt.Portfolio.from_signals(
    close, entries, exits,
    init_cash=10_000,
    fees=broker.commissions.comision_pct / 100,   # porcentual
    fixed_fees=broker.commissions.comision_fija,   # fijo por operación
    freq="1D",
)
```

El backtest ya conoce la cesta (`basket`); con el campo `basket.broker` podrá
recuperar el broker del `BROKER_REGISTRY` y aplicar sus comisiones exactas.
Esto hará los backtests significativamente más realistas, especialmente para
estrategias con muchas operaciones.

---

## Gestión de cestas desactivadas

Las cestas eliminadas con `/eliminarcesta` se marcan `active=False` y su nombre
queda renombrado a `{nombre}#{id_hex}` (ej. `Mi_Ahorro_jmc#b`) para liberar el
nombre original. Los registros permanecen en la BD con todo su historial de
órdenes intacto.

Ideas para un futuro panel de administración:

- **`/cestas_archivadas`** — listar cestas con `active=False` (solo OWNER global).
- **Borrado definitivo** — eliminar físicamente una cesta archivada y en cascada
  sus órdenes, posiciones, alertas y membresías. Requiere confirmación de doble
  paso para evitar accidentes.
- **Restaurar cesta** — reactivar una cesta archivada (deshacer el renombrado y
  volver a poner `active=True`), útil si el usuario se arrepiente.
- **Métricas de archivo** — exponer en Prometheus el número de cestas activas vs
  archivadas.

---

## Backtest: separar warmup del periodo de evaluación

Actualmente `BacktestEngine` usa un warmup fijo de 60 barras dentro del periodo
solicitado (e.g., `/backtest 1y` evalúa solo ~9 meses). La solución es pedir
datos extra al proveedor para que el warmup no consuma el periodo del usuario:

```python
# En engine.run():
ohlcv = data.get_historical(ticker, period=_extend_period(period, warmup=60), ...)
# Recortar los primeros `warmup` bars para los cálculos de rentabilidad
eval_start = close.index[window]
```

Aplica también a `MonteCarloEngine` (usa `HIST_PERIOD = "2y"`, afecta menos).
La función `_extend_period("1y", warmup=60)` necesitaría mapearse a `"15mo"` o
similar, o usar fechas explícitas con `yfinance.download(start=..., end=...)`.

---

## Long-term ideas

- **Portfolio value chart**: log `scroogebot_portfolio_value_eur` every scan;
  plot it in Grafana as an equity curve over weeks/months.
- **Strategy performance**: cross-reference `alerts_generated_total` with
  DB order outcomes → signal quality over time.
- **Backtest metrics**: expose backtest Sharpe / max-drawdown as gauges when
  `/backtest` is called, so they appear in Grafana.
- **Structured logging to Loki**: replace rotating file `scroogebot.log` with
  Grafana Loki for log aggregation alongside metrics in the same dashboard.

---

*Last updated: 2026-02-21*
