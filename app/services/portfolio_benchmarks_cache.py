"""
Cache HIST/NOW para:
- /portfolio/index-comparison (benchmarks vs portfolio)

Estrategia:
- HIST: comparación completa (requiere Yahoo) cuando cambia el pasado o cambia el día
- NOW: recálculo sobre el portfolio actual SIN volver a pedir Yahoo en cada poll
  (se reutiliza benchmark_data_daily almacenado en el cache)
"""

from __future__ import annotations

import copy
from datetime import date, datetime, time, timezone, timedelta
from typing import Any

from flask import current_app

from app import db
from app.models.portfolio_benchmarks_cache import PortfolioBenchmarksCache
from app.services.metrics.benchmark_comparison import BenchmarkComparisonService, BENCHMARKS
from app.services.metrics.modified_dietz import ModifiedDietzCalculator


def _utc_iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _meta_defaults(meta: dict[str, Any]) -> dict[str, Any]:
    meta = dict(meta or {})
    meta.setdefault("needs_full_rebuild", False)
    meta.setdefault("dirty_now", False)
    meta.setdefault("hist_end_date", None)  # YYYY-MM-DD
    meta.setdefault("version", 0)
    meta.setdefault("_now_cached_at", None)
    meta.setdefault("sync_type", None)  # "HIST+NOW" | "NOW" | null
    return meta


def _to_json_safe(obj: Any) -> Any:
    """Convierte date/datetime a strings para que cached_data sea JSON-serializable."""
    if isinstance(obj, date) and not isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, datetime):
        return _utc_iso_z(obj) if obj.tzinfo else obj.strftime("%Y-%m-%dT%H:%M:%S")
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    return obj


class PortfolioBenchmarksCacheService:
    @staticmethod
    def _get_cache_row(user_id: int) -> PortfolioBenchmarksCache | None:
        cache = PortfolioBenchmarksCache.query.filter_by(user_id=user_id).first()
        if cache and not cache.is_valid:
            db.session.delete(cache)
            db.session.commit()
            return None
        return cache

    @staticmethod
    def touch_for_dates(user_id: int, dates: list[date]) -> None:
        today = datetime.now().date()
        any_past = any(d < today for d in dates if isinstance(d, date))
        any_today = any(d == today for d in dates if isinstance(d, date))
        if not any_past and not any_today:
            return

        cache = PortfolioBenchmarksCacheService._get_cache_row(user_id)
        if not cache:
            return

        data = copy.deepcopy(cache.cached_data or {})
        meta = _meta_defaults(data.get("meta") or {})
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
        cache = PortfolioBenchmarksCacheService._get_cache_row(user_id)
        if not cache:
            return
        data = copy.deepcopy(cache.cached_data or {})
        meta = _meta_defaults(data.get("meta") or {})
        meta["dirty_now"] = True
        data["meta"] = meta
        cache.cached_data = data
        db.session.commit()

    @staticmethod
    def invalidate(user_id: int) -> None:
        cache = PortfolioBenchmarksCacheService._get_cache_row(user_id)
        if cache:
            db.session.delete(cache)
            db.session.commit()

    @staticmethod
    def _bump_version(meta: dict[str, Any], now: datetime) -> None:
        meta["version"] = int(now.timestamp() * 1000)
        meta["_now_cached_at"] = _utc_iso_z(now)

    @staticmethod
    def _compute_benchmark_annualized_from_daily(
        start_date: date,
        end_date: date,
        benchmark_data_daily: dict[str, Any],
    ) -> tuple[dict[str, float], dict[str, float], float]:
        """
        Returns: (benchmarks_totals_pct, benchmarks_annualized_pct, years_total)
        """
        days_total = (end_date - start_date).days
        years_total = days_total / 365.25 if days_total > 0 else 1

        bench_totals: dict[str, float] = {}
        bench_annualized: dict[str, float] = {}

        for name in BENCHMARKS.keys():
            series = benchmark_data_daily.get(name) or {}
            points = series.get("data_points") or []
            if len(points) < 2:
                continue
            first_price = points[0].get("price") or 0
            last_price = points[-1].get("price") or 0
            if not first_price or first_price <= 0:
                continue

            total_return = (last_price - first_price) / first_price
            total_return_pct = total_return * 100
            bench_totals[name] = total_return_pct

            if years_total > 0 and total_return > -1:
                annualized_return = ((1 + total_return) ** (1 / years_total)) - 1
                bench_annualized[name] = annualized_return * 100
            else:
                bench_annualized[name] = None

        return bench_totals, bench_annualized, years_total

    @staticmethod
    def _full_rebuild(user_id: int) -> dict[str, Any]:
        service = BenchmarkComparisonService(user_id)
        start_date = service.start_date
        if not start_date:
            comparison_data = service.get_comparison_data()
            return {"comparison_data": comparison_data, "annualized_summary": {}, "benchmark_data_daily": {}, "meta": _meta_defaults({})}

        end_date = datetime.now().date()

        # 1) Descargar benchmarks diarios (Yahoo) - HIST
        benchmark_data_daily: dict[str, Any] = {}
        for name, ticker in BENCHMARKS.items():
            data = service.get_benchmark_historical_data(ticker, start_date, end_date=end_date)
            if data:
                benchmark_data_daily[name] = data

        # 2) Recalcular comparación (portfolio+benchmarks)
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)

        portfolio_monthly = service._calculate_portfolio_monthly_returns(start_datetime, end_datetime)
        monthly_data = {name: service._group_by_month(daily.get("data_points") or []) for name, daily in benchmark_data_daily.items()}
        normalized_data = service._normalize_to_100(portfolio_monthly, monthly_data)
        annual_returns = service._calculate_annual_returns(portfolio_monthly, monthly_data, benchmark_data_daily)

        chart_datasets = {
            "portfolio": normalized_data["portfolio"],
        }
        for name in BENCHMARKS.keys():
            if name in normalized_data.get("benchmarks", {}):
                chart_datasets[name] = normalized_data["benchmarks"][name]

        comparison_data = {
            "labels": normalized_data["labels"],
            "datasets": chart_datasets,
            "annual_returns": annual_returns,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "benchmarks": list(BENCHMARKS.keys()),
        }

        # 3) Resumen anualizado (card) SIN re-pedir Yahoo
        portfolio_annualized_data = ModifiedDietzCalculator.calculate_annualized_return(user_id)
        portfolio_annualized_pct = portfolio_annualized_data.get("annualized_return_pct", 0.0) or 0.0

        portfolio_total_data = ModifiedDietzCalculator.calculate_return(
            user_id=user_id,
            start_date=start_datetime,
            end_date=end_datetime,
        )
        portfolio_total_pct = portfolio_total_data.get("return_pct", 0.0) if portfolio_total_data else 0.0

        bench_totals, bench_annualized, years_total = PortfolioBenchmarksCacheService._compute_benchmark_annualized_from_daily(
            start_date=start_date,
            end_date=end_date,
            benchmark_data_daily=benchmark_data_daily,
        )

        differences = {name: portfolio_total_pct - bench_totals[name] for name in bench_totals.keys()}
        differences_annualized = {
            name: portfolio_annualized_pct - bench_annualized[name]
            for name in bench_annualized.keys()
            if bench_annualized.get(name) is not None
        }

        annualized_summary = {
            "portfolio_annualized": portfolio_annualized_pct,
            "benchmarks": bench_totals,
            "benchmarks_annualized": bench_annualized,
            "differences": differences,
            "differences_annualized": differences_annualized,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "years": round(years_total, 2),
        }

        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        meta = {
            "needs_full_rebuild": False,
            "dirty_now": False,
            "hist_end_date": end_date.strftime("%Y-%m-%d"),
            "version": int(now.timestamp() * 1000),
            "_now_cached_at": _utc_iso_z(now),
            "sync_type": "HIST+NOW",
        }
        return {
            "comparison_data": comparison_data,
            "annualized_summary": annualized_summary,
            "benchmark_data_daily": benchmark_data_daily,
            "portfolio_start_date": start_date.strftime("%Y-%m-%d"),
            "meta": meta,
        }

    @staticmethod
    def _recompute_now(user_id: int, cached: dict[str, Any]) -> dict[str, Any]:
        service = BenchmarkComparisonService(user_id)
        today = datetime.now().date()
        today_str = today.strftime("%Y-%m-%d")

        # Si no está el dataset daily, fallback a rebuild completo
        if not cached.get("benchmark_data_daily"):
            rebuilt = PortfolioBenchmarksCacheService._full_rebuild(user_id)
            return rebuilt

        start_date_str = cached.get("portfolio_start_date") or (service.start_date.strftime("%Y-%m-%d") if service.start_date else None)
        if not start_date_str:
            return PortfolioBenchmarksCacheService._full_rebuild(user_id)
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()

        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(today, time.max)

        # Benchmarks mensuales desde daily cache (sin Yahoo)
        benchmark_data_daily = cached["benchmark_data_daily"]
        monthly_data = {name: service._group_by_month(daily.get("data_points") or []) for name, daily in benchmark_data_daily.items()}

        # Portfolio mensual actualizado (ModifiedDietz) - HIST requiere rebuild, NOW recalc una vez
        portfolio_monthly = service._calculate_portfolio_monthly_returns(start_datetime, end_datetime)
        normalized_data = service._normalize_to_100(portfolio_monthly, monthly_data)
        annual_returns = service._calculate_annual_returns(portfolio_monthly, monthly_data, benchmark_data_daily)

        chart_datasets = {"portfolio": normalized_data["portfolio"]}
        for name in BENCHMARKS.keys():
            if name in normalized_data.get("benchmarks", {}):
                chart_datasets[name] = normalized_data["benchmarks"][name]

        comparison_data = {
            "labels": normalized_data["labels"],
            "datasets": chart_datasets,
            "annual_returns": annual_returns,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": today.strftime("%Y-%m-%d"),
            "benchmarks": list(BENCHMARKS.keys()),
        }

        # Resumen card: actualizar SOLO portfolio (benchmarks ya están en cache diaria)
        portfolio_annualized_data = ModifiedDietzCalculator.calculate_annualized_return(user_id)
        portfolio_annualized_pct = portfolio_annualized_data.get("annualized_return_pct", 0.0) or 0.0
        portfolio_total_data = ModifiedDietzCalculator.calculate_return(
            user_id=user_id,
            start_date=start_datetime,
            end_date=end_datetime,
        )
        portfolio_total_pct = portfolio_total_data.get("return_pct", 0.0) if portfolio_total_data else 0.0

        bench_totals, bench_annualized, years_total = PortfolioBenchmarksCacheService._compute_benchmark_annualized_from_daily(
            start_date=start_date,
            end_date=today,
            benchmark_data_daily=benchmark_data_daily,
        )

        differences = {name: portfolio_total_pct - bench_totals[name] for name in bench_totals.keys()}
        differences_annualized = {
            name: portfolio_annualized_pct - bench_annualized[name]
            for name in bench_annualized.keys()
            if bench_annualized.get(name) is not None
        }

        annualized_summary = {
            "portfolio_annualized": portfolio_annualized_pct,
            "benchmarks": bench_totals,
            "benchmarks_annualized": bench_annualized,
            "differences": differences,
            "differences_annualized": differences_annualized,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "years": round(years_total, 2),
        }

        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        meta = _meta_defaults(cached.get("meta") or {})
        meta["dirty_now"] = False
        meta["needs_full_rebuild"] = False
        meta["hist_end_date"] = today_str
        meta["sync_type"] = "NOW"
        PortfolioBenchmarksCacheService._bump_version(meta, now)

        return {
            **cached,
            "comparison_data": comparison_data,
            "annualized_summary": annualized_summary,
            "meta": meta,
            "portfolio_start_date": start_date.strftime("%Y-%m-%d"),
        }

    @staticmethod
    def get_comparison_state(user_id: int) -> dict[str, Any]:
        """
        Para la API de /portfolio/api/benchmarks (Chart + tabla).
        """
        cache = PortfolioBenchmarksCacheService._get_cache_row(user_id)
        today_str = datetime.now().date().strftime("%Y-%m-%d")

        if not cache or not cache.cached_data:
            rebuilt = PortfolioBenchmarksCacheService._full_rebuild(user_id)
            safe_rebuilt = _to_json_safe(rebuilt)
            if cache:
                cache.cached_data = safe_rebuilt
            else:
                cache = PortfolioBenchmarksCache(user_id=user_id, cached_data=safe_rebuilt, expires_at=PortfolioBenchmarksCache.get_default_expiry())
                db.session.add(cache)
            cache.expires_at = PortfolioBenchmarksCache.get_default_expiry()
            cache.created_at = datetime.utcnow()
            db.session.commit()
            result = copy.deepcopy(rebuilt.get("comparison_data") or {})
            result["meta"] = rebuilt.get("meta") or {}
            return result

        cached = cache.cached_data
        meta = _meta_defaults(cached.get("meta") or {})

        if meta.get("needs_full_rebuild") or (meta.get("hist_end_date") and meta.get("hist_end_date") != today_str):
            rebuilt = PortfolioBenchmarksCacheService._full_rebuild(user_id)
            cache.cached_data = _to_json_safe(rebuilt)
            cache.expires_at = PortfolioBenchmarksCache.get_default_expiry()
            cache.created_at = datetime.utcnow()
            db.session.commit()
            result = copy.deepcopy(rebuilt.get("comparison_data") or {})
            result["meta"] = rebuilt.get("meta") or {}
            return result

        if meta.get("dirty_now"):
            updated = PortfolioBenchmarksCacheService._recompute_now(user_id, cached)
            cache.cached_data = _to_json_safe(updated)
            cache.expires_at = PortfolioBenchmarksCache.get_default_expiry()
            cache.created_at = datetime.utcnow()
            db.session.commit()
            result = copy.deepcopy(updated.get("comparison_data") or {})
            result["meta"] = updated.get("meta") or {}
            return result

        result = copy.deepcopy(cached.get("comparison_data") or {})
        # Caches antiguos pueden no tener sync_type; usar fallback para que la UI muestre algo
        if not meta.get("sync_type"):
            meta = dict(meta)
            meta["sync_type"] = "cached"
        result["meta"] = meta
        return result

    @staticmethod
    def get_annualized_summary(user_id: int) -> dict[str, Any]:
        """
        Para renderizar la tarjeta superior en /portfolio/index-comparison.
        """
        state = PortfolioBenchmarksCacheService.get_comparison_state(user_id)
        cache = PortfolioBenchmarksCacheService._get_cache_row(user_id)
        if cache and cache.cached_data:
            return cache.cached_data.get("annualized_summary") or {}
        return {}

