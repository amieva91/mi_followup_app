"""Tests unitarios: pipelines valoración banco y REIT (sin BD)."""
from types import SimpleNamespace

from app.services.watchlist_bank_valuation import (
    bank_fair_price,
    bank_target_5y_bruto,
    bank_valoracion_12m,
    bank_valuation_pipeline,
    bvps_ref,
    compute_f_bank_final,
)
from app.services.watchlist_reit_valuation import (
    compute_f_re_final,
    reit_flow_per_share,
    reit_target_5y_bruto,
    reit_valoracion_12m,
    reit_valuation_pipeline,
)


def _bank_wl(**kwargs):
    base = dict(
        precio_actual=100.0,
        price_to_book=1.0,
        pb_fair=1.2,
        bvps=None,
        eps=5.0,
        per_ntm=10.0,
        ntm_dividend_yield=4.0,
        roe_pct=12.0,
        bvps_cagr_yoy=None,
        cet1_ratio_pct=15.0,
        npl_ratio_pct=None,
        cost_to_income_pct=None,
        nim_pct=None,
        loan_to_deposit_pct=None,
        cost_of_risk_pct=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_bvps_ref_from_price_over_pb():
    wl = _bank_wl(precio_actual=50.0, price_to_book=2.0, bvps=None)
    assert bvps_ref(wl) == 25.0


def test_bank_fair_price_from_pb_ratio():
    wl = _bank_wl(precio_actual=100.0, price_to_book=1.0, pb_fair=1.2)
    assert bank_fair_price(wl, 100.0) == 120.0
    assert bank_fair_price(wl, None) == 120.0


def test_bank_valoracion_12m():
    wl = _bank_wl(precio_actual=100.0, price_to_book=1.0, pb_fair=1.1, bvps=100.0)
    # P_fair = 110 → +10%
    assert bank_valoracion_12m(wl) == 10.0


def test_bank_target_5y_uses_roe_proxy():
    wl = _bank_wl(
        precio_actual=100.0,
        price_to_book=1.0,
        pb_fair=None,
        bvps=100.0,
        eps=5.0,
        per_ntm=10.0,
        ntm_dividend_yield=4.0,
        roe_pct=10.0,
        bvps_cagr_yoy=None,
    )
    tp = bank_target_5y_bruto(wl)
    assert tp is not None and tp > 100.0 * 1.0


def test_f_bank_clamped():
    wl = _bank_wl(cet1_ratio_pct=8.0)
    f = compute_f_bank_final(wl)
    assert 0.72 <= f <= 1.06


def test_bank_pipeline_requires_price_pb():
    wl = SimpleNamespace(precio_actual=None, price_to_book=1.0)
    v, b, f, a = bank_valuation_pipeline(wl)
    assert v is None and b is None


def _reit_wl(**kwargs):
    base = dict(
        precio_actual=100.0,
        affo_per_share=4.0,
        ffo_per_share=4.5,
        price_to_ffo=15.0,
        p_ffo_fair=16.0,
        cagr_ffo_yoy=3.0,
        same_store_growth_pct=2.0,
        reit_leverage_ratio=None,
        ffo_interest_coverage=None,
        ffo_to_total_debt=None,
        occupancy_pct=None,
        walt_years=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_reit_prefers_affo():
    wl = _reit_wl(affo_per_share=3.0, ffo_per_share=4.0)
    assert reit_flow_per_share(wl) == 3.0


def test_reit_valoracion_fair_vs_price():
    wl = _reit_wl(
        precio_actual=100.0,
        affo_per_share=4.0,
        price_to_ffo=15.0,
        p_ffo_fair=15.0,
    )
    # fair = 4*15 = 60 vs price 100 → -40%
    assert reit_valoracion_12m(wl) == -40.0


def test_reit_target_5y_blend_growth():
    wl = _reit_wl(
        precio_actual=100.0,
        affo_per_share=2.0,
        price_to_ffo=20.0,
        p_ffo_fair=None,
        cagr_ffo_yoy=4.0,
        same_store_growth_pct=2.0,
    )
    tp = reit_target_5y_bruto(wl)
    assert tp is not None
    g = 0.5 * 4.0 + 0.5 * 2.0
    expect = 2.0 * ((1.0 + g / 100.0) ** 5) * 20.0
    assert abs(tp - expect) < 1e-6


def test_f_re_leverage_penalty():
    wl = _reit_wl(reit_leverage_ratio=10.0)
    assert compute_f_re_final(wl) < 1.0


def test_reit_pipeline_minimal():
    wl = _reit_wl(
        cagr_ffo_yoy=3.0,
        same_store_growth_pct=None,
    )
    v, b, f, a = reit_valuation_pipeline(wl)
    assert v is not None
    assert b is not None
    assert f is not None
    assert a == b * f
