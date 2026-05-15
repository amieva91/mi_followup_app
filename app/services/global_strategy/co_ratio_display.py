"""Porcentajes de inversión (IR) y liquidez (efectivo bróker) vs Capital Operativo (CO)."""
from __future__ import annotations


def pct_of_co(part_eur: float, co: float) -> float | None:
    """Porcentaje de una parte del bróker respecto al CO (= total bróker: efectivo + posiciones)."""
    if co <= 0:
        return None
    return 100.0 * float(part_eur) / float(co)


def format_pct_for_message(pct: float | None) -> str:
    if pct is None:
        return "—"
    try:
        return f"{float(pct):.1f} %"
    except (TypeError, ValueError):
        return "—"


def investment_and_liquidity_pct(co: float, ir: float) -> tuple[float | None, float | None]:
    """IR = valor mercado posiciones; liquidez = efectivo bróker (CO − IR)."""
    inv = pct_of_co(ir, co)
    liq = pct_of_co(co - ir, co)
    return inv, liq
