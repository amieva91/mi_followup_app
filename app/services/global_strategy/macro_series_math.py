"""Utilidades puras para series diarias del motor macro (sin I/O)."""
from __future__ import annotations

from typing import Any, Optional


def merge_point_maps(
    existing_points: list[dict[str, Any]],
    new_points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for p in existing_points or []:
        d = p.get("date")
        if d:
            by_date[str(d)] = dict(p)
    for p in new_points or []:
        d = p.get("date")
        if d:
            by_date[str(d)] = dict(p)
    return [by_date[k] for k in sorted(by_date.keys())]


def last_close_and_ma200(data_points: list[dict[str, Any]]) -> tuple[Optional[float], Optional[float], Optional[str]]:
    pts = [p for p in (data_points or []) if p.get("date") and p.get("price") is not None]
    if len(pts) < 200:
        return None, None, None
    prices = [float(p["price"]) for p in pts]
    last = prices[-1]
    ma200 = sum(prices[-200:]) / 200.0
    last_d = str(pts[-1]["date"])
    return last, ma200, last_d
