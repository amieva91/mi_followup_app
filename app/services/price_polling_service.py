"""
Servicio de polling de precios en segundo plano.
Actualiza 1 elemento por minuto (rotación): activos (cartera/watchlist) + benchmarks globales.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from app import db
from app.models.asset import Asset
from app.models.benchmark_global_quote import BenchmarkGlobalQuote
from app.models.portfolio import PortfolioHolding
from app.models.watchlist import Watchlist
from app.models.price_polling_state import PricePollingState
from app.services.metrics.benchmark_comparison import BENCHMARKS

# Tipos de activo que se pueden actualizar vía Yahoo Chart API
POLLABLE_TYPES = ("Stock", "ETF", "Crypto", "Commodity")


@dataclass(frozen=True)
class _PollAsset:
    asset: Asset


@dataclass(frozen=True)
class _PollBenchmark:
    name: str
    ticker: str


PollSlot = Union[_PollAsset, _PollBenchmark]


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
    rows = (
        db.session.query(Asset.id)
        .filter(
            Asset.id.in_(all_ids),
            Asset.last_price_update.isnot(None),
            Asset.last_price_update > since,
        )
        .all()
    )
    return [r[0] for r in rows]


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

    holding_ids = (
        db.session.query(PortfolioHolding.asset_id)
        .filter(PortfolioHolding.quantity > 0)
        .distinct()
        .all()
    )
    holding_ids = {r[0] for r in holding_ids}

    watchlist_ids = db.session.query(Watchlist.asset_id).distinct().all()
    watchlist_ids = {r[0] for r in watchlist_ids}

    all_ids = holding_ids | watchlist_ids

    # Dashboard commodities: incluir aunque no estén en holdings/watchlist
    # (GC=F, SI=F, BZ=F). Si no existen todavía, se crearán al cargar el dashboard.
    dash_syms = {"GC=F", "SI=F", "BZ=F"}
    dash_ids = db.session.query(Asset.id).filter(Asset.symbol.in_(dash_syms)).all()
    all_ids |= {r[0] for r in dash_ids}
    if not all_ids:
        return []

    delisted = set(get_delisted_asset_ids())
    ids_to_poll = [i for i in all_ids if i not in delisted]

    assets = (
        Asset.query.filter(Asset.id.in_(ids_to_poll))
        .filter(Asset.asset_type.in_(POLLABLE_TYPES))
        .filter(Asset.symbol.isnot(None))
        .all()
    )

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


def build_poll_queue() -> List[PollSlot]:
    """Activos ordenados por id + benchmarks (orden de inserción en BENCHMARKS)."""
    assets = get_assets_to_poll()
    slots: List[PollSlot] = [_PollAsset(a) for a in sorted(assets, key=lambda x: x.id)]
    for name, ticker in BENCHMARKS.items():
        slots.append(_PollBenchmark(name=name, ticker=ticker))
    return slots


def _poll_benchmark_slot(slot: _PollBenchmark) -> bool:
    from app.services.market_data.services.price_updater import PriceUpdater

    q = PriceUpdater.fetch_yahoo_chart_quote(slot.ticker)
    if not q or q.get("regular_market_price") is None:
        return False

    row = BenchmarkGlobalQuote.query.filter_by(benchmark_name=slot.name).first()
    if not row:
        row = BenchmarkGlobalQuote(benchmark_name=slot.name, yahoo_ticker=slot.ticker, updated_at=datetime.utcnow())
        db.session.add(row)
    row.yahoo_ticker = slot.ticker
    row.regular_market_price = q["regular_market_price"]
    row.previous_close = q.get("previous_close")
    row.day_change_percent = q.get("day_change_percent")
    row.updated_at = datetime.utcnow()
    db.session.commit()
    return True


def run_poll_one() -> Optional[Dict[str, Any]]:
    """
    Ejecuta una iteración del job: un slot de la cola (activo o benchmark).
    Returns:
        {"kind": "asset", "asset_id": int} | {"kind": "benchmark", "name": str, "ticker": str} | None
    """
    queue = build_poll_queue()
    if not queue:
        return None

    state = PricePollingState.query.get(1)
    if not state:
        state = PricePollingState(id=1, last_asset_index=0)
        db.session.add(state)
        db.session.flush()

    idx = (state.last_asset_index + 1) % len(queue)
    slot = queue[idx]

    from app.services.market_data.services.price_updater import PriceUpdater

    updater = PriceUpdater()
    state.last_asset_index = idx
    state.last_run_at = datetime.utcnow()

    if isinstance(slot, _PollAsset):
        ok = updater.update_single_asset_price_only(slot.asset)
        state.last_updated_asset_id = slot.asset.id if ok else state.last_updated_asset_id
        state.updated_at = datetime.utcnow()
        db.session.commit()
        if ok:
            _invalidate_caches_for_asset(slot.asset.id)
            return {"kind": "asset", "asset_id": slot.asset.id}
        return None

    ok = _poll_benchmark_slot(slot)
    state.last_updated_asset_id = None
    state.updated_at = datetime.utcnow()
    db.session.commit()
    if ok:
        return {"kind": "benchmark", "name": slot.name, "ticker": slot.ticker}
    return None


def _invalidate_caches_for_asset(asset_id: int) -> None:
    """
    Caches que dependen del precio del activo.
    Benchmarks: solo dirty_now (no borrar serie HIST global en caché por usuario).
    """
    from app.services.portfolio_evolution_cache import PortfolioEvolutionCacheService
    from app.services.portfolio_benchmarks_cache import PortfolioBenchmarksCacheService

    user_ids = set()
    for row in db.session.query(PortfolioHolding.user_id).filter(
        PortfolioHolding.asset_id == asset_id,
        PortfolioHolding.quantity > 0,
    ).distinct().all():
        user_ids.add(row[0])
    for row in db.session.query(Watchlist.user_id).filter(Watchlist.asset_id == asset_id).distinct().all():
        user_ids.add(row[0])

    for uid in user_ids:
        PortfolioEvolutionCacheService.invalidate(uid)
        PortfolioBenchmarksCacheService.touch_for_prices_update(uid)
        from app.services.dashboard_summary_cache import DashboardSummaryCacheService

        DashboardSummaryCacheService.recompute_current_from_cache(uid)
