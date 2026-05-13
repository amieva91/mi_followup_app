"""
Valoración modo ``banks``: P/B, BVPS, ROE, CET1 y ajuste F_bank.

Referencias: docs/implementaciones/WATCHLIST_VALORACION_PLAN_IMPLEMENTACION.md §13.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from app.models.watchlist import Watchlist


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def bvps_ref(wl: Watchlist) -> Optional[float]:
    if wl.bvps is not None and wl.bvps > 0:
        return wl.bvps
    p0 = wl.precio_actual
    pb = wl.price_to_book
    if p0 is not None and pb is not None and pb > 0:
        return p0 / pb
    return None


def bank_fair_price(wl: Watchlist, bvps_r: Optional[float]) -> Optional[float]:
    """P_fair = BVPS × P/B fair; si no hay BVPS explícito: P0 × (P/B_fair / P/B0)."""
    pbf = wl.pb_fair
    if pbf is None or pbf <= 0:
        return None
    if bvps_r is not None and bvps_r > 0:
        return bvps_r * pbf
    p0 = wl.precio_actual
    pb0 = wl.price_to_book
    if p0 is not None and pb0 is not None and pb0 > 0:
        return p0 * (pbf / pb0)
    return None


def bank_valoracion_12m(wl: Watchlist) -> Optional[float]:
    p0 = wl.precio_actual
    if p0 is None or p0 <= 0:
        return None
    bv = bvps_ref(wl)
    p_fair = bank_fair_price(wl, bv)
    if p_fair is None or p_fair <= 0:
        return None
    return round((p_fair / p0 - 1.0) * 100.0, 2)


def bank_growth_bvps_pct(wl: Watchlist) -> Optional[float]:
    if wl.bvps_cagr_yoy is not None:
        return _clamp(wl.bvps_cagr_yoy, -5.0, 12.0)
    if wl.roe_pct is None:
        return None
    payout = 0.0
    if (
        wl.eps is not None
        and wl.eps > 0
        and wl.per_ntm is not None
        and wl.per_ntm > 0
        and wl.ntm_dividend_yield is not None
    ):
        payout = (wl.ntm_dividend_yield / 100.0) * wl.per_ntm
    payout = max(0.0, min(1.0, payout))
    if wl.eps is not None and wl.eps > 0:
        g = wl.roe_pct * (1.0 - payout)
    else:
        g = wl.roe_pct * 0.55
    return _clamp(g, -5.0, 12.0)


def pb_terminal(wl: Watchlist) -> Optional[float]:
    if wl.pb_fair is not None and wl.pb_fair > 0:
        return wl.pb_fair
    if wl.price_to_book is not None and wl.price_to_book > 0:
        return wl.price_to_book
    return None


def bank_target_5y_bruto(wl: Watchlist) -> Optional[float]:
    bv = bvps_ref(wl)
    pb_t = pb_terminal(wl)
    g = bank_growth_bvps_pct(wl)
    if bv is None or pb_t is None or g is None:
        return None
    if bv <= 0 or pb_t <= 0:
        return None
    gd = g / 100.0
    return bv * ((1.0 + gd) ** 5) * pb_t


def factor_cet1(pct: Optional[float]) -> float:
    if pct is None:
        return 1.0
    if pct >= 14.0:
        return 1.0
    if pct >= 12.0:
        return 0.98
    if pct >= 10.0:
        return 0.93
    return 0.86


def factor_cost_to_income(pct: Optional[float]) -> float:
    if pct is None:
        return 1.0
    if pct <= 40.0:
        return 1.02
    if pct <= 55.0:
        return 1.0
    if pct <= 70.0:
        return 0.96
    return 0.90


def factor_nim(pct: Optional[float]) -> float:
    if pct is None:
        return 1.0
    if pct >= 5.5:
        return 1.0
    if pct >= 4.0:
        return 0.98
    if pct >= 3.0:
        return 0.94
    return 0.88


def factor_npl(pct: Optional[float]) -> float:
    if pct is None:
        return 1.0
    if pct <= 3.0:
        return 1.02
    if pct <= 5.0:
        return 1.0
    if pct <= 8.0:
        return 0.96
    if pct <= 12.0:
        return 0.90
    return 0.84


def factor_cost_of_risk(pct: Optional[float]) -> float:
    if pct is None:
        return 1.0
    if pct <= 1.0:
        return 1.0
    if pct <= 2.0:
        return 0.97
    if pct <= 3.5:
        return 0.92
    return 0.85


def factor_ldr(pct: Optional[float]) -> float:
    if pct is None:
        return 1.0
    if pct <= 85.0:
        return 1.0
    if pct <= 95.0:
        return 0.99
    if pct <= 105.0:
        return 0.94
    return 0.88


def bank_f_asset(wl: Watchlist) -> float:
    fn = factor_npl(wl.npl_ratio_pct)
    fc = factor_cost_of_risk(wl.cost_of_risk_pct)
    if wl.npl_ratio_pct is None and wl.cost_of_risk_pct is None:
        return 1.0
    return math.sqrt(fn * fc)


def compute_f_bank_final(wl: Watchlist) -> float:
    f = (
        factor_cet1(wl.cet1_ratio_pct)
        * factor_cost_to_income(wl.cost_to_income_pct)
        * factor_nim(wl.nim_pct)
        * bank_f_asset(wl)
        * factor_ldr(wl.loan_to_deposit_pct)
    )
    return min(1.06, max(0.72, f))


def bank_core_price_pb_ok(wl: Watchlist) -> bool:
    if wl.precio_actual is None or wl.precio_actual <= 0:
        return False
    if wl.price_to_book is None or wl.price_to_book <= 0:
        return False
    return True


def bank_valuation_pipeline(
    wl: Watchlist,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Retorna (valoracion_12m, target_bruto, f_bank_final, target_adj).

    Sin P/B fair no hay valoración 12m (fair explícita). Target 5y requiere
    BVPS (explícito o vía P/PB), múltiplo terminal y crecimiento BVPS (CAGR o
    proxy ROE × retención cuando aplica).
    """
    if not bank_core_price_pb_ok(wl):
        return None, None, None, None

    v12 = bank_valoracion_12m(wl)
    bruto = bank_target_5y_bruto(wl)
    if bruto is None:
        return v12, None, None, None
    f_fin = compute_f_bank_final(wl)
    return v12, bruto, f_fin, bruto * f_fin
