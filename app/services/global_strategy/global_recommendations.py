"""
Recomendaciones de estrategia global (§5 motor): oportunidad, riesgo, confirmación.

Solo lista (sin email). Prioridad: riesgo > oportunidad > confirmación.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.global_strategy_sg_daily import GlobalStrategySgDaily
from app.services.global_strategy.co_ratio_display import (
    format_pct_for_message,
    investment_and_liquidity_pct,
)
from app.services.global_strategy.score_math import umbral_objetivo_mercado
from app.services.global_strategy.sg_trend_math import mean5_sg_falling
from app.services.net_worth_service import _get_broker_value_at_date


def _round_eur(x: float) -> int:
    return int(round(float(x)))


def _load_sg_series(user_id: int, limit: int = 5) -> list[GlobalStrategySgDaily]:
    return (
        GlobalStrategySgDaily.query.filter_by(user_id=user_id)
        .order_by(GlobalStrategySgDaily.snapshot_date.desc())
        .limit(limit)
        .all()
    )


@dataclass(frozen=True)
class _BrokerMacroContext:
    co: float
    ir: float
    sg: float
    uom: float
    rows: list[GlobalStrategySgDaily]


def _load_broker_macro_context(user_id: int) -> _BrokerMacroContext | None:
    rows = _load_sg_series(user_id, 5)
    if not rows:
        return None
    sg = float(rows[0].sg)
    bd = _get_broker_value_at_date(user_id, datetime.now(), use_current_prices=True)
    co = float(bd.get("total_value") or 0.0)
    ir = float(bd.get("holdings_value") or 0.0)
    uom = umbral_objetivo_mercado(co, sg)
    return _BrokerMacroContext(co=co, ir=ir, sg=sg, uom=uom, rows=rows)


def build_global_strategy_recommendations(user_id: int) -> list[Any]:
    """Devuelve instancias ``Recommendation`` (import diferido para evitar ciclos)."""
    from app.services.recommendation_service import Recommendation
    from flask import current_app

    ctx = _load_broker_macro_context(user_id)
    if ctx is None:
        return []

    show_confirm = bool(current_app.config.get("GLOBAL_STRATEGY_INCLUDE_CONFIRMATION_RECOMMENDATION", True))

    sg_vals = [float(r.sg) for r in ctx.rows]
    ir, uom, sg = ctx.ir, ctx.uom, ctx.sg

    recs: list[Any] = []

    score_bajando = mean5_sg_falling(sg, sg_vals)

    # B — riesgo (prioridad alta)
    if score_bajando and uom > 0 and ir > 1.30 * uom:
        reduc = ir - 1.1 * uom
        if reduc > 0:
            amt = _round_eur(reduc)
            recs.append(
                Recommendation(
                    priority="high",
                    icon="⚠️",
                    title="Alerta de deterioro macro",
                    text=(
                        "Tu nivel de apalancamiento supera el límite de seguridad "
                        f"(margen del 30% sobre el objetivo). Debes reducir posiciones por valor de {amt} € "
                        "para proteger tu Capital Operativo."
                    ),
                    action="Revisa tu cartera y el score global",
                    source="global_strategy",
                )
            )

    # A — oportunidad
    if not recs and uom > 0 and sg > 2.0 and ir < 0.5 * uom:
        add = uom - ir
        if add > 0:
            amt = _round_eur(add)
            recs.append(
                Recommendation(
                    priority="medium",
                    icon="📈",
                    title="Fuerte viento a favor",
                    text=(
                        "Tu exposición está un 50% por debajo del umbral recomendado. "
                        f"Puedes aumentar tu posición en {amt} € adicionales para optimizar tu ratio según el "
                        "Capital Operativo actual."
                    ),
                    action="Revisar exposición en Portfolio",
                    source="global_strategy",
                )
            )

    # C — confirmación (solo si no hay A ni B y banda de IR razonable)
    if not recs and show_confirm and uom > 0:
        low, high = 0.5 * uom, 1.30 * uom
        entre = low <= ir <= high
        if entre:
            inv_pct, liq_pct = investment_and_liquidity_pct(ctx.co, ir)
            recs.append(
                Recommendation(
                    priority="low",
                    icon="✅",
                    title="Situación actual del mercado",
                    text=(
                        f"Tus ratios de inversión ({format_pct_for_message(inv_pct)}) y liquidez "
                        f"({format_pct_for_message(liq_pct)}) actuales con respecto a tu Capital Operativo "
                        "son adecuados."
                    ),
                    action=None,
                    source="global_strategy",
                )
            )

    return recs


def append_global_strategy_recommendations(user_id: int, recs: list[Any]) -> None:
    """Añade al listado mutable ``recs`` (mismo tipo que ``RecommendationService``)."""
    for r in build_global_strategy_recommendations(user_id):
        recs.append(r)
