"""
Bandas de score global (SG ∈ [0, 3]) para etiqueta de contexto y significado operativo (UI).

El significado operativo usa RO(SG) progresivo (ratio_objetivo), no multiplicadores fijos de nodos.
"""
from __future__ import annotations

from typing import Any, Final, Literal

from app.services.global_strategy.score_math import ratio_objetivo

SgBandKey = Literal["euforia", "crecimiento", "fragilidad", "proteccion"]

_BAND_META: Final[tuple[dict[str, str], ...]] = (
    {"key": "euforia", "score_range": "2.5 – 3.0", "label": "Euforia / Expansión Total"},
    {"key": "crecimiento", "score_range": "1.5 – 2.5", "label": "Crecimiento Sólido"},
    {"key": "fragilidad", "score_range": "0.5 – 1.5", "label": "Fragilidad / Dudas"},
    {"key": "proteccion", "score_range": "0.0 – 0.5", "label": "Protección Máxima"},
)

# Límites SG por banda (hi exclusivo salvo euforia que incluye 3.0)
_BAND_SG_BOUNDS: Final[dict[SgBandKey, tuple[float, float]]] = {
    "euforia": (2.5, 3.0),
    "crecimiento": (1.5, 2.5),
    "fragilidad": (0.5, 1.5),
    "proteccion": (0.0, 0.5),
}


def sg_band_key(sg: float) -> SgBandKey:
    """
    Clasifica SG acotado a [0, 3]. Límites: ≥2.5 euforia; 1.5–<2.5 crecimiento;
    0.5–<1.5 fragilidad; <0.5 protección (0.5 entra en fragilidad).
    """
    x = max(0.0, min(3.0, float(sg)))
    if x >= 2.5:
        return "euforia"
    if x >= 1.5:
        return "crecimiento"
    if x >= 0.5:
        return "fragilidad"
    return "proteccion"


def _fmt_ro(ro: float) -> str:
    s = f"{float(ro):.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") + "×"


def ratio_inversion_real(co: float | None, ir: float | None) -> float | None:
    """Apalancamiento real del usuario: IR / CO (posiciones vs capital operativo bróker)."""
    if co is None or ir is None or float(co) <= 0:
        return None
    return float(ir) / float(co)


def _ro_range_plain(lo_ro: float, hi_ro: float) -> str:
    """Rango RO de banda sin paréntesis (fila activa, fuera del multiplicador actual)."""
    if abs(hi_ro - lo_ro) < 0.005:
        return _fmt_ro(lo_ro)
    lo_s, hi_s = _fmt_ro(lo_ro), _fmt_ro(hi_ro)
    if lo_s == hi_s:
        return lo_s
    return f"{lo_s}–{hi_s}"


def _ro_co_range_clause(lo_ro: float, hi_ro: float) -> str:
    plain = _ro_range_plain(lo_ro, hi_ro)
    return f"({plain})"


def _band_ro_endpoints(key: SgBandKey) -> tuple[float, float]:
    lo_sg, hi_sg = _BAND_SG_BOUNDS[key]
    # SG superior exclusivo en clasificación → RO justo por debajo del límite
    if key == "crecimiento":
        hi_sg = 2.499
    elif key == "fragilidad":
        hi_sg = 1.499
    elif key == "proteccion":
        hi_sg = 0.499
    return ratio_objetivo(lo_sg), ratio_objetivo(hi_sg)


def _inactive_operational_text(key: SgBandKey) -> str:
    """Fila inactiva: rango RO progresivo de la banda entre paréntesis (comportamiento actual)."""
    lo_ro, hi_ro = _band_ro_endpoints(key)
    clause = _ro_co_range_clause(lo_ro, hi_ro)
    if key == "euforia":
        return f"Máximo apalancamiento permitido {clause}."
    if key == "crecimiento":
        return f"Inversión agresiva {clause} pero vigilando deudas."
    if key == "fragilidad":
        return f"Desapalancamiento y creación de liquidez {clause}."
    return f"Escenario de recesión/pánico. Exposición objetivo {clause}."


def active_operational_parts(key: SgBandKey, ro_real: float | None) -> dict[str, str]:
    """
    Fila activa: rango RO de la banda fuera del paréntesis; IR/CO real del usuario en negrita entre paréntesis.
    """
    lo_ro, hi_ro = _band_ro_endpoints(key)
    ro_range = _ro_range_plain(lo_ro, hi_ro)
    highlight = f"({_fmt_ro(ro_real)})" if ro_real is not None else ""
    if key == "euforia":
        return {
            "prefix": "Máximo apalancamiento permitido · ",
            "range": ro_range,
            "highlight": highlight,
            "suffix": ".",
        }
    if key == "crecimiento":
        return {
            "prefix": "Inversión agresiva · ",
            "range": ro_range,
            "highlight": highlight,
            "suffix": " pero vigilando deudas.",
        }
    if key == "fragilidad":
        return {
            "prefix": "Desapalancamiento y creación de liquidez · ",
            "range": ro_range,
            "highlight": highlight,
            "suffix": ".",
        }
    return {
        "prefix": "Escenario de recesión/pánico · ",
        "range": ro_range,
        "highlight": highlight,
        "suffix": ".",
    }


def _active_operational_plain(parts: dict[str, str]) -> str:
    mid = f" {parts['highlight']}" if parts.get("highlight") else ""
    return f"{parts['prefix']}{parts['range']}{mid}{parts['suffix']}"


def sg_context_payload(
    sg: float,
    co: float | None = None,
    ir: float | None = None,
) -> dict[str, Any]:
    """Payload JSON para dashboard: bandas + RO objetivo/UOM y apalancamiento real IR/CO."""
    sg_clamped = max(0.0, min(3.0, float(sg)))
    active = sg_band_key(sg_clamped)
    ro = ratio_objetivo(sg_clamped)
    co_val = float(co) if co is not None and co > 0 else None
    ir_val = float(ir) if ir is not None and co_val is not None else None
    ro_real = ratio_inversion_real(co_val, ir_val)
    uom = (co_val * ro) if co_val is not None else None

    bands: list[dict[str, Any]] = []
    for meta in _BAND_META:
        key = meta["key"]  # type: ignore[assignment]
        assert key in _BAND_SG_BOUNDS
        is_active = key == active
        if is_active:
            parts = active_operational_parts(key, ro_real)
            entry = {
                **meta,
                "operational": _active_operational_plain(parts),
                "operational_parts": parts,
            }
        else:
            entry = {
                **meta,
                "operational": _inactive_operational_text(key),
            }
        bands.append(entry)

    payload: dict[str, Any] = {
        "active": active,
        "ro": round(ro, 4),
        "bands": bands,
    }
    if co_val is not None:
        payload["co_eur"] = round(co_val, 2)
    if ir_val is not None:
        payload["ir_eur"] = round(ir_val, 2)
    if ro_real is not None:
        payload["ro_real"] = round(ro_real, 4)
    if uom is not None:
        payload["uom_eur"] = round(uom, 2)
    return payload
