"""
Valoración modo ``realestate`` / REIT: FFO/AFFO, P/FFO y F_RE.

Referencias: docs/implementaciones/WATCHLIST_VALORACION_PLAN_IMPLEMENTACION.md §14.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from app.models.watchlist import Watchlist


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def reit_flow_per_share(wl: Watchlist) -> Optional[float]:
    if wl.affo_per_share is not None and wl.affo_per_share > 0:
        return wl.affo_per_share
    if wl.ffo_per_share is not None and wl.ffo_per_share > 0:
        return wl.ffo_per_share
    return None


def reit_m_terminal(wl: Watchlist) -> Optional[float]:
    if wl.p_ffo_fair is not None and wl.p_ffo_fair > 0:
        return wl.p_ffo_fair
    if wl.price_to_ffo is not None and wl.price_to_ffo > 0:
        return wl.price_to_ffo
    return None


def reit_fair_price(wl: Watchlist) -> Optional[float]:
    flow = reit_flow_per_share(wl)
    m = reit_m_terminal(wl)
    if flow is None or m is None:
        return None
    return flow * m


def reit_valoracion_12m(wl: Watchlist) -> Optional[float]:
    p0 = wl.precio_actual
    if p0 is None or p0 <= 0:
        return None
    p_fair = reit_fair_price(wl)
    if p_fair is None or p_fair <= 0:
        return None
    return round((p_fair / p0 - 1.0) * 100.0, 2)


def reit_g_eff_pct(wl: Watchlist) -> Optional[float]:
    cf = wl.cagr_ffo_yoy
    ss = wl.same_store_growth_pct
    has_cf = cf is not None
    has_ss = ss is not None
    if has_cf and has_ss:
        g = 0.5 * cf + 0.5 * ss
    elif has_cf:
        g = cf
    elif has_ss:
        g = ss
    else:
        return None
    return _clamp(g, -2.0, 7.0)


def reit_target_5y_bruto(wl: Watchlist) -> Optional[float]:
    flow = reit_flow_per_share(wl)
    m_t = reit_m_terminal(wl)
    g = reit_g_eff_pct(wl)
    if flow is None or m_t is None or g is None:
        return None
    gd = g / 100.0
    return flow * ((1.0 + gd) ** 5) * m_t


def factor_reit_nd_ebitda(x: Optional[float]) -> float:
    if x is None:
        return 1.0
    if x <= 5.5:
        return 1.0
    if x <= 7.0:
        return 0.98
    if x <= 9.0:
        return 0.94
    return 0.88


def factor_ffo_interest_coverage(x: Optional[float]) -> float:
    """Reservado para input futuro; sin dato → 1,00."""
    if x is None:
        return 1.0
    if x >= 4.5:
        return 1.0
    if x >= 3.5:
        return 0.98
    if x >= 2.5:
        return 0.93
    return 0.85


def factor_ffo_to_total_debt(x: Optional[float]) -> float:
    """Reservado para input futuro; sin dato → 1,00."""
    if x is None:
        return 1.0
    if x >= 0.15:
        return 1.0
    if x >= 0.11:
        return 0.98
    if x >= 0.08:
        return 0.94
    return 0.88


def reit_f_cov(ffo_interest: Optional[float], ffo_debt: Optional[float]) -> float:
    a = factor_ffo_interest_coverage(ffo_interest)
    b = factor_ffo_to_total_debt(ffo_debt)
    return math.sqrt(a * b)


def factor_reit_occupancy(pct: Optional[float]) -> float:
    if pct is None:
        return 1.0
    if pct >= 98.0:
        return 1.02
    if pct >= 95.0:
        return 1.0
    if pct >= 90.0:
        return 0.96
    return 0.88


def factor_reit_walt(years: Optional[float]) -> float:
    if years is None:
        return 1.0
    if years < 5.0:
        return 0.94
    if years < 7.0:
        return 0.97
    if years <= 12.0:
        return 1.0
    if years <= 15.0:
        return 1.01
    return 1.02


def compute_f_re_final(wl: Watchlist) -> float:
    f_cov = reit_f_cov(None, None)
    f = (
        factor_reit_nd_ebitda(wl.reit_leverage_ratio)
        * f_cov
        * factor_reit_occupancy(wl.occupancy_pct)
        * factor_reit_walt(wl.walt_years)
    )
    return min(1.06, max(0.72, f))


def reit_minimum_inputs_ok(wl: Watchlist) -> bool:
    if wl.precio_actual is None or wl.precio_actual <= 0:
        return False
    if reit_flow_per_share(wl) is None:
        return False
    if wl.price_to_ffo is None or wl.price_to_ffo <= 0:
        return False
    return True


def reit_valuation_pipeline(
    wl: Watchlist,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Retorna (valoracion_12m, target_bruto, f_re_final, target_adj).
    """
    if not reit_minimum_inputs_ok(wl):
        return None, None, None, None

    v12 = reit_valoracion_12m(wl)
    bruto = reit_target_5y_bruto(wl)
    if bruto is None:
        return v12, None, None, None
    f_fin = compute_f_re_final(wl)
    return v12, bruto, f_fin, bruto * f_fin
