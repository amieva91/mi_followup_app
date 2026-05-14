"""
Payload de dashboard para el widget de estrategia global (SG + scores regionales).

Solo hay datos cuando el usuario tiene módulo `stock` y existe al menos una fila
en `global_strategy_sg_daily` (poblada por el job macro diario).
"""
from __future__ import annotations

from typing import Any, Optional

from app.models import User
from app.models.global_strategy_macro_daily import GlobalStrategyMacroState
from app.models.global_strategy_sg_daily import GlobalStrategySgDaily


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

    def _r(x: Any) -> Optional[float]:
        if x is None:
            return None
        try:
            return round(float(x), 2)
        except (TypeError, ValueError):
            return None

    return {
        "sg": round(float(row.sg), 2),
        "s_us": _r(row.s_us),
        "s_eu": _r(row.s_eu),
        "s_as": _r(row.s_as),
        "snapshot_date": row.snapshot_date.isoformat() if row.snapshot_date else None,
        "indicator_as_of": row.indicator_as_of.isoformat() if row.indicator_as_of else None,
        "usa_score_mode": mode,
        "usa_label": usa_label,
    }
