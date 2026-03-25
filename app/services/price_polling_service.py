"""
Servicio de polling de precios en segundo plano.
Actualiza 1 activo por minuto (rotación) para respetar límites de Yahoo (~2000/día).
"""
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app import db
from app.models.asset import Asset
from app.models.portfolio import PortfolioHolding
from app.models.watchlist import Watchlist
from app.models.price_polling_state import PricePollingState


# Tipos de activo que se pueden actualizar vía Yahoo Chart API
POLLABLE_TYPES = ('Stock', 'ETF', 'Crypto', 'Commodity')


def get_updated_asset_ids_for_user(user_id: int, since: datetime) -> List[int]:
    """
    IDs de activos del usuario (portfolio + watchlist) cuyo precio se actualizó
    después de `since` (útil para efecto flash en la UI).
    """
    holding_ids = db.session.query(PortfolioHolding.asset_id).filter(
        PortfolioHolding.user_id == user_id,
        PortfolioHolding.quantity > 0,
    ).distinct().all()
    watch_ids = db.session.query(Watchlist.asset_id).filter(
        Watchlist.user_id == user_id,
    ).distinct().all()
    all_ids = {r[0] for r in holding_ids} | {r[0] for r in watch_ids}
    if not all_ids:
        return []
    rows = db.session.query(Asset.id).filter(
        Asset.id.in_(all_ids),
        Asset.last_price_update.isnot(None),
        Asset.last_price_update > since,
    ).all()
    return [r[0] for r in rows]


def run_poll_one() -> Optional[int]:
    """
    Ejecuta una iteración del job: actualiza 1 activo y rota el índice.
    Returns: asset_id actualizado, o None si no hubo actualización.
    """
    assets = get_assets_to_poll()
    if not assets:
        return None

    state = PricePollingState.query.get(1)
    if not state:
        state = PricePollingState(id=1, last_asset_index=0)
        db.session.add(state)
        db.session.flush()

    idx = (state.last_asset_index + 1) % len(assets)
    asset = assets[idx]

    from app.services.market_data.services.price_updater import PriceUpdater
    updater = PriceUpdater()
    ok = updater.update_single_asset_price_only(asset)

    state.last_asset_index = idx
    state.last_run_at = datetime.utcnow()
    state.last_updated_asset_id = asset.id if ok else state.last_updated_asset_id
    state.updated_at = datetime.utcnow()
    db.session.commit()

    if ok:
        _invalidate_caches_for_asset(asset.id)
        return asset.id
    return None


def _invalidate_caches_for_asset(asset_id: int) -> None:
    """Invalida caches que dependen del precio (evolution, benchmarks, dashboard touch)."""
    from app.models import User
    from app.services.portfolio_evolution_cache import PortfolioEvolutionCacheService
    from app.services.portfolio_benchmarks_cache import PortfolioBenchmarksCacheService

    # Usuarios con este asset en portfolio o watchlist
    user_ids = set()
    for row in db.session.query(PortfolioHolding.user_id).filter(
        PortfolioHolding.asset_id == asset_id,
        PortfolioHolding.quantity > 0,
    ).distinct().all():
        user_ids.add(row[0])
    for row in db.session.query(Watchlist.user_id).filter(
        Watchlist.asset_id == asset_id,
    ).distinct().all():
        user_ids.add(row[0])

    for uid in user_ids:
        PortfolioEvolutionCacheService.invalidate(uid)
        PortfolioBenchmarksCacheService.invalidate(uid)
        # Dashboard: touch NOW (recompute_current) para que el próximo poll tenga datos frescos
        from app.services.dashboard_summary_cache import DashboardSummaryCacheService
        DashboardSummaryCacheService.recompute_current_from_cache(uid)


def get_assets_to_poll() -> List[Asset]:
    """
    Lista única de assets a actualizar en el job de polling.

    - Holdings con quantity > 0 (cualquier usuario)
    - Watchlist de cualquier usuario que no estén ya en holdings
    - Solo con yahoo_ticker válido
    - Excluye delisted
    - Sin duplicados por asset_id
    """
    from app.services.delisting_reconciliation_service import get_delisted_asset_ids

    # 1) Asset IDs con holdings > 0
    holding_ids = (
        db.session.query(PortfolioHolding.asset_id)
        .filter(PortfolioHolding.quantity > 0)
        .distinct()
        .all()
    )
    holding_ids = {r[0] for r in holding_ids}

    # 2) Asset IDs en watchlist (union con holdings, sin duplicados)
    watchlist_ids = (
        db.session.query(Watchlist.asset_id)
        .distinct()
        .all()
    )
    watchlist_ids = {r[0] for r in watchlist_ids}

    all_ids = holding_ids | watchlist_ids  # Union: holdings + watchlist sin duplicados
    if not all_ids:
        return []

    delisted = set(get_delisted_asset_ids())
    ids_to_poll = [i for i in all_ids if i not in delisted]

    assets = (
        Asset.query
        .filter(Asset.id.in_(ids_to_poll))
        .filter(Asset.asset_type.in_(POLLABLE_TYPES))
        .filter(Asset.symbol.isnot(None))
        .all()
    )

    # Filtrar por yahoo_ticker válido (symbol + suffix)
    result = []
    seen = set()
    for a in assets:
        if a.id in seen:
            continue
        ticker = a.yahoo_ticker
        if not ticker or not ticker.strip():
            continue
        seen.add(a.id)
        result.append(a)

    return result
