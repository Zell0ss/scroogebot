from __future__ import annotations
from dataclasses import dataclass


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
    capital_total: float
    aviso:         str | None
