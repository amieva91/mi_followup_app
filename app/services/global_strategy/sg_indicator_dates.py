"""Cálculo de fechas de cierre a partir del snapshot macro (solo stdlib)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional


def indicator_as_of_minimum(snap: dict[str, Any]) -> Optional[date]:
    """
    Fecha de indicadores = mínimo entre las fechas ``as_of`` de los subyacentes
    que entran en el score (conservador: el cierre más rezagado).
    """
    mode = str(snap.get("usa_score_mode") or "vix").strip().lower()
    ser = snap.get("series") or {}
    dates: list[date] = []

    if mode == "spy":
        d = _parse_iso((ser.get("spy") or {}).get("as_of_date"))
    else:
        d = _parse_iso((ser.get("vix") or {}).get("as_of_date"))
    if d:
        dates.append(d)

    for key in ("fez", "asia_hk"):
        d = _parse_iso((ser.get(key) or {}).get("as_of_date"))
        if d:
            dates.append(d)

    return min(dates) if dates else None


def _parse_iso(s: Any) -> Optional[date]:
    if not s or not isinstance(s, str):
        return None
    try:
        return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
