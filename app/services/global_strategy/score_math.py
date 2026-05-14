"""
Cálculos puros del motor de estrategia global (sin I/O).

Ver docs/implementaciones/global_strategy_engine.md.
"""
from __future__ import annotations

# Nodos (SG, RO) para interpolación lineal a tramos
_RO_NODES: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (0.5, 0.6),
    (1.0, 0.8),
    (2.0, 1.3),
    (3.0, 2.0),
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def score_usa_yield_curve_spread_pct(x: float) -> float:
    """
    x = (10Y − 2Y) en puntos porcentuales (p. ej. 0.35 = +0,35 %).
    """
    x = float(x)
    if x >= 0.5:
        return 1.0
    if x <= -0.5:
        return 0.0
    return _clamp((x + 0.5) / 1.0, 0.0, 1.0)


def score_eu_vstoxx_vs_ma200(v: float, v_ma200: float) -> float:
    """v = V2TX actual; v_ma200 = media móvil 200 sesiones."""
    v = float(v)
    m = float(v_ma200)
    if m <= 0:
        return 0.0
    low, high = 0.8 * m, 1.5 * m
    if v <= low:
        return 1.0
    if v >= high:
        return 0.0
    span = high - low
    if span <= 0:
        return 0.0
    return _clamp(1.0 - (v - low) / span, 0.0, 1.0)


def score_asia_price_vs_ma200(price: float, ma200: float) -> float:
    """Modo Asia por defecto: precio vs MA200 (3188.HK)."""
    p = float(price)
    m = float(ma200)
    if m <= 0:
        return 0.0
    lo, hi = 0.95 * m, 1.05 * m
    if p >= hi:
        return 1.0
    if p <= lo:
        return 0.0
    span = hi - lo
    if span <= 0:
        return 0.0
    return _clamp((p - lo) / span, 0.0, 1.0)


def score_global(s_us: float, s_eu: float, s_as: float) -> float:
    return _clamp(float(s_us) + float(s_eu) + float(s_as), 0.0, 3.0)


def ratio_objetivo(sg: float) -> float:
    """
    RO(SG) con interpolación lineal entre nodos; SG fuera de [0,3] se satura.
    """
    sg = _clamp(float(sg), 0.0, 3.0)
    nodes = _RO_NODES
    for i in range(len(nodes) - 1):
        sg0, ro0 = nodes[i]
        sg1, ro1 = nodes[i + 1]
        if sg0 <= sg <= sg1:
            if sg1 <= sg0:
                return ro1
            return ro0 + (sg - sg0) * (ro1 - ro0) / (sg1 - sg0)
    return nodes[-1][1]


def umbral_objetivo_mercado(co: float, sg: float) -> float:
    """UOM = CO × RO(SG)."""
    return float(co) * ratio_objetivo(sg)
