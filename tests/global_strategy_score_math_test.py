"""Tests unitarios: motor de estrategia global (score_math puro)."""
import importlib.util
from pathlib import Path

import pytest

# Carga el módulo sin importar `app` (evita Flask/SQLAlchemy en entornos mínimos).
_ROOT = Path(__file__).resolve().parents[1]
_SCORE_MATH = _ROOT / "app" / "services" / "global_strategy" / "score_math.py"
_spec = importlib.util.spec_from_file_location("global_strategy_score_math", _SCORE_MATH)
assert _spec and _spec.loader
_score_math = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_score_math)

ratio_objetivo = _score_math.ratio_objetivo
score_asia_price_vs_ma200 = _score_math.score_asia_price_vs_ma200
score_eu_price_vs_ma200 = _score_math.score_eu_price_vs_ma200
score_global = _score_math.score_global
score_price_vs_ma200 = _score_math.score_price_vs_ma200
score_usa_spy_vs_ma200 = _score_math.score_usa_spy_vs_ma200
score_usa_vix_vs_ma200 = _score_math.score_usa_vix_vs_ma200
score_usa_yield_curve_spread_pct = _score_math.score_usa_yield_curve_spread_pct
umbral_objetivo_mercado = _score_math.umbral_objetivo_mercado


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


@pytest.mark.parametrize(
    "fn",
    [score_price_vs_ma200, score_asia_price_vs_ma200, score_eu_price_vs_ma200, score_usa_spy_vs_ma200],
)
def test_score_price_vs_ma200_aliases(fn):
    m = 100.0
    assert fn(110.0, m) == 1.0
    assert fn(90.0, m) == 0.0
    assert abs(fn(100.0, m) - 0.5) < 1e-9


def test_score_usa_vix_vs_ma200_inverts_price_band():
    m = 100.0
    # VIX bajo vs MA → score alto
    assert score_usa_vix_vs_ma200(90.0, m) == 1.0
    # VIX alto vs MA → score bajo
    assert score_usa_vix_vs_ma200(110.0, m) == 0.0
    assert abs(score_usa_vix_vs_ma200(100.0, m) - 0.5) < 1e-9


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
