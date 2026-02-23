# Guía Avanzada: Cuaderno de Laboratorio

*Aprende a leer el backtest y el Monte Carlo desde los datos reales*

---

## Antes de empezar

Esta guía asume que ya sabes moverte por el bot — crear cestas, comprar activos, ejecutar un `/backtest`. Si no es así, empieza por la Guía de Inicio.

Aquí no hay personaje que aprende. Aquí eres tú el experimentador.

El objetivo no es memorizar definiciones. Es que, al acabar, seas capaz de mirar un backtest y un Monte Carlo y saber exactamente qué preguntas hacerte — y cuáles no puedes responder con esos datos.

**Lo que necesitas**: papel y lápiz. Habrá momentos en que te pida que escribas algo antes de seguir leyendo.

---

## La cartera de laboratorio

Para todos los experimentos usamos la misma cartera: cinco activos con perfiles deliberadamente distintos.

```
/nuevacesta Lab_Avanzado rsi
/sel Lab_Avanzado
/compra NVDA 1
/compra MSFT 1
/compra IBE.MC 1
/compra GLD 1
/compra SAN.MC 1
```

| Activo | Tipo | Perfil |
|---|---|---|
| NVDA | Tecnología americana | Alta volatilidad, tendencia alcista fuerte |
| MSFT | Tecnología americana | Volatilidad media, año complicado |
| IBE.MC | Utility española | Baja volatilidad, tendencia alcista suave |
| GLD | ETF oro | Baja volatilidad, tendencia alcista sostenida |
| SAN.MC | Banca española | Volatilidad media-alta, año espectacular |

Cinco caracteres distintos. Cinco comportamientos distintos ante las mismas estrategias.

---

## Experimento 1 — El win rate miente (a veces)

### Los datos

Ejecuta:
```
/estrategia Lab_Avanzado rsi
/backtest 1y
```

Apunta esta tabla en el papel:

| | IBE.MC | SAN.MC |
|---|---|---|
| Rentabilidad estrategia | +25.2% | +54.3% |
| B&H | +50.0% | +89.1% |
| Alpha (α) | -24.8% | -34.7% |
| Win rate | 100% | 67% |
| Operaciones | 8 | 13 |

### La paradoja

Antes de seguir, hazte esta pregunta y apunta tu respuesta:

> IBE.MC ganó el 100% de sus operaciones.
> SAN.MC ganó solo el 67%.
> Sin embargo RSI ganó más dinero con SAN (+54%) que con IBE (+25%).
> ¿Cómo es posible?

---

La respuesta está en el B&H.

Santander tuvo un año espectacular: **+89%**. Iberdrola tuvo un buen año: **+50%**. No es lo mismo.

Ahora mira cuánto capturó RSI de cada uno:

> IBE: 25 / 50 = **50%** del movimiento real
> SAN: 54 / 89 = **61%** del movimiento real

RSI capturó porcentualmente más de Santander que de Iberdrola. Pero con IBE acertó el 100% de sus operaciones. ¿Por qué?

Santander subió +89% ese año de forma explosiva. Cada vez que llegaba a RSI>70 — "sobrecomprado, vende" — la estrategia vendía. Y Santander seguía subiendo. Y volvía a RSI>70. Y volvía a vender. 13 operaciones en un año. Cada venta "correcta" según el indicador... y cada vez que vendía, Santander seguía subiendo sin él.

Con Iberdrola fue diferente: subida más suave, RSI llegó a extremos 8 veces, acertó siempre, pero cada movimiento capturado fue pequeño.

Esto tiene nombre: **coste de oportunidad**. Lo que dejaste de ganar por salir demasiado pronto.

En tendencias bajistas sostenidas ocurre lo opuesto: RSI compra "en mínimos" que resultan no ser mínimos. Compra, cae más, compra de nuevo, cae más. Intentar coger el fondo de una caída tiene un nombre en el mercado: **agarrar un cuchillo que cae**.

> **Nota sobre el win rate**: una operación se cuenta como *win* si el precio de venta es mayor que el precio de compra. RSI compró Santander a 80, vendió a 95 — win. Que luego Santander fuera a 140 es irrelevante para el contador. El win rate no sabe nada del futuro de la operación después de que cerraste.

### Conclusión 1

> El win rate mide que la operación cerró ganando.
> No mide el coste de oportunidad de haber salido demasiado pronto.
> Solo tiene sentido leído junto al alpha.

---

## Experimento 2 — El mismo activo, dos estrategias, resultados opuestos

### Los datos

Ejecuta:
```
/estrategia Lab_Avanzado rsi
/backtest 1y
```
y luego:
```
/estrategia Lab_Avanzado ma_crossover
/backtest 1y
```

Apunta esta tabla para NVDA:

| | RSI | MA Crossover |
|---|---|---|
| Rentabilidad | +34.6% | +0.2% |
| B&H | +47.1% | +47.1% |
| Alpha (α) | -12.4% | -46.9% |
| Operaciones | 11 | 2 |
| Win rate | 90% | 0% |
| Max DD | -19.2% | -19.5% |

Mismo activo. Mismo año. **34 puntos de diferencia**.

### Por qué MA Crossover falló con NVDA

MA Crossover es lento por diseño: espera a que la media de 20 días cruce la de 50 días. Cuando el cruce se confirma, el movimiento lleva días ocurriendo.

NVDA tuvo caídas profundas ese año... seguidas de recuperaciones fuertes. Cada caída fue suficiente para que las medias se cruzaran a la baja — señal de venta. Luego la recuperación cruzó de nuevo al alza — señal de compra. Y cada vez que reaccionó, llegó tarde. Entró tarde. Salió tarde. En ambas direcciones.

Eso se llama **whipsaw** — el serrucho. La estrategia te corta de ida y de vuelta.

### Por qué MA Crossover funcionó con GLD y SAN

| Activo | MA Crossover | Max DD |
|---|---|---|
| NVDA | +0.2% | -19.5% |
| GLD | +53.2% | -13.9% |
| SAN.MC | +57.2% | -9.5% |

GLD y SAN tuvieron un año de subida más **continua y sostenida**, sin grandes hoyos intermedios. La media rápida se puso por encima de la lenta... y se quedó ahí. MA Crossover entró una vez y se quedó quieto mientras el activo subía. No necesitó reaccionar porque no hubo falsas alarmas.

### La regla del carácter del activo

| Estrategia | Funciona mejor cuando... |
|---|---|
| RSI | El activo es volátil y oscila entre extremos |
| MA Crossover | El activo tiene tendencias limpias y sostenidas sin mucho ruido |

> NVDA ese año fue volátil con tendencia alcista. RSI aprovechó la volatilidad.
> MA Crossover se atragantó con ella.

### Conclusión 2

> Una estrategia no es buena o mala en abstracto.
> Es buena o mala para ese activo, en ese tipo de mercado.
> Elegir estrategia sin mirar el carácter del activo es como poner neumáticos de lluvia en un circuito seco.

---

## Experimento 3 — El portfolio que miente

### Los datos

MA Crossover, desglose completo (backtest corregido):

| Activo | Rentabilidad | B&H | Alpha |
|---|---|---|---|
| NVDA | +0.2% | +47.1% | -46.9% |
| MSFT | -8.7% | -4.1% | -4.6% |
| IBE.MC | +15.7% | +50.0% | -34.3% |
| GLD | +53.2% | +76.8% | -23.7% |
| SAN.MC | +57.2% | +89.1% | -31.9% |
| **CARTERA** | **+23.5%** | **+51.8%** | **-28.3%** |

### Lo que el titular oculta

El número de portfolio es +23.5%. Ese número es correcto. Y es completamente engañoso si te quedas solo con él.

Lo que oculta:
- **2 activos en negativo** (NVDA, MSFT)
- **Ningún activo bate a su propio B&H**
- SAN y GLD arrastran todo el resultado

Leer el titular sin el desglose es como ver la nota media de un examen sin saber que la mitad de los alumnos suspendió.

### Por qué el portfolio puede batir al B&H agregado aunque ningún activo lo haga

Cuando MA Crossover está fuera de un activo, ese capital está en **cash**. Cash no pierde.

B&H siempre está invertido. Si NVDA cae un 20% en un tramo, B&H sufre ese -20%. MA Crossover, si vendió antes, no lo sufre — está aparcado. Ese capital preservado eleva el resultado de portfolio por encima de lo que haría el B&H en ese mismo período.

> B&H se lleva todos los golpes.
> La estrategia a veces esquiva los golpes quedándose en cash.
> Si esquiva suficientes golpes, el portfolio puede ganar al B&H agregado aunque pierda activo a activo.

> **Nota técnica**: el número de portfolio no es la media aritmética de los activos. Depende de cuánto capital había en cada activo en cada momento y cuándo. No puedes derivar los individuales del portfolio ni al revés.

### Conclusión 3

> El titular de portfolio puede ser correcto y completamente engañoso al mismo tiempo.
> Lee siempre el desglose antes que el titular.
> Un portfolio con +23% puede tener 2 de 5 activos perdiendo dinero.

---

## Experimento 4 — Backtest y Monte Carlo: dos preguntas distintas

### Los datos

Ejecuta:
```
/estrategia Lab_Avanzado rsi
/montecarlo Lab_Avanzado
```

Apunta estos dos bloques uno al lado del otro:

**IBE.MC con RSI — Backtest (1 año pasado)**
```
Rentabilidad: +25.2%
Win rate:     100%
Operaciones:  8
Max DD:       -7.1%
```

**IBE.MC con RSI — Monte Carlo (90 días futuros)**
```
Mediana:        0.0%
Rango 80%:      0.0% a +1.9%
Peor caso 5%:   0.0%
Prob. pérdida:  4%
```

### ¿Se contradicen?

No. Responden preguntas distintas.

> **Backtest pregunta**: ¿qué habría pasado si hubieras aplicado esta estrategia el año pasado?
>
> **Monte Carlo pregunta**: dado cómo se ha comportado este activo históricamente, ¿qué distribución de resultados puedes esperar en los próximos 90 días?

Son máquinas del tiempo en direcciones opuestas. Una mira atrás. La otra mira adelante.

### Por qué la mediana es 0% cuando el backtest dice +25%

RSI solo actúa cuando el indicador llega a extremos: RSI<30 para comprar, RSI>70 para vender.

IBE.MC es Iberdrola — utility española, ATR del 0.6%, baja volatilidad. En la mayoría de los 100 escenarios simulados de 90 días, Iberdrola simplemente **no llegó a esos extremos**. La estrategia no tuvo nada que hacer. El capital estuvo en cash. Retorno: 0%.

El backtest trabajó con 365 días y tuvo 8 oportunidades de actuar. El Monte Carlo trabaja con 90 días y en la mayoría de simulaciones encuentra 0 oportunidades. No es que la estrategia funcione mal — es que no tiene ocasión de actuar.

### El rango 80% como radiografía de volatilidad

Compara los tres activos con RSI en Monte Carlo:

| | Rango 80% |
|---|---|
| IBE.MC | 0.0% a +1.9% |
| SAN.MC | 0.0% a +2.0% |
| NVDA | -1.9% a +27.6% |

IBE y SAN: rango estrecho. Activos que no se mueven mucho, y cuando RSI actúa los movimientos son contenidos.

NVDA: rango asimétrico y amplio. Lado bajista pequeño (-1.9%), lado alcista enorme (+27.6%). Cuando RSI captura un movimiento en NVDA, históricamente ha sido más frecuentemente alcista que bajista — y cuando ocurre, el ATR de 3-4% diario hace que el movimiento sea grande.

> Un rango 80% estrecho = activo tranquilo o estrategia que rara vez actúa.
> Un rango 80% amplio y asimétrico = activo volátil con sesgo direccional.

Es información que el backtest no te da directamente — el backtest te dice qué pasó, no la forma de la distribución de posibles futuros.

### Para qué sirve cada herramienta

| | Backtest | Monte Carlo |
|---|---|---|
| Pregunta | ¿Qué habría pasado? | ¿Qué puede pasar? |
| Horizonte | Pasado conocido | Futuros posibles |
| Útil para | Descartar estrategias malas | Entender el rango de resultados |
| No sirve para | Predecir el futuro | Garantizar rentabilidad |

Usados juntos, te dan algo más valioso que cualquiera por separado: **saber qué preguntas hacerte antes de invertir dinero real**.

### Conclusión 4

> Backtest y Monte Carlo no se contradicen — responden preguntas distintas.
> Uno mira atrás. El otro pinta la distribución de lo que puede pasar.
> Ninguno predice el futuro. Juntos, te ayudan a entender el riesgo que estás asumiendo.

---

## Bonus — Cuando ninguna estrategia te salva

### Los datos

MSFT, todo junto:

| | RSI | MA Crossover | B&H |
|---|---|---|---|
| Rentabilidad | -19.2% | -8.7% | -4.1% |
| Alpha | -15.1% | -4.6% | — |
| Max DD | -21.7% | -11.6% | — |
| Operaciones | 1 | 1 | 0 |
| Win rate | 0% | 0% | — |

### Lo que pasó

MSFT cayó ese año de forma sostenida.

Con RSI: el indicador llegó a <30 — "sobrevendido, oportunidad de compra". RSI compró. MSFT siguió cayendo. RSI nunca llegó a >70 porque el precio nunca se recuperó suficiente. La posición se quedó abierta, perdiendo, hasta el final del año. Una operación. 0% win rate. -19.2%.

Con MA Crossover: entró tarde (el cruce tardó en confirmarse), salió tarde. Una operación. -8.7%.

B&H simplemente aguantó la caída: -4.1%.

**Las dos estrategias perdieron más que no hacer nada.**

### Por qué RSI no vendió cuando caía

RSI **no vende cuando el activo cae** — eso es el stop loss, no RSI. RSI solo vende cuando el activo está sobrecomprado (RSI>70). En una caída sostenida, RSI nunca llega a ese nivel — así que no genera señal de salida. La posición queda abierta mientras el activo sigue bajando.

### La conclusión incómoda

> Ninguna estrategia puede convertir un mal año de un activo en un buen resultado.
> La mejor estrategia en un año malo es la que **pierde menos** — no la que gana.
> Y ningún indicador técnico te dice con certeza cuándo viene ese mal año.

La diferencia entre perder -19% y perder -4% con MSFT no es trivial. Pero tampoco nadie sabía antes del año que MSFT iba a tener ese comportamiento. El análisis técnico trabaja con probabilidades y patrones — no con certezas.

---

## Las cinco conclusiones

**1 — El win rate**
El win rate mide que la operación cerró ganando. No mide el coste de oportunidad de haber salido demasiado pronto. Solo tiene sentido leído junto al alpha.

**2 — Estrategia y activo**
Una estrategia no es buena o mala en abstracto. Es buena o mala para ese activo, en ese tipo de mercado. RSI en activos volátiles que oscilan. MA Crossover en activos con tendencias limpias y sostenidas.

**3 — El titular de portfolio**
El titular de portfolio puede ser correcto y completamente engañoso al mismo tiempo. Lee siempre el desglose — ahí está la verdad. Un portfolio con +23% puede tener 2 de 5 activos perdiendo dinero.

**4 — Backtest vs Monte Carlo**
Backtest y Monte Carlo no se contradicen — responden preguntas distintas. Uno mira atrás. El otro pinta la distribución de lo que puede pasar, incluyendo si puedes sobrevivir el peor caso. Ninguno predice el futuro.

**5 — El límite de las estrategias**
Ninguna estrategia convierte un mal año en un buen resultado. Con un activo que cae, el objetivo es perder menos — no ganar. Y ningún indicador técnico te avisa con certeza antes de que ocurra.

---

## ¿Y ahora qué?

Los dos análisis que siguen a esta guía:

**Guía 3 — Iterar la cartera**: dado un conjunto de activos y una estrategia elegida, ¿cómo identificar qué activos no encajan y cómo encontrar sustitutos? ¿Cómo iterar backtest + Monte Carlo para mejorar la cartera de forma sistemática?

**Guía 4 — Fondos indexados**: en España, los fondos indexados tienen ventaja fiscal sobre acciones directas (no tributan hasta el reembolso). ¿Cómo encontrar el fondo indexado que mejor representa una cartera de activos y repetir este mismo estudio con ellos?

---

*Basada en datos reales del bot — backtests y simulaciones Monte Carlo ejecutados en febrero 2026*
*Cartera: NVDA, MSFT, IBE.MC, GLD, SAN.MC | Estrategias: RSI y MA Crossover | Período: 1 año*