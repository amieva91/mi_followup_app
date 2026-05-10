"""Tests: valoración modo general (blend, estilo B, target bruto)."""
from types import SimpleNamespace

from app.services.watchlist_general_valuation import (
    blend_growth_pct,
    calculate_target_price_5yr_bruto,
    compute_style_b_factor_final,
    general_profitable_pipeline,
    per_terminal_ntm_or_fair,
)


def test_blend_both_arithmetic_mean():
    assert blend_growth_pct(10.0, 6.0) == 8.0


def test_blend_single_fallback():
    assert blend_growth_pct(12.0, None) == 12.0
    assert blend_growth_pct(None, 5.0) == 5.0
    assert blend_growth_pct(None, None) is None


def test_per_terminal_prefers_fair():
    assert per_terminal_ntm_or_fair(20.0, 18.0) == 18.0
    assert per_terminal_ntm_or_fair(20.0, None) == 20.0


def test_target_bruto_numeric():
    # EPS 2, g 10%, PER 15 → 2 * 1.1^5 * 15
    tp = calculate_target_price_5yr_bruto(2.0, 10.0, 15.0)
    assert tp is not None
    assert abs(tp - 2.0 * (1.1**5) * 15.0) < 1e-6


def test_style_b_all_missing_is_clamped_neutral():
    wl = SimpleNamespace(
        net_debt_to_ebitda=None,
        fcf_to_net_income=None,
        ebitda_margin_pct=None,
        operating_margin_pct=None,
        roic_pct=None,
        eps=1.0,
    )
    assert compute_style_b_factor_final(wl) == 1.0


def test_style_b_penalizes_high_leverage():
    wl = SimpleNamespace(
        net_debt_to_ebitda=6.0,
        fcf_to_net_income=None,
        ebitda_margin_pct=None,
        operating_margin_pct=None,
        roic_pct=None,
        eps=1.0,
    )
    assert compute_style_b_factor_final(wl) == 0.80


def test_general_pipeline_minimal():
    wl = SimpleNamespace(
        eps=2.0,
        per_ntm=15.0,
        per_fair=None,
        ntm_dividend_yield=2.0,
        cagr_revenue_yoy=10.0,
        cagr_eps_yoy=10.0,
        net_debt_to_ebitda=None,
        fcf_to_net_income=None,
        ebitda_margin_pct=None,
        operating_margin_pct=None,
        roic_pct=None,
    )
    v, bruto, f_fin, adj = general_profitable_pipeline(wl)
    assert v is not None
    assert bruto is not None
    assert f_fin == 1.0
    assert adj == bruto


def test_general_pipeline_eps_negative():
    wl = SimpleNamespace(
        eps=-1.0,
        per_ntm=10.0,
        per_fair=None,
        ntm_dividend_yield=0.0,
        cagr_revenue_yoy=5.0,
        cagr_eps_yoy=5.0,
        net_debt_to_ebitda=None,
        fcf_to_net_income=None,
        ebitda_margin_pct=None,
        operating_margin_pct=None,
        roic_pct=None,
    )
    v, bruto, f_fin, adj = general_profitable_pipeline(wl)
    assert v is None and bruto is None and f_fin is None and adj is None
