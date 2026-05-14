"""
Bandas de score global (SG ∈ [0, 3]) para etiqueta de contexto y significado operativo (UI).
"""
from __future__ import annotations

from typing import Any, Final, Literal

SgBandKey = Literal["euforia", "crecimiento", "fragilidad", "proteccion"]

_BAND_ROWS: Final[tuple[dict[str, str], ...]] = (
    {
        "key": "euforia",
        "score_range": "2.5 – 3.0",
        "label": "Euforia / Expansión Total",
        "operational": "Máximo apalancamiento permitido (2.0×).",
    },
    {
        "key": "crecimiento",
        "score_range": "1.5 – 2.5",
        "label": "Crecimiento Sólido",
        "operational": "Inversión agresiva (1.3×) pero vigilando deudas.",
    },
    {
        "key": "fragilidad",
        "score_range": "0.5 – 1.5",
        "label": "Fragilidad / Dudas",
        "operational": "Desapalancamiento y creación de liquidez (20%).",
    },
    {
        "key": "proteccion",
        "score_range": "0.0 – 0.5",
        "label": "Protección Máxima",
        "operational": "Escenario de recesión/pánico. Liquidez > 40%.",
    },
)


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


def sg_context_payload(sg: float) -> dict[str, Any]:
    """Payload JSON para dashboard: bandas fijas + clave de la fila activa."""
    active = sg_band_key(sg)
    return {
        "active": active,
        "bands": [dict(row) for row in _BAND_ROWS],
    }
