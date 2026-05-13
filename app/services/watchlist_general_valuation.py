"""
Valoración modo ``general``: blend de crecimiento, target 5y bruto/ajustado (estilo B).

Referencias: docs/implementaciones/WATCHLIST_VALORACION_PLAN_IMPLEMENTACION.md §8–9.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from app.models.watchlist import Watchlist


def blend_growth_pct(
    cagr_revenue_yoy: Optional[float],
    cagr_eps_yoy: Optional[float],
) -> Optional[float]:
    """
    Media aritmética de CAGR revenue y CAGR EPS (%) cuando ambos existen;
    si solo uno, ese valor; si ninguno → None.
    """
    has_r = cagr_revenue_yoy is not None
    has_e = cagr_eps_yoy is not None
    if has_r and has_e:
        return (cagr_revenue_yoy + cagr_eps_yoy) / 2.0
    if has_r:
        return cagr_revenue_yoy
    if has_e:
        return cagr_eps_yoy
    return None


def per_terminal_ntm_or_fair(per_ntm: Optional[float], per_fair: Optional[float]) -> Optional[float]:
    """PER objetivo a 5y: fair si existe y > 0; si no PER NTM."""
    if per_fair is not None and per_fair > 0:
        return per_fair
    if per_ntm is not None and per_ntm > 0:
        return per_ntm
    return None


def calculate_target_price_5yr_bruto(
    eps: Optional[float],
    g_eff_pct: Optional[float],
    per_terminal: Optional[float],
) -> Optional[float]:
    """
    P_5y^bruto = EPS * (1 + g_eff)^5 * PER_T
    g_eff en % (p. ej. 8 → 0,08 anual compuesto).
    """
    if eps is None or g_eff_pct is None or per_terminal is None:
        return None
    if eps <= 0 or per_terminal <= 0:
        return None
    g = g_eff_pct / 100.0
    return eps * ((1.0 + g) ** 5) * per_terminal


def factor_net_debt_to_ebitda(ratio: Optional[float]) -> float:
    if ratio is None:
        return 1.0
    if ratio <= 2.0:
        return 1.00
    if ratio <= 3.0:
        return 0.98
    if ratio <= 4.0:
        return 0.94
    if ratio <= 5.0:
        return 0.88
    return 0.80


def effective_fcf_to_net_income_ratio(wl: "Watchlist") -> Optional[float]:
    """
    Si existen ambos márgenes (FCF/ventas y BN/ventas, en % numérico), FCF/BN ≈ cociente.
    Si falta alguno o el denominador es ~0, se usa ``fcf_to_net_income`` (ratio directo).

    Si **ambos** márgenes son negativos, el cociente es matemáticamente positivo pero no
    refleja “calidad” FCF/BN; en ese caso **no** se usa el cociente y se aplica el mismo
    fallback que cuando falta algún margen (``fcf_to_net_income`` o ``None``).
    """
    fm = getattr(wl, "fcf_margin_pct", None)
    nim = getattr(wl, "net_income_margin_pct", None)
    legacy = getattr(wl, "fcf_to_net_income", None)
    if fm is not None and nim is not None and abs(float(nim)) > 1e-9:
        fmv, nimv = float(fm), float(nim)
        if fmv < 0 and nimv < 0:
            return legacy
        return fmv / nimv
    return legacy


def factor_fcf_to_net_income(ratio: Optional[float], eps: Optional[float]) -> float:
    if ratio is None:
        return 1.0
    if eps is not None and eps > 0 and ratio <= 0:
        return 0.85
    if ratio >= 0.90:
        return 1.00
    if ratio >= 0.75:
        return 0.97
    if ratio >= 0.50:
        return 0.92
    return 0.85


def factor_roic(roic_pct: Optional[float]) -> float:
    if roic_pct is None:
        return 1.0
    if roic_pct < 6:
        return 0.93
    if roic_pct < 9:
        return 0.97
    if roic_pct < 12:
        return 1.00
    if roic_pct < 18:
        return 1.02
    return 1.03


def factor_ebitda_margin(pct: Optional[float]) -> float:
    if pct is None:
        return 1.0
    if pct < 12:
        return 0.96
    if pct < 18:
        return 0.99
    if pct <= 28:
        return 1.00
    return 1.02


def factor_operating_margin(pct: Optional[float]) -> float:
    if pct is None:
        return 1.0
    if pct < 8:
        return 0.95
    if pct < 12:
        return 0.99
    if pct <= 22:
        return 1.00
    return 1.02


def combine_margin_factors(
    ebitda_margin_pct: Optional[float],
    operating_margin_pct: Optional[float],
) -> float:
    fe = factor_ebitda_margin(ebitda_margin_pct)
    fo = factor_operating_margin(operating_margin_pct)
    if ebitda_margin_pct is None and operating_margin_pct is None:
        return 1.0
    if ebitda_margin_pct is None:
        return fo
    if operating_margin_pct is None:
        return fe
    return math.sqrt(fe * fo)


def calculate_valoracion_12m_from_g(
    per: Optional[float],
    dividend_yield_pct: Optional[float],
    g_blend_pct: Optional[float],
) -> Optional[float]:
    """Misma convención que WatchlistMetricsService.calculate_valoracion_12m (signo invertido)."""
    if per is None or g_blend_pct is None or per <= 0:
        return None
    d = dividend_yield_pct if dividend_yield_pct is not None else 0.0
    denom = g_blend_pct + d
    if denom == 0:
        return None
    pegy = per / denom
    return round(-((pegy - 1.0) * 100.0), 2)


def general_loss_valoracion_12m(wl: "Watchlist") -> Optional[float]:
    """
    Modo ``general`` con EPS ≤ 0: PEGY usando la misma media de CAGRs que el camino rentable
    (``blend_growth_pct``: revenue + EPS). PER: NTM si > 0, si no ``per_fair`` > 0.

    El target a 5 años sigue derivándose en ``WatchlistMetricsService`` de la extrapolación
    sobre el precio a partir de esta valoración (no PER × EPS con pérdidas).
    """
    per_for_pegy = None
    if wl.per_ntm is not None and wl.per_ntm > 0:
        per_for_pegy = wl.per_ntm
    elif wl.per_fair is not None and wl.per_fair > 0:
        per_for_pegy = wl.per_fair
    g_eff = blend_growth_pct(wl.cagr_revenue_yoy, wl.cagr_eps_yoy)
    if per_for_pegy is None or g_eff is None:
        return None
    return calculate_valoracion_12m_from_g(
        per_for_pegy,
        wl.ntm_dividend_yield,
        g_eff,
    )


def compute_style_b_factor_final(wl: Watchlist) -> float:
    """
    F = f_debt * f_fcf * f_margin * f_roic; F_final en [0,72 .. 1,06].
    """
    ratio_fcf_bn = effective_fcf_to_net_income_ratio(wl)
    f = (
        factor_net_debt_to_ebitda(wl.net_debt_to_ebitda)
        * factor_fcf_to_net_income(ratio_fcf_bn, wl.eps)
        * combine_margin_factors(wl.ebitda_margin_pct, wl.operating_margin_pct)
        * factor_roic(wl.roic_pct)
    )
    return min(1.06, max(0.72, f))


def general_profitable_pipeline(
    wl: Watchlist,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Retorna (valoracion_12m, target_bruto, f_final, target_adj).
    Sin PEGY/target si falta PER NTM, EPS>0 o blend de crecimiento.
    """
    if wl.eps is None or wl.eps <= 0:
        return None, None, None, None
    if wl.per_ntm is None or wl.per_ntm <= 0:
        return None, None, None, None

    g = blend_growth_pct(wl.cagr_revenue_yoy, wl.cagr_eps_yoy)
    if g is None:
        return None, None, None, None

    div = wl.ntm_dividend_yield
    valoracion = calculate_valoracion_12m_from_g(wl.per_ntm, div, g)

    per_t = per_terminal_ntm_or_fair(wl.per_ntm, wl.per_fair)
    bruto = calculate_target_price_5yr_bruto(wl.eps, g, per_t)
    if bruto is None:
        return valoracion, None, None, None

    f_final = compute_style_b_factor_final(wl)
    adj = bruto * f_final
    return valoracion, bruto, f_final, adj
