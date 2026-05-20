"""Tests: bandas de contexto SG (dashboard)."""
import importlib.util
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_SCORE_MATH = _ROOT / "app" / "services" / "global_strategy" / "score_math.py"
_SG_CTX = _ROOT / "app" / "services" / "global_strategy" / "sg_context_bands.py"

_sm_spec = importlib.util.spec_from_file_location("gs_score_math", _SCORE_MATH)
assert _sm_spec and _sm_spec.loader
_sm_mod = importlib.util.module_from_spec(_sm_spec)
_sm_spec.loader.exec_module(_sm_mod)

_ctx_src = _SG_CTX.read_text().replace(
    "from app.services.global_strategy.score_math import ratio_objetivo\n",
    "",
)
_ctx_ns: dict[str, Any] = {"__builtins__": __builtins__, "ratio_objetivo": _sm_mod.ratio_objetivo}
exec(compile(_ctx_src, str(_SG_CTX), "exec"), _ctx_ns)

sg_band_key = _ctx_ns["sg_band_key"]
sg_context_payload = _ctx_ns["sg_context_payload"]


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
    assert "ro" in p
    assert p["ro"] > 1.3


def test_active_crecimiento_operational_uses_progressive_ro_not_fixed_13():
    p = sg_context_payload(2.41, co=104_505.0)
    active = next(b for b in p["bands"] if b["key"] == p["active"])
    assert p["active"] == "crecimiento"
    assert "1,3×" not in active["operational"]
    assert "× CO)" in active["operational"]
    assert "≈" not in active["operational"]
    assert p["uom_eur"] > 130_000
    assert p["ro"] > 1.5
