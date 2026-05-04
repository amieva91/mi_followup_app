"""
Refresco periódico de datos de consenso de analistas (quoteSummary / financialData).
Cron diario global: mismos activos que el polling (cartera + watchlist + metales dashboard),
en orden por id ascendente (igual que la cola de activos en price-poll-one).

Se refresca si el consenso está vacío (tres campos nulos) o si la última actualización
de consenso no existe o es anterior a hace STALE_DAYS días (datos con más de STALE_DAYS días).
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Collection, Dict, Optional

from app import db
from app.models.asset import Asset
from app.services.market_data.services.price_updater import DELAY_BETWEEN_REQUESTS, PriceUpdater
from app.services.price_polling_service import POLLABLE_TYPES, get_assets_to_poll, _invalidate_caches_for_asset

STALE_DAYS = 90
_log = logging.getLogger(__name__)


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


def run_refresh(only_asset_ids: Optional[Collection[int]] = None) -> Dict[str, Any]:
    """
    Primero se determina el subconjunto pollable que necesita refresco (vacío o consenso
    con más de STALE_DAYS días); solo esos reciben llamadas a Yahoo.

    Args:
        only_asset_ids: Si se indica (p. ej. activos tocados por un CSV), solo se consideran
            esos ids entre los pollables. None = todos los pollables (cron global).
    """
    pollable = get_assets_to_poll()
    if not pollable:
        return {"ok": True, "processed": 0, "success": 0, "failed": 0, "message": "Sin activos pollables"}

    if only_asset_ids is not None:
        allow = {int(x) for x in only_asset_ids}
        if not allow:
            return {
                "ok": True,
                "processed": 0,
                "success": 0,
                "failed": 0,
                "message": "Sin ids de activo para revisar",
            }
        pollable = [a for a in pollable if a.id in allow]
        if not pollable:
            return {
                "ok": True,
                "processed": 0,
                "success": 0,
                "failed": 0,
                "message": "Ningún activo del lote está en la cola pollable",
            }

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


def schedule_stale_analyst_consensus_refresh(app, only_asset_ids: Optional[Collection[int]] = None) -> None:
    """
    Encola el mismo trabajo que el cron en un hilo daemon: no bloquea la respuesta HTTP
    (p. ej. tras importar CSV). Si only_asset_ids está vacío, no hace nada.
    """
    if only_asset_ids is not None:
        ids = frozenset(int(x) for x in only_asset_ids)
        if not ids:
            return
    else:
        ids = None

    def worker():
        with app.app_context():
            try:
                summary = run_refresh(only_asset_ids=ids)
                _log.info("%s", summary.get("message", summary))
            except Exception:
                _log.exception("schedule_stale_analyst_consensus_refresh: error en segundo plano")

    threading.Thread(
        target=worker,
        name="analyst-consensus-refresh",
        daemon=True,
    ).start()


def schedule_immediate_market_data_for_watchlist_asset(app, asset_id: int) -> None:
    """
    Tras añadir un activo a la watchlist: en segundo plano, mismo trabajo que el cron
    de consenso (Chart + quoteSummary cuando Yahoo autentica). Si no hay éxito, al menos
    actualiza precio vía Chart API como price-poll-one.
    """
    aid = int(asset_id)

    def worker():
        with app.app_context():
            try:
                asset = Asset.query.get(aid)
                if (
                    not asset
                    or not asset.yahoo_ticker
                    or (asset.asset_type or "") not in POLLABLE_TYPES
                ):
                    return
                summary = run_refresh(only_asset_ids=[aid])
                if summary.get("success", 0) >= 1:
                    return
                db.session.expire_all()
                asset = Asset.query.get(aid)
                if not asset or not asset.yahoo_ticker:
                    return
                updater = PriceUpdater()
                if updater.update_single_asset_price_only(asset):
                    try:
                        db.session.commit()
                        _invalidate_caches_for_asset(aid)
                    except Exception:
                        db.session.rollback()
            except Exception:
                _log.exception("schedule_immediate_market_data_for_watchlist_asset: error en segundo plano")

    threading.Thread(
        target=worker,
        name="watchlist-immediate-market",
        daemon=True,
    ).start()
