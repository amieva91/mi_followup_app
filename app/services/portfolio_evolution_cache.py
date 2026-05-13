"""
Servicio de caché HIST/NOW para:
- /portfolio/performance (evolución del portfolio para Chart.js)

Objetivo:
1) Rebuild completo (HIST) solo cuando cambia "pasado" (transacciones de fechas pasadas, etc.)
2) Recalcular solo el tramo actual (NOW) cuando cambia "hoy", y hacerlo dentro del polling (~30s)
3) Un único snapshot guarda daily + weekly + monthly para no reconstruir al cambiar frecuencia en la UI
"""

from __future__ import annotations

import copy
import os
from contextlib import contextmanager
from datetime import date, datetime, time, timezone
from typing import Any, Iterator

from app import db
from app.models.portfolio_evolution_cache import PortfolioEvolutionCache
from app.services.metrics.portfolio_evolution import PortfolioEvolutionService
from app.services.metrics.portfolio_valuation import PortfolioValuation
from app.services.metrics.modified_dietz import ModifiedDietzCalculator

EVOLUTION_FREQUENCIES: tuple[str, ...] = ("daily", "weekly", "monthly")


def _utc_iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _touch_meta_defaults(meta: dict[str, Any]) -> dict[str, Any]:
    meta = dict(meta or {})
    meta.setdefault("needs_full_rebuild", False)
    meta.setdefault("dirty_now", False)
    meta.setdefault("hist_end_date", None)  # YYYY-MM-DD
    meta.setdefault("frequency", None)  # "all" cuando hay bundle multi-frecuencia
    meta.setdefault("version", 0)
    meta.setdefault("_now_cached_at", None)
    meta.setdefault("sync_type", None)  # "HIST+NOW" | "NOW" | null
    return meta


def _normalize_frequency(frequency: str) -> str:
    if frequency in EVOLUTION_FREQUENCIES:
        return frequency
    return "weekly"


def _is_multi_frequency_bundle(cached: dict[str, Any]) -> bool:
    evs = cached.get("evolutions")
    if not isinstance(evs, dict):
        return False
    return all(f in evs and isinstance(evs[f], dict) for f in EVOLUTION_FREQUENCIES)


def _slice_response(evolution: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    response = copy.deepcopy(evolution)
    response["meta"] = meta
    return response


@contextmanager
def _user_evolution_file_lock(user_id: int) -> Iterator[None]:
    """
    Evita varias peticiones HTTP/worker en paralelo recalculando el mismo usuario
    (rebuild triple = costoso). Misma ruta en Linux que el worker (fcntl + fichero).
    """
    try:
        import fcntl
    except ImportError:
        yield
        return

    from flask import has_app_context, current_app

    if not has_app_context():
        yield
        return

    lock_dir = os.path.join(current_app.instance_path, "evolution_cache_locks")
    os.makedirs(lock_dir, exist_ok=True)
    lock_path = os.path.join(lock_dir, f"user_{user_id}.lock")
    with open(lock_path, "a+", encoding="utf-8") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


class PortfolioEvolutionCacheService:
    @staticmethod
    def _extract_meta(cache_row: PortfolioEvolutionCache) -> dict[str, Any]:
        data = cache_row.cached_data or {}
        meta = data.get("meta") or {}
        return _touch_meta_defaults(meta)

    @staticmethod
    def get(user_id: int, frequency: str) -> dict | None:
        frequency = _normalize_frequency(frequency)
        cache = PortfolioEvolutionCache.query.filter_by(user_id=user_id).first()
        if not cache or not cache.is_valid:
            if cache:
                db.session.delete(cache)
                db.session.commit()
            return None

        data = copy.deepcopy(cache.cached_data or {})
        meta = _touch_meta_defaults(data.get("meta") or {})
        data["meta"] = meta

        if _is_multi_frequency_bundle(data):
            evolution = (data.get("evolutions") or {}).get(frequency)
            return copy.deepcopy(evolution) if evolution else None

        evolution = data.get("evolution")
        if not evolution:
            return None
        if meta.get("frequency") and meta.get("frequency") not in (frequency, "all"):
            return None
        return evolution

    @staticmethod
    def touch_for_dates(user_id: int, dates: list[date]) -> None:
        """
        - Si alguna fecha es pasada: needs_full_rebuild=True
        - Si solo fechas de hoy: dirty_now=True
        (Misma noción de "hoy" que PortfolioEvolutionService / valoraciones.)
        """
        today = datetime.now().date()
        any_past = any(d < today for d in dates if isinstance(d, date))
        any_today = any(d == today for d in dates if isinstance(d, date))
        if not any_past and not any_today:
            return

        with _user_evolution_file_lock(user_id):
            cache = PortfolioEvolutionCache.query.filter_by(user_id=user_id).first()
            if not cache:
                return
            data = copy.deepcopy(cache.cached_data or {})
            meta = _touch_meta_defaults(data.get("meta") or {})
            if any_past:
                meta["needs_full_rebuild"] = True
                meta["dirty_now"] = False
            elif any_today:
                meta["dirty_now"] = True
            data["meta"] = meta
            cache.cached_data = data
            db.session.commit()

    @staticmethod
    def touch_for_prices_update(user_id: int) -> None:
        """Actualizar NOW por cambios en current_price (precios)."""
        with _user_evolution_file_lock(user_id):
            cache = PortfolioEvolutionCache.query.filter_by(user_id=user_id).first()
            if not cache:
                return
            data = copy.deepcopy(cache.cached_data or {})
            meta = _touch_meta_defaults(data.get("meta") or {})
            meta["dirty_now"] = True
            data["meta"] = meta
            cache.cached_data = data
            db.session.commit()

    @staticmethod
    def invalidate(user_id: int) -> None:
        with _user_evolution_file_lock(user_id):
            cache = PortfolioEvolutionCache.query.filter_by(user_id=user_id).first()
            if cache:
                db.session.delete(cache)
                db.session.commit()

    @staticmethod
    def _bump_version(meta: dict[str, Any], now: datetime) -> None:
        meta["version"] = int(now.timestamp() * 1000)
        meta["_now_cached_at"] = _utc_iso_z(now)

    @staticmethod
    def _full_rebuild_single(user_id: int, frequency: str) -> dict[str, Any]:
        service = PortfolioEvolutionService(user_id)
        return service.get_evolution_data(frequency=frequency)

    @staticmethod
    def _full_rebuild_all(user_id: int) -> dict[str, Any]:
        evolutions: dict[str, Any] = {}
        last_end: str | None = None
        for freq in EVOLUTION_FREQUENCIES:
            ev = PortfolioEvolutionCacheService._full_rebuild_single(user_id, freq)
            evolutions[freq] = ev
            last_end = ev.get("end_date") or last_end

        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        meta = {
            "needs_full_rebuild": False,
            "dirty_now": False,
            "hist_end_date": last_end,
            "frequency": "all",
            "version": int(now.timestamp() * 1000),
            "_now_cached_at": _utc_iso_z(now),
            "sync_type": "HIST+NOW",
        }
        return {"evolutions": evolutions, "meta": meta}

    @staticmethod
    def _recompute_one_evolution_now(
        user_id: int,
        evolution: dict[str, Any],
        service: PortfolioEvolutionService,
        today: date,
        current_end_date_str: str,
    ) -> dict[str, Any] | None:
        """
        Actualiza el último punto de un único bloque evolution. None => hay que hacer full rebuild global.
        """
        start_date_str = evolution.get("start_date")
        if not start_date_str:
            return None

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        start_date_dt = datetime.combine(start_date, time.min)
        end_date_dt = datetime.combine(today, time.max)

        portfolio_data = PortfolioValuation.get_detailed_value_at_date(
            user_id=user_id,
            target_date=end_date_dt,
            use_current_prices=True,
        )

        value = float(portfolio_data["total_value"])
        holdings_value = float(portfolio_data["holdings_value"])
        pl_unrealized_at_date = float(portfolio_data["pl_unrealized"])

        capital = float(service._get_capital_invested(today))
        return_data = ModifiedDietzCalculator.calculate_return(
            user_id=user_id,
            start_date=start_date_dt,
            end_date=end_date_dt,
        )
        return_pct = float(return_data.get("return_pct") or 0.0)

        dividends = float(service._get_dividends_until(today))
        fees = float(service._get_fees_until(today))
        pl_realized = float(service._get_pl_realized_until(today))

        pl_total = pl_realized + pl_unrealized_at_date + dividends - fees
        user_money = capital + pl_realized + dividends - fees
        user_money_for_leverage = user_money

        broker_money = user_money_for_leverage - float(holdings_value - pl_unrealized_at_date)

        labels = evolution.get("labels") or []
        datasets = evolution.get("datasets") or {}
        idx = len(labels) - 1
        if idx < 0:
            return None

        datasets = dict(datasets)
        datasets.setdefault("portfolio_value", [])
        datasets.setdefault("capital_invested", [])
        datasets.setdefault("returns_pct", [])
        datasets.setdefault("leverage", [])
        datasets.setdefault("cash_flows_cumulative", [])
        datasets.setdefault("pl_accumulated", [])

        datasets["portfolio_value"][idx] = value
        datasets["capital_invested"][idx] = capital
        datasets["returns_pct"][idx] = return_pct
        datasets["leverage"][idx] = float(broker_money)
        datasets["cash_flows_cumulative"][idx] = capital
        datasets["pl_accumulated"][idx] = float(pl_total)

        out = copy.deepcopy(evolution)
        out["datasets"] = datasets
        out["end_date"] = current_end_date_str
        out["cash_flows"] = service._get_cash_flows()
        return out

    @staticmethod
    def _recompute_now_all(user_id: int, cached: dict[str, Any]) -> dict[str, Any]:
        """Recalcula el último punto para daily, weekly y monthly."""
        meta = _touch_meta_defaults(cached.get("meta") or {})
        today = datetime.now().date()
        current_end_date_str = today.strftime("%Y-%m-%d")

        if meta.get("hist_end_date") and meta.get("hist_end_date") != current_end_date_str:
            return PortfolioEvolutionCacheService._full_rebuild_all(user_id)

        if not _is_multi_frequency_bundle(cached):
            return PortfolioEvolutionCacheService._full_rebuild_all(user_id)

        service = PortfolioEvolutionService(user_id)
        evolutions_in = cached.get("evolutions") or {}
        new_evs: dict[str, Any] = {}
        for freq in EVOLUTION_FREQUENCIES:
            ev = copy.deepcopy(evolutions_in.get(freq) or {})
            updated = PortfolioEvolutionCacheService._recompute_one_evolution_now(
                user_id, ev, service, today, current_end_date_str
            )
            if updated is None:
                return PortfolioEvolutionCacheService._full_rebuild_all(user_id)
            new_evs[freq] = updated

        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        PortfolioEvolutionCacheService._bump_version(meta, now)
        meta["dirty_now"] = False
        meta["needs_full_rebuild"] = False
        meta["hist_end_date"] = current_end_date_str
        meta["frequency"] = "all"
        meta["sync_type"] = "NOW"

        return {"evolutions": new_evs, "meta": meta}

    @staticmethod
    def _persist_bundle(cache_row: PortfolioEvolutionCache | None, user_id: int, bundle: dict[str, Any]) -> None:
        if not cache_row:
            cache_row = PortfolioEvolutionCache(
                user_id=user_id,
                cached_data=bundle,
                expires_at=PortfolioEvolutionCache.get_default_expiry(),
            )
            db.session.add(cache_row)
        else:
            cache_row.cached_data = bundle
        cache_row.expires_at = PortfolioEvolutionCache.get_default_expiry()
        cache_row.created_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def get_state(user_id: int, frequency: str) -> dict:
        """
        Devuelve el snapshot evolution para la frecuencia pedida + meta.version para detectar cambios.
        El almacenamiento interno mantiene daily/weekly/monthly juntos.
        Serializado por usuario (flock) para no solapar rebuilds costosos entre tabs/polling/worker.
        """
        with _user_evolution_file_lock(user_id):
            return PortfolioEvolutionCacheService._get_state_impl(user_id, frequency)

    @staticmethod
    def _get_state_impl(user_id: int, frequency: str) -> dict:
        frequency = _normalize_frequency(frequency)
        cached = None
        cache_row = PortfolioEvolutionCache.query.filter_by(user_id=user_id).first()
        if cache_row and cache_row.is_valid and cache_row.cached_data:
            cached = cache_row.cached_data

        def _return_bundle_slice(bundle: dict[str, Any]) -> dict[str, Any]:
            meta = _touch_meta_defaults(bundle.get("meta") or {})
            evs = bundle.get("evolutions") or {}
            ev = evs.get(frequency) or {}
            return _slice_response(ev, meta)

        if not cached:
            rebuilt = PortfolioEvolutionCacheService._full_rebuild_all(user_id)
            PortfolioEvolutionCacheService._persist_bundle(cache_row, user_id, rebuilt)
            return _return_bundle_slice(rebuilt)

        if not _is_multi_frequency_bundle(cached):
            rebuilt = PortfolioEvolutionCacheService._full_rebuild_all(user_id)
            PortfolioEvolutionCacheService._persist_bundle(cache_row, user_id, rebuilt)
            return _return_bundle_slice(rebuilt)

        meta = _touch_meta_defaults(cached.get("meta") or {})

        if meta.get("needs_full_rebuild"):
            rebuilt = PortfolioEvolutionCacheService._full_rebuild_all(user_id)
            PortfolioEvolutionCacheService._persist_bundle(cache_row, user_id, rebuilt)
            return _return_bundle_slice(rebuilt)

        if meta.get("dirty_now"):
            updated = PortfolioEvolutionCacheService._recompute_now_all(user_id, cached)
            PortfolioEvolutionCacheService._persist_bundle(cache_row, user_id, updated)
            return _return_bundle_slice(updated)

        response = copy.deepcopy((cached.get("evolutions") or {}).get(frequency) or {})
        if not meta.get("sync_type"):
            meta = dict(meta)
            meta["sync_type"] = "cached"
        response["meta"] = meta
        return response
