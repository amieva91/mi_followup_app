"""Tests: valoración modo general (blend, estilo B, target bruto)."""
from types import SimpleNamespace

from app.services.watchlist_general_valuation import (
    blend_growth_pct,
    calculate_target_price_5yr_bruto,
    calculate_valoracion_12m_from_g,
    compute_style_b_factor_final,
    effective_fcf_to_net_income_ratio,
    general_loss_valoracion_12m,
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
        fcf_margin_pct=None,
        net_income_margin_pct=None,
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
        fcf_margin_pct=None,
        net_income_margin_pct=None,
        fcf_to_net_income=None,
        ebitda_margin_pct=None,
        operating_margin_pct=None,
        roic_pct=None,
        eps=1.0,
    )
    assert compute_style_b_factor_final(wl) == 0.80


def test_effective_fcf_bn_prefers_margin_quotient():
    wl = SimpleNamespace(
        fcf_margin_pct=10.0,
        net_income_margin_pct=5.0,
        fcf_to_net_income=0.5,
    )
    assert effective_fcf_to_net_income_ratio(wl) == 2.0


def test_effective_fcf_bn_falls_back_to_ratio():
    wl = SimpleNamespace(
        fcf_margin_pct=10.0,
        net_income_margin_pct=None,
        fcf_to_net_income=0.85,
    )
    assert effective_fcf_to_net_income_ratio(wl) == 0.85


def test_effective_fcf_bn_both_negative_margins_skips_misleading_quotient():
    # (-5)/(-2) = +2.5 sería engañoso; se ignora y se usa ratio legado
    wl = SimpleNamespace(
        fcf_margin_pct=-5.0,
        net_income_margin_pct=-2.0,
        fcf_to_net_income=0.6,
    )
    assert effective_fcf_to_net_income_ratio(wl) == 0.6


def test_effective_fcf_bn_both_negative_without_legacy():
    wl = SimpleNamespace(
        fcf_margin_pct=-5.0,
        net_income_margin_pct=-2.0,
        fcf_to_net_income=None,
    )
    assert effective_fcf_to_net_income_ratio(wl) is None


def test_style_b_uses_margin_derived_ratio_for_fcf_factor():
    # ratio 2.0 from margins → factor_fcf 1.00 (domina sobre fcf_to_net_income legado)
    wl = SimpleNamespace(
        net_debt_to_ebitda=None,
        fcf_margin_pct=10.0,
        net_income_margin_pct=5.0,
        fcf_to_net_income=0.5,
        ebitda_margin_pct=None,
        operating_margin_pct=None,
        roic_pct=None,
        eps=1.0,
    )
    assert compute_style_b_factor_final(wl) == 1.0


def test_general_pipeline_minimal():
    wl = SimpleNamespace(
        eps=2.0,
        per_ntm=15.0,
        per_fair=None,
        ntm_dividend_yield=2.0,
        cagr_revenue_yoy=10.0,
        cagr_eps_yoy=10.0,
        net_debt_to_ebitda=None,
        fcf_margin_pct=None,
        net_income_margin_pct=None,
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
        fcf_margin_pct=None,
        net_income_margin_pct=None,
        fcf_to_net_income=None,
        ebitda_margin_pct=None,
        operating_margin_pct=None,
        roic_pct=None,
    )
    v, bruto, f_fin, adj = general_profitable_pipeline(wl)
    assert v is None and bruto is None and f_fin is None and adj is None


def test_general_loss_valoracion_revenue_only_matches_pegy_on_revenue():
    wl = SimpleNamespace(
        eps=-0.5,
        per_ntm=12.0,
        per_fair=18.0,
        ntm_dividend_yield=1.0,
        cagr_revenue_yoy=8.0,
        cagr_eps_yoy=None,
    )
    v_loss = general_loss_valoracion_12m(wl)
    v_ref = calculate_valoracion_12m_from_g(12.0, 1.0, 8.0)
    assert v_loss == v_ref


def test_general_loss_valoracion_uses_blend_when_both_cagrs():
    wl = SimpleNamespace(
        eps=-0.5,
        per_ntm=20.0,
        per_fair=None,
        ntm_dividend_yield=2.0,
        cagr_revenue_yoy=10.0,
        cagr_eps_yoy=30.0,
    )
    g = blend_growth_pct(10.0, 30.0)
    assert g == 20.0
    v = general_loss_valoracion_12m(wl)
    assert v == calculate_valoracion_12m_from_g(20.0, 2.0, 20.0)


def test_general_loss_valoracion_fair_per_when_ntm_missing():
    wl = SimpleNamespace(
        eps=-1.0,
        per_ntm=None,
        per_fair=15.0,
        ntm_dividend_yield=0.0,
        cagr_revenue_yoy=5.0,
        cagr_eps_yoy=None,
    )
    assert general_loss_valoracion_12m(wl) == calculate_valoracion_12m_from_g(15.0, 0.0, 5.0)
