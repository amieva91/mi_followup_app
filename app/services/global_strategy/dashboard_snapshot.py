"""
Payload de dashboard para el widget de estrategia global (SG + scores + regiones).

Solo hay datos cuando el usuario tiene módulo `stock` y existe al menos una fila
en `global_strategy_sg_daily` (poblada por el job macro diario).
Las series por región vienen de `global_strategy_macro_daily` (mismo job diario).
"""
from __future__ import annotations

from typing import Any, Optional

from app.models import User
from app.models.global_strategy_macro_daily import GlobalStrategyMacroDaily, GlobalStrategyMacroState
from app.models.global_strategy_sg_daily import GlobalStrategySgDaily
from app.services.global_strategy.macro_series_math import last_close_and_ma200, tail_chart_points
from app.services.global_strategy.sg_context_bands import sg_context_payload


def _region_block(
    *,
    key: str,
    label: str,
    series_key: str,
    ticker: str,
    score: Optional[float],
    points: list[dict[str, Any]],
    hue: str,
) -> Optional[dict[str, Any]]:
    last, ma200, last_d = last_close_and_ma200(list(points))
    if last is None or ma200 is None or ma200 <= 0:
        return None
    band_low = round(0.95 * ma200, 6)
    band_high = round(1.05 * ma200, 6)
    chart = tail_chart_points(points, 100)
    if not chart:
        return None
    return {
        "key": key,
        "label": label,
        "series_key": series_key,
        "ticker": ticker,
        "close": round(float(last), 6),
        "ma200": round(float(ma200), 6),
        "band_low": band_low,
        "band_high": band_high,
        "as_of_date": last_d,
        "score": round(float(score), 2) if score is not None else None,
        "hue": hue,
        "chart": chart,
    }


def get_global_strategy_dashboard_snapshot(user_id: int) -> Optional[dict[str, Any]]:
    user = User.query.get(user_id)
    if not user or not user.has_module("stock"):
        return None

    row = (
        GlobalStrategySgDaily.query.filter_by(user_id=user_id)
        .order_by(GlobalStrategySgDaily.snapshot_date.desc())
        .first()
    )
    if not row or row.sg is None:
        return None

    st = GlobalStrategyMacroState.query.get(1)
    mode = str((st.usa_score_mode if st else None) or "vix").strip().lower()
    if mode not in ("vix", "spy"):
        mode = "vix"
    usa_label = "^VIX" if mode == "vix" else "SPY"
    us_series = "vix" if mode == "vix" else "spy"

    def _r(x: Any) -> Optional[float]:
        if x is None:
            return None
        try:
            return round(float(x), 2)
        except (TypeError, ValueError):
            return None

    def _points(sk: str) -> list[dict[str, Any]]:
        m = GlobalStrategyMacroDaily.query.filter_by(series_key=sk).first()
        return list(m.data_points) if m and m.data_points else []

    s_us = _r(row.s_us)
    s_eu = _r(row.s_eu)
    s_as = _r(row.s_as)

    us_row = GlobalStrategyMacroDaily.query.filter_by(series_key=us_series).first()
    us_ticker = us_row.yahoo_ticker if us_row and us_row.yahoo_ticker else ("^VIX" if mode == "vix" else "SPY")

    regions: dict[str, Any] = {}
    rb_us = _region_block(
        key="us",
        label="USA",
        series_key=us_series,
        ticker=us_ticker,
        score=s_us,
        points=_points(us_series),
        hue="indigo",
    )
    if rb_us:
        regions["us"] = rb_us
    rb_eu = _region_block(
        key="eu",
        label="Europa",
        series_key="fez",
        ticker="FEZ",
        score=s_eu,
        points=_points("fez"),
        hue="amber",
    )
    if rb_eu:
        regions["eu"] = rb_eu
    rb_as = _region_block(
        key="asia",
        label="Asia",
        series_key="asia_hk",
        ticker="3188.HK",
        score=s_as,
        points=_points("asia_hk"),
        hue="teal",
    )
    if rb_as:
        regions["asia"] = rb_as

    sg_val = round(float(row.sg), 2)
    return {
        "sg": sg_val,
        "s_us": s_us,
        "s_eu": s_eu,
        "s_as": s_as,
        "snapshot_date": row.snapshot_date.isoformat() if row.snapshot_date else None,
        "indicator_as_of": row.indicator_as_of.isoformat() if row.indicator_as_of else None,
        "usa_score_mode": mode,
        "usa_label": usa_label,
        "regions": regions,
        "sg_context": sg_context_payload(sg_val),
    }
