"""Tests: bandas de contexto SG (dashboard)."""
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "app" / "services" / "global_strategy" / "sg_context_bands.py"
_spec = importlib.util.spec_from_file_location("sg_context_bands", _PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

sg_band_key = _mod.sg_band_key
sg_context_payload = _mod.sg_context_payload


def test_sg_band_proteccion_upper_bound():
    assert sg_band_key(0.0) == "proteccion"
    assert sg_band_key(0.49) == "proteccion"


def test_sg_band_fragilidad_includes_point_five():
    assert sg_band_key(0.5) == "fragilidad"
    assert sg_band_key(1.0) == "fragilidad"
    assert sg_band_key(1.49) == "fragilidad"


def test_sg_band_crecimiento():
    assert sg_band_key(1.5) == "crecimiento"
    assert sg_band_key(2.0) == "crecimiento"
    assert sg_band_key(2.49) == "crecimiento"


def test_sg_band_euforia_includes_two_point_five():
    assert sg_band_key(2.5) == "euforia"
    assert sg_band_key(3.0) == "euforia"


def test_sg_band_clamps_outside_zero_three():
    assert sg_band_key(-1.0) == "proteccion"
    assert sg_band_key(5.0) == "euforia"


def test_sg_context_payload_shape():
    p = sg_context_payload(2.78)
    assert p["active"] == "euforia"
    assert len(p["bands"]) == 4
    assert {b["key"] for b in p["bands"]} == {"euforia", "crecimiento", "fragilidad", "proteccion"}
