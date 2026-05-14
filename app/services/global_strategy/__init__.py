"""Motor de estrategia global (scores, RO, persistencia de SG)."""

from app.services.global_strategy.score_math import (
    ratio_objetivo,
    score_asia_price_vs_ma200,
    score_eu_price_vs_ma200,
    score_global,
    score_price_vs_ma200,
    score_usa_spy_vs_ma200,
    score_usa_vix_vs_ma200,
    score_usa_yield_curve_spread_pct,
    umbral_objetivo_mercado,
)
from app.services.global_strategy.sg_history import upsert_sg_daily_atomic

__all__ = [
    "ratio_objetivo",
    "score_asia_price_vs_ma200",
    "score_eu_price_vs_ma200",
    "score_global",
    "score_price_vs_ma200",
    "score_usa_spy_vs_ma200",
    "score_usa_vix_vs_ma200",
    "score_usa_yield_curve_spread_pct",
    "umbral_objetivo_mercado",
    "upsert_sg_daily_atomic",
]
