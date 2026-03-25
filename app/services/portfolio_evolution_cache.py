"""
Servicio de caché HIST/NOW para:
- /portfolio/performance (evolución del portfolio para Chart.js)

Objetivo:
1) Rebuild completo (HIST) solo cuando cambia "pasado" (transacciones de fechas pasadas)
2) Recalcular solo el tramo actual (NOW) cuando cambia "hoy", y hacerlo dentro del polling (~30s)
"""

from __future__ import annotations

import copy
import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from app import db
from app.models.portfolio_evolution_cache import PortfolioEvolutionCache
from app.services.metrics.portfolio_evolution import PortfolioEvolutionService
from app.services.metrics.portfolio_valuation import PortfolioValuation
from app.services.metrics.modified_dietz import ModifiedDietzCalculator


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
    meta.setdefault("frequency", None)
    meta.setdefault("version", 0)
    meta.setdefault("_now_cached_at", None)
    meta.setdefault("sync_type", None)  # "HIST+NOW" | "NOW" | null
    return meta


class PortfolioEvolutionCacheService:
    @staticmethod
    def _extract_meta(cache_row: PortfolioEvolutionCache) -> dict[str, Any]:
        data = cache_row.cached_data or {}
        meta = data.get("meta") or {}
        return _touch_meta_defaults(meta)

    @staticmethod
    def get(user_id: int, frequency: str) -> dict | None:
        cache = PortfolioEvolutionCache.query.filter_by(user_id=user_id).first()
        if not cache or not cache.is_valid:
            if cache:
                db.session.delete(cache)
                db.session.commit()
            return None

        data = copy.deepcopy(cache.cached_data or {})
        meta = _touch_meta_defaults(data.get("meta") or {})
        data["meta"] = meta

        evolution = data.get("evolution")
        if not evolution:
            return None
        if meta.get("frequency") and meta.get("frequency") != frequency:
            # Frecuencia distinta: no reutilizamos el snapshot.
            return None
        return evolution

    @staticmethod
    def touch_for_dates(user_id: int, dates: list[date]) -> None:
        """
        - Si alguna fecha es pasada: needs_full_rebuild=True
        - Si alguna fecha es hoy: dirty_now=True
        """
        today = datetime.now().date()  # coincide con PortfolioValuation/ModifiedDietz en el proyecto
        any_past = any(d < today for d in dates if isinstance(d, date))
        any_today = any(d == today for d in dates if isinstance(d, date))
        if not any_past and not any_today:
            return

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
        cache = PortfolioEvolutionCache.query.filter_by(user_id=user_id).first()
        if cache:
            db.session.delete(cache)
            db.session.commit()

    @staticmethod
    def _bump_version(meta: dict[str, Any], now: datetime) -> None:
        meta["version"] = int(now.timestamp() * 1000)
        meta["_now_cached_at"] = _utc_iso_z(now)

    @staticmethod
    def _full_rebuild(user_id: int, frequency: str) -> dict[str, Any]:
        service = PortfolioEvolutionService(user_id)
        evolution = service.get_evolution_data(frequency=frequency)

        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        meta = {
            "needs_full_rebuild": False,
            "dirty_now": False,
            "hist_end_date": evolution.get("end_date"),
            "frequency": frequency,
            "version": int(now.timestamp() * 1000),
            "_now_cached_at": _utc_iso_z(now),
            "sync_type": "HIST+NOW",
        }
        return {"evolution": evolution, "meta": meta}

    @staticmethod
    def _recompute_now_last_point(user_id: int, cached: dict[str, Any], frequency: str) -> dict[str, Any]:
        """
        Recalcula SOLO el último punto (NOW) sobre el snapshot HIST.
        """
        evolution = copy.deepcopy(cached.get("evolution") or {})
        meta = _touch_meta_defaults(cached.get("meta") or {})

        today = datetime.now().date()
        current_end_date_str = today.strftime("%Y-%m-%d")

        # Si el end_date cambió (cambio de día / frecuencia que cambia fechas): rebuild completo.
        if meta.get("hist_end_date") and meta.get("hist_end_date") != current_end_date_str:
            return PortfolioEvolutionCacheService._full_rebuild(user_id, frequency)

        start_date_str = evolution.get("start_date")
        if not start_date_str:
            return PortfolioEvolutionCacheService._full_rebuild(user_id, frequency)

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        start_date_dt = datetime.combine(start_date, time.min)
        end_date_dt = datetime.combine(today, time.max)

        service = PortfolioEvolutionService(user_id)

        # Calcular último punto (misma lógica que PortfolioEvolutionService cuando date == end_date)
        # - Para el último punto usamos precios actuales (use_current_prices=True)
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

        # Actualizar estructuras del snapshot
        labels = evolution.get("labels") or []
        datasets = evolution.get("datasets") or {}
        idx = len(labels) - 1
        if idx < 0:
            return PortfolioEvolutionCacheService._full_rebuild(user_id, frequency)

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

        evolution["end_date"] = current_end_date_str
        evolution["cash_flows"] = service._get_cash_flows()

        # Bump meta NOW
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        PortfolioEvolutionCacheService._bump_version(meta, now)
        meta["dirty_now"] = False
        meta["needs_full_rebuild"] = False
        meta["hist_end_date"] = current_end_date_str
        meta["frequency"] = frequency
        meta["sync_type"] = "NOW"

        return {"evolution": evolution, "meta": meta}

    @staticmethod
    def get_state(user_id: int, frequency: str) -> dict:
        """
        Devuelve el snapshot evolution para el frontend + meta.version para detectar cambios.
        """
        cached = None
        cache_row = PortfolioEvolutionCache.query.filter_by(user_id=user_id).first()
        if cache_row and cache_row.is_valid and cache_row.cached_data:
            cached = cache_row.cached_data

        if not cached:
            rebuilt = PortfolioEvolutionCacheService._full_rebuild(user_id, frequency)
            cache_row = PortfolioEvolutionCache.query.filter_by(user_id=user_id).first()
            if not cache_row:
                cache_row = PortfolioEvolutionCache(user_id=user_id, cached_data=rebuilt, expires_at=PortfolioEvolutionCache.get_default_expiry())
                db.session.add(cache_row)
            else:
                cache_row.cached_data = rebuilt
            cache_row.expires_at = PortfolioEvolutionCache.get_default_expiry()
            cache_row.created_at = datetime.utcnow()
            db.session.commit()
            response = copy.deepcopy(rebuilt["evolution"])
            response["meta"] = rebuilt["meta"]
            return response

        meta = _touch_meta_defaults(cached.get("meta") or {})
        if meta.get("frequency") != frequency:
            rebuilt = PortfolioEvolutionCacheService._full_rebuild(user_id, frequency)
            cache_row.cached_data = rebuilt
            cache_row.expires_at = PortfolioEvolutionCache.get_default_expiry()
            cache_row.created_at = datetime.utcnow()
            db.session.commit()
            response = copy.deepcopy(rebuilt["evolution"])
            response["meta"] = rebuilt["meta"]
            return response

        if meta.get("needs_full_rebuild"):
            rebuilt = PortfolioEvolutionCacheService._full_rebuild(user_id, frequency)
            cache_row.cached_data = rebuilt
            cache_row.expires_at = PortfolioEvolutionCache.get_default_expiry()
            cache_row.created_at = datetime.utcnow()
            db.session.commit()
            response = copy.deepcopy(rebuilt["evolution"])
            response["meta"] = rebuilt["meta"]
            return response

        if meta.get("dirty_now"):
            updated = PortfolioEvolutionCacheService._recompute_now_last_point(user_id, cached, frequency)
            cache_row.cached_data = updated
            cache_row.expires_at = PortfolioEvolutionCache.get_default_expiry()
            cache_row.created_at = datetime.utcnow()
            db.session.commit()
            response = copy.deepcopy(updated["evolution"])
            response["meta"] = updated["meta"]
            return response

        # Sin dirty: devolver snapshot actual
        response = copy.deepcopy(cached.get("evolution") or {})
        # Caches antiguos pueden no tener sync_type; usar fallback para que la UI muestre algo
        if not meta.get("sync_type"):
            meta = dict(meta)
            meta["sync_type"] = "cached"
        response["meta"] = meta
        return response

