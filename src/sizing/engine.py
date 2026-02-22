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
    capital_total: float = CAPITAL_TOTAL,
) -> SizingResult:
    # 1. Price (convert to EUR if needed)
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

    if distancia <= 0:
        return SizingResult(
            ticker=ticker,
            company_name=ticker,
            precio=precio,
            currency=currency,
            stop_loss=stop_loss,
            stop_tipo=stop_tipo,
            atr=atr_val,
            distancia=distancia,
            distancia_pct=distancia_pct,
            acciones=0,
            factor_limite="riesgo",
            nominal=0.0,
            pct_cartera=0.0,
            riesgo_maximo=CAPITAL_TOTAL * RIESGO_MAX_PCT,
            riesgo_real=0.0,
            com_compra=0.0,
            com_venta=0.0,
            broker_nombre=broker.name,
            capital_total=capital_total,
            aviso="❌ Stop loss debe ser inferior al precio actual",
        )

    # 3. Sizing
    riesgo_max = capital_total * RIESGO_MAX_PCT
    posicion_max = capital_total * POSICION_MAX_PCT

    has_pct = broker.commissions.comision_pct > 0

    if not has_pct:
        # Fixed commissions — no circular dependency
        com_c_fixed = broker.commissions.calcular(0)  # fixed fee same for any nominal
        com_v_fixed = broker.commissions.calcular(0)
        riesgo_disp = max(0.0, riesgo_max - com_c_fixed - com_v_fixed)
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
    aviso_parts = []
    if distancia_pct > STOP_ALEJADO_UMBRAL * 100:
        aviso_parts.append(f"Stop muy alejado ({distancia_pct:.1f}%), considera usar ATR automatico")
    if currency != "EUR":
        aviso_parts.append(f"Precio convertido desde {currency} (x{fx:.4f})")
    if acciones == 0:
        aviso_parts.append("Riesgo insuficiente para esta distancia de stop")
    aviso = "\n".join(aviso_parts) if aviso_parts else None

    return SizingResult(
        ticker=ticker,
        company_name=ticker,
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
        pct_cartera=(nominal / capital_total * 100) if acciones > 0 else 0.0,
        riesgo_maximo=riesgo_max,
        riesgo_real=riesgo_real if acciones > 0 else 0.0,
        com_compra=com_compra,
        com_venta=com_venta,
        broker_nombre=broker.name,
        capital_total=capital_total,
        aviso=aviso,
    )
