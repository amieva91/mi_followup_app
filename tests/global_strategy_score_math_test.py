"""Tests unitarios: motor de estrategia global (score_math puro)."""
import pytest

from app.services.global_strategy.score_math import (
    ratio_objetivo,
    score_asia_price_vs_ma200,
    score_eu_vstoxx_vs_ma200,
    score_global,
    score_usa_yield_curve_spread_pct,
    umbral_objetivo_mercado,
)


@pytest.mark.parametrize(
    "x,expected",
    [
        (0.6, 1.0),
        (-0.6, 0.0),
        (0.0, 0.5),
        (0.5, 1.0),
        (-0.5, 0.0),
        (0.25, 0.75),
    ],
)
def test_score_usa_yield_curve_spread_pct(x, expected):
    assert abs(score_usa_yield_curve_spread_pct(x) - expected) < 1e-9


def test_score_eu_vstoxx_vs_ma200():
    m = 20.0
    assert score_eu_vstoxx_vs_ma200(16.0, m) == 1.0  # v <= 0.8*m
    assert score_eu_vstoxx_vs_ma200(35.0, m) == 0.0  # v >= 1.5*m
    mid = score_eu_vstoxx_vs_ma200(26.0, m)  # entre 16 y 30
    assert 0.0 < mid < 1.0


def test_score_asia_price_vs_ma200():
    m = 100.0
    assert score_asia_price_vs_ma200(110.0, m) == 1.0
    assert score_asia_price_vs_ma200(90.0, m) == 0.0
    assert abs(score_asia_price_vs_ma200(100.0, m) - 0.5) < 1e-9


def test_score_global_sum():
    assert score_global(1.0, 0.5, 0.25) == 1.75
    assert score_global(1.0, 1.0, 1.0) == 3.0


@pytest.mark.parametrize(
    "sg,ro",
    [
        (0.0, 0.0),
        (0.5, 0.6),
        (1.0, 0.8),
        (2.0, 1.3),
        (3.0, 2.0),
        (1.5, 1.05),  # mitad entre (1,0.8) y (2,1.3)
        (-1.0, 0.0),
        (5.0, 2.0),
    ],
)
def test_ratio_objetivo_nodes_and_interpolation(sg, ro):
    assert abs(ratio_objetivo(sg) - ro) < 1e-9


def test_umbral_objetivo_mercado():
    assert abs(umbral_objetivo_mercado(100_000.0, 3.0) - 200_000.0) < 1e-6
    assert abs(umbral_objetivo_mercado(100_000.0, 1.0) - 80_000.0) < 1e-6
