"""
Refresco periódico de datos de consenso de analistas (quoteSummary / financialData).
Pensado para cron diario: activos en cartera/watchlist con consenso vacío o antiguo (>90 días).
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

from app import db
from app.models.asset import Asset
from app.services.market_data.services.price_updater import DELAY_BETWEEN_REQUESTS, PriceUpdater
from app.services.price_polling_service import get_assets_to_poll

STALE_DAYS = 90


def _asset_ids_needing_refresh(pollable: List[Asset], threshold: datetime) -> List[int]:
    """IDs de activos pollables que deben pasar por _update_single_asset (con quoteSummary si hay auth)."""
    ids: List[int] = []
    for a in pollable:
        empty = (
            a.recommendation_key is None
            and a.number_of_analyst_opinions is None
            and a.target_mean_price is None
        )
        stale_date = a.analyst_consensus_updated_at is None or a.analyst_consensus_updated_at < threshold
        if empty or stale_date:
            ids.append(a.id)
    return ids


def run_refresh(limit: int = 30) -> Dict[str, Any]:
    """
    Autentica una vez con Yahoo y actualiza hasta ``limit`` activos (orden por id).
    Returns dict con contadores y mensajes breves.
    """
    limit = max(1, min(int(limit), 500))
    pollable = get_assets_to_poll()
    if not pollable:
        return {"ok": True, "processed": 0, "success": 0, "failed": 0, "message": "Sin activos pollables"}

    threshold = datetime.utcnow() - timedelta(days=STALE_DAYS)
    stale_ids = _asset_ids_needing_refresh(pollable, threshold)
    if not stale_ids:
        return {"ok": True, "processed": 0, "success": 0, "failed": 0, "message": "Ningún activo requiere refresco de consenso"}

    stale_ids.sort()
    to_run = stale_ids[:limit]
    assets = Asset.query.filter(Asset.id.in_(to_run)).all()
    by_id = {a.id: a for a in assets}

    updater = PriceUpdater()
    auth_ok = updater._authenticate_yahoo()
    if not auth_ok:
        return {
            "ok": False,
            "processed": 0,
            "success": 0,
            "failed": len(to_run),
            "message": "No se pudo autenticar con Yahoo; consenso no actualizado",
        }

    success = 0
    failed = 0
    for i, aid in enumerate(to_run):
        asset = by_id.get(aid)
        if not asset or not asset.yahoo_ticker:
            failed += 1
            continue
        if i > 0:
            time.sleep(DELAY_BETWEEN_REQUESTS)
        try:
            if updater._update_single_asset(asset):
                try:
                    db.session.commit()
                    success += 1
                except Exception:
                    db.session.rollback()
                    failed += 1
            else:
                db.session.rollback()
                failed += 1
        except Exception:
            db.session.rollback()
            failed += 1

    return {
        "ok": True,
        "processed": len(to_run),
        "success": success,
        "failed": failed,
        "message": f"Refresco consenso: {success} ok, {failed} fallidos (lote máx. {limit})",
    }
