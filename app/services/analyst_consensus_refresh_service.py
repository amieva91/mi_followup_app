"""
Refresco periódico de datos de consenso de analistas (quoteSummary / financialData).
Cron diario global: mismos activos que el polling (cartera + watchlist + metales dashboard),
en orden por id ascendente (igual que la cola de activos en price-poll-one).

Se refresca si el consenso está vacío (tres campos nulos) o si la última actualización
de consenso no existe o es anterior a hace STALE_DAYS días (datos con más de STALE_DAYS días).
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Dict

from app import db
from app.models.asset import Asset
from app.services.market_data.services.price_updater import DELAY_BETWEEN_REQUESTS, PriceUpdater
from app.services.price_polling_service import get_assets_to_poll

STALE_DAYS = 90


def _needs_analyst_refresh(asset: Asset, threshold: datetime) -> bool:
    """True si conviene volver a llamar a quoteSummary para este activo."""
    empty = (
        asset.recommendation_key is None
        and asset.number_of_analyst_opinions is None
        and asset.target_mean_price is None
    )
    # Sin fecha, o fecha de consenso más antigua que (ahora - STALE_DAYS)
    consensus_too_old = (
        asset.analyst_consensus_updated_at is None
        or asset.analyst_consensus_updated_at < threshold
    )
    return empty or consensus_too_old


def run_refresh() -> Dict[str, Any]:
    """
    Autentica una vez con Yahoo y actualiza todos los activos pollables que lo necesiten,
    en orden por id (como build_poll_queue para activos).
    """
    pollable = get_assets_to_poll()
    if not pollable:
        return {"ok": True, "processed": 0, "success": 0, "failed": 0, "message": "Sin activos pollables"}

    threshold = datetime.utcnow() - timedelta(days=STALE_DAYS)
    stale_assets = [a for a in sorted(pollable, key=lambda x: x.id) if _needs_analyst_refresh(a, threshold)]
    if not stale_assets:
        return {"ok": True, "processed": 0, "success": 0, "failed": 0, "message": "Ningún activo requiere refresco de consenso"}

    updater = PriceUpdater()
    auth_ok = updater._authenticate_yahoo()
    if not auth_ok:
        return {
            "ok": False,
            "processed": 0,
            "success": 0,
            "failed": len(stale_assets),
            "message": "No se pudo autenticar con Yahoo; consenso no actualizado",
        }

    success = 0
    failed = 0
    for i, asset in enumerate(stale_assets):
        if not asset.yahoo_ticker:
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
        "processed": len(stale_assets),
        "success": success,
        "failed": failed,
        "message": f"Refresco consenso: {success} ok, {failed} fallidos (total a procesar: {len(stale_assets)})",
    }
