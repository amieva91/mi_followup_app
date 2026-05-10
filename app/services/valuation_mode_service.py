"""
Resolución del modo de valoración watchlist (general / banks / realestate).

Ver docs/implementaciones/WATCHLIST_VALORACION_PLAN_IMPLEMENTACION.md §3–4.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    from app.models import Asset, WatchlistConfig

ValuationMode = Literal["general", "banks", "realestate"]


def _norm_segment(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _pair_in_rules(
    sector: Optional[str], industry: Optional[str], pairs: list
) -> bool:
    if not sector or not industry:
        return False
    ns, ni = _norm_segment(sector), _norm_segment(industry)
    for p in pairs or []:
        if not isinstance(p, dict):
            continue
        ps = _norm_segment(p.get("sector"))
        pi = _norm_segment(p.get("industry"))
        if ps == ns and pi == ni:
            return True
    return False


def resolve_valuation_mode(
    asset: Optional["Asset"],
    watchlist_config: Optional["WatchlistConfig"],
) -> ValuationMode:
    """
    Orden: banks si coincide; realestate si coincide; empate banks+realestate → banks;
    sin sector/industria en asset → general; sin config → general.
    """
    if asset is None:
        return "general"
    sector, industry = asset.sector, asset.industry
    if not sector or not industry:
        return "general"

    if watchlist_config is None:
        return "general"

    rules = watchlist_config.get_valuation_sector_rules()
    banks = rules.get("banks") or []
    re_list = rules.get("realestate") or []

    in_banks = _pair_in_rules(sector, industry, banks)
    in_re = _pair_in_rules(sector, industry, re_list)

    if in_banks and in_re:
        return "banks"
    if in_banks:
        return "banks"
    if in_re:
        return "realestate"
    return "general"
