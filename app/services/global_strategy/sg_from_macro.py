r"""
Cálculo de s_US, s_EU, s_AS y SG desde `GlobalStrategyMacroService.snapshot_for_scores`
y persistencia diaria por usuario (módulo `stock`).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Optional

from app.models.user import User
from app.services.global_strategy.macro_daily_service import GlobalStrategyMacroService
from app.services.global_strategy.score_math import (
    score_asia_price_vs_ma200,
    score_eu_price_vs_ma200,
    score_global,
    score_usa_spy_vs_ma200,
    score_usa_vix_vs_ma200,
)
from app.services.global_strategy.sg_history import upsert_sg_daily_atomic
from app.services.global_strategy.sg_indicator_dates import indicator_as_of_minimum


@dataclass(frozen=True)
class SgMacroComponents:
    s_us: float
    s_eu: float
    s_as: float
    sg: float
    indicator_as_of: date


def compute_sg_from_macro_snapshot(snap: dict[str, Any]) -> Optional[SgMacroComponents]:
    """
    Devuelve componentes y SG si hay close + MA200 para USA (VIX o SPY), FEZ y Asia.
    """
    mode = str(snap.get("usa_score_mode") or "vix").strip().lower()
    if mode not in ("vix", "spy"):
        mode = "vix"

    ser = snap.get("series") or {}

    if mode == "spy":
        usa = ser.get("spy") or {}
        s_us = _score_price_ma200(usa, score_usa_spy_vs_ma200)
    else:
        usa = ser.get("vix") or {}
        s_us = _score_vix(usa)

    s_eu = _score_price_ma200(ser.get("fez") or {}, score_eu_price_vs_ma200)
    s_as = _score_price_ma200(ser.get("asia_hk") or {}, score_asia_price_vs_ma200)

    if s_us is None or s_eu is None or s_as is None:
        return None

    sg = score_global(s_us, s_eu, s_as)
    ind = indicator_as_of_minimum(snap)
    if ind is None:
        return None
    return SgMacroComponents(s_us=s_us, s_eu=s_eu, s_as=s_as, sg=sg, indicator_as_of=ind)


def _score_price_ma200(
    payload: dict[str, Any],
    fn: Callable[[float, float], float],
) -> Optional[float]:
    c = payload.get("close")
    m = payload.get("ma200")
    if c is None or m is None:
        return None
    try:
        return float(fn(float(c), float(m)))
    except (TypeError, ValueError):
        return None


def _score_vix(payload: dict[str, Any]) -> Optional[float]:
    return _score_price_ma200(payload, score_usa_vix_vs_ma200)


def upsert_sg_daily_for_all_stock_users(
    snap: Optional[dict[str, Any]] = None,
    *,
    snapshot_date: Optional[date] = None,
) -> dict[str, Any]:
    """
    Calcula SG desde el snapshot macro y hace upsert para cada usuario activo con módulo stock.
    ``snapshot_date`` por defecto: día UTC actual.
    """
    if snap is None:
        snap = GlobalStrategyMacroService.snapshot_for_scores()
    comp = compute_sg_from_macro_snapshot(snap)
    if not comp:
        return {"ok": False, "users_updated": 0, "reason": "insufficient_macro_data"}

    day = snapshot_date or datetime.utcnow().date()
    users = User.query.filter(User.is_active.is_(True)).all()
    n = 0
    for u in users:
        if not u.has_module("stock"):
            continue
        upsert_sg_daily_atomic(
            u.id,
            day,
            comp.sg,
            s_us=comp.s_us,
            s_eu=comp.s_eu,
            s_as=comp.s_as,
            indicator_as_of=comp.indicator_as_of,
            fill_weekend_from_friday=False,
        )
        n += 1

    return {
        "ok": True,
        "users_updated": n,
        "snapshot_date": day.isoformat(),
        "sg": comp.sg,
        "s_us": comp.s_us,
        "s_eu": comp.s_eu,
        "s_as": comp.s_as,
        "indicator_as_of": comp.indicator_as_of.isoformat(),
    }
