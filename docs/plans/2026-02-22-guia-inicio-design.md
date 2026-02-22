# Design: GUIA_INICIO.md — Crash Course de Inversión con TioGilito

**Fecha:** 2026-02-22
**Tipo:** Documentación de usuario (no requiere cambios de código)

---

## Objetivo

Crear una guía de inicio en español que enseñe simultáneamente a usar el bot y conceptos básicos de inversión, dirigida a usuarios con conocimiento cero de análisis técnico.

## Audiencia

Entre "cero absoluto" y "curioso sin experiencia": saben por qué invertir es útil pero no conocen ETFs, RSI, medias móviles ni estrategias.

## Formato

- Fichero: `GUIA_INICIO.md` en la raíz del repositorio
- Imágenes: `docs/img/guia/` — 8 capturas de pantalla reales
- Enlace desde `/help` (comando del bot)
- Longitud: ~2.500 palabras

## Enfoque: Híbrido narrativo + taller

Álvaro (personaje ligero) aparece en la intro y en momentos de duda/decisión. El cuerpo usa estructura de taller numerado con cajas `> 📚 Concepto` para el contenido educativo.

## Dos cestas de prueba

| Cesta | Activos | Estrategia | Filosofía |
|-------|---------|-----------|-----------|
| Mi Ahorro | IBE.MC, SAN.MC, GLD, MSFT | stop_loss | Preservar capital, activos estables |
| Mi Apuesta | NVDA, AAPL | rsi | Crecimiento/momentum, mayor volatilidad |

Esta dualidad permite que backtest y Monte Carlo cuenten una historia real: la defensiva pierde menos en caídas, la de crecimiento sube más en tendencias.

## Estructura de módulos

1. Intro — Álvaro y el problema de la inflación
2. Paso 0 — Registro
3. Módulo 1 — Cesta "Mi Ahorro" (stop_loss): buscar activos, /analiza, RSI
4. Módulo 2 — Cesta "Mi Apuesta" (rsi): riesgo/rentabilidad, /sizing
5. Módulo 3 — Backtest: Sharpe, drawdown, win rate
6. Módulo 4 — Monte Carlo: leer percentiles p10/p50/p90
7. Módulo 5 — Cestas modelo del sistema como benchmarks
8. Cierre — Liquidar posiciones, /eliminarcesta, crear cesta real

## Imágenes requeridas (8)

| Fichero | Qué capturar |
|---------|-------------|
| `docs/img/guia/alvaro.jpg` | Foto/avatar del personaje Álvaro |
| `docs/img/guia/start.png` | Respuesta del bot al /start |
| `docs/img/guia/buscar-ibe.png` | /buscar iberdrola — resultado IBE.MC |
| `docs/img/guia/analiza-ibe.png` | /analiza IBE.MC — con RSI y SMAs |
| `docs/img/guia/analiza-nvda.png` | /analiza NVDA — contraste de volatilidad |
| `docs/img/guia/cartera.png` | /cartera con posiciones de ambas cestas |
| `docs/img/guia/backtest.png` | /backtest 1y — resultados comparados |
| `docs/img/guia/montecarlo.png` | /montecarlo Mi Apuesta — distribución |
