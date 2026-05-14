"""Tests: utilidades puras de series macro (merge + MA200)."""
import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_MATH = _ROOT / "app" / "services" / "global_strategy" / "macro_series_math.py"
_spec = importlib.util.spec_from_file_location("macro_series_math", _MATH)
assert _spec and _spec.loader
_ms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ms)

merge_point_maps = _ms.merge_point_maps
last_close_and_ma200 = _ms.last_close_and_ma200
tail_chart_points = _ms.tail_chart_points


def test_merge_point_maps_orders_and_overrides():
    a = [{"date": "2024-01-01", "price": 1.0}, {"date": "2024-01-03", "price": 3.0}]
    b = [{"date": "2024-01-02", "price": 2.0}, {"date": "2024-01-03", "price": 33.0}]
    m = merge_point_maps(a, b)
    assert [p["date"] for p in m] == ["2024-01-01", "2024-01-02", "2024-01-03"]
    assert m[2]["price"] == 33.0


def test_last_close_and_ma200_insufficient():
    pts = [{"date": f"2024-01-{i+1:02d}", "price": float(i)} for i in range(50)]
    assert last_close_and_ma200(pts) == (None, None, None)


def test_last_close_and_ma200_exact_window():
    from datetime import date, timedelta

    d0 = date(2024, 1, 2)
    pts = [{"date": (d0 + timedelta(days=i)).isoformat(), "price": 100.0 + i} for i in range(200)]
    last, ma200, d = last_close_and_ma200(pts)
    assert last == 100.0 + 199
    assert abs(ma200 - (sum(100.0 + j for j in range(200)) / 200.0)) < 1e-9
    assert d == pts[-1]["date"]


def test_tail_chart_points_max_and_shape():
    from datetime import date, timedelta

    d0 = date(2024, 1, 2)
    pts = [{"date": (d0 + timedelta(days=i)).isoformat(), "price": float(i)} for i in range(55)]
    t = tail_chart_points(pts, max_points=10)
    assert len(t) == 10
    assert t[0]["date"] == (d0 + timedelta(days=45)).isoformat()
    assert t[-1]["v"] == 54.0
    assert "date" in t[0] and "v" in t[0]
