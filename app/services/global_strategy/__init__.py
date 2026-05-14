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
from app.services.global_strategy.sg_from_macro import (
    SgMacroComponents,
    compute_sg_from_macro_snapshot,
    upsert_sg_daily_for_all_stock_users,
)
from app.services.global_strategy.sg_indicator_dates import indicator_as_of_minimum

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
    "SgMacroComponents",
    "compute_sg_from_macro_snapshot",
    "upsert_sg_daily_for_all_stock_users",
    "indicator_as_of_minimum",
]
