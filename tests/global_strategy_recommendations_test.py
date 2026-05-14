"""Tests: tendencia SG vs media 5 (sg_trend_math, sin Flask)."""
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "app" / "services" / "global_strategy" / "sg_trend_math.py"
_spec = importlib.util.spec_from_file_location("sg_trend_math", _PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

mean5_sg_falling = _mod.mean5_sg_falling


def test_mean5_insufficient_length():
    assert mean5_sg_falling(2.0, [2.0, 2.0, 2.0, 2.0]) is False


def test_mean5_flat_not_falling():
    assert mean5_sg_falling(2.0, [2.0, 2.0, 2.0, 2.0, 2.0]) is False


def test_mean5_falling_below_mean_by_more_than_point3():
    assert mean5_sg_falling(1.0, [1.0, 2.0, 2.0, 2.0, 2.0]) is True


def test_mean5_small_drop_not_falling():
    assert mean5_sg_falling(1.75, [1.75, 2.0, 2.0, 2.0, 2.0]) is False
