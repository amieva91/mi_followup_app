"""
Catálogo Sector → Industria para clasificación de valoración (watchlist).

Origen: activos en watchlist del usuario ∪ cartera (holdings con cantidad > 0).
"""
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from app import db
from app.models import Asset, PortfolioHolding, Watchlist


def get_sector_industry_catalog_for_user(user_id: int) -> Dict[str, Any]:
    """
    Devuelve pares distintos (sector, industry) no vacíos para los activos
    relevantes del usuario.

    Returns:
        {
          "sectors": [str, ...] ordenados,
          "by_sector": { sector: [industria, ...] } industrias ordenadas
        }
    """
    asset_ids: Set[int] = set()
    for (aid,) in (
        db.session.query(Watchlist.asset_id)
        .filter(Watchlist.user_id == user_id)
        .distinct()
        .all()
    ):
        if aid is not None:
            asset_ids.add(aid)
    for (aid,) in (
        db.session.query(PortfolioHolding.asset_id)
        .filter(
            PortfolioHolding.user_id == user_id,
            PortfolioHolding.quantity > 0,
        )
        .distinct()
        .all()
    ):
        if aid is not None:
            asset_ids.add(aid)

    if not asset_ids:
        return {"sectors": [], "by_sector": {}}

    rows: List[Tuple[str, str]] = (
        db.session.query(Asset.sector, Asset.industry)
        .filter(Asset.id.in_(asset_ids))
        .filter(
            Asset.sector.isnot(None),
            Asset.industry.isnot(None),
        )
        .distinct()
        .all()
    )

    by_sector: Dict[str, Set[str]] = {}
    for sector, industry in rows:
        s = (sector or "").strip()
        i = (industry or "").strip()
        if not s or not i:
            continue
        by_sector.setdefault(s, set()).add(i)

    sectors_sorted = sorted(by_sector.keys(), key=lambda x: x.lower())
    by_sector_out = {
        s: sorted(by_sector[s], key=lambda x: x.lower()) for s in sectors_sorted
    }
    return {"sectors": sectors_sorted, "by_sector": by_sector_out}
