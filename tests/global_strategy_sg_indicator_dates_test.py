"""Tests: fechas indicator_as_of desde snapshot macro (sin Flask)."""
import importlib.util
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "app" / "services" / "global_strategy" / "sg_indicator_dates.py"
_spec = importlib.util.spec_from_file_location("sg_indicator_dates", _PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

indicator_as_of_minimum = _mod.indicator_as_of_minimum


def test_indicator_as_of_minimum_vix_mode_uses_vix_fez_asia():
    snap = {
        "usa_score_mode": "vix",
        "series": {
            "vix": {"as_of_date": "2026-05-14"},
            "fez": {"as_of_date": "2026-05-13"},
            "asia_hk": {"as_of_date": "2026-05-12"},
        },
    }
    assert indicator_as_of_minimum(snap) == date(2026, 5, 12)


def test_indicator_as_of_minimum_spy_mode_uses_spy():
    snap = {
        "usa_score_mode": "spy",
        "series": {
            "spy": {"as_of_date": "2026-05-10"},
            "fez": {"as_of_date": "2026-05-11"},
            "asia_hk": {"as_of_date": "2026-05-11"},
        },
    }
    assert indicator_as_of_minimum(snap) == date(2026, 5, 10)


def test_indicator_as_of_minimum_empty():
    assert indicator_as_of_minimum({}) is None
