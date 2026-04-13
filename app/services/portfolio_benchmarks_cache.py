"""
Cache HIST/NOW para:
- /portfolio/index-comparison (benchmarks vs portfolio)

Estrategia:
- HIST índices: tabla global `benchmark_global_daily` mantenida por `benchmark-global-daily-once` (Yahoo compartido).
- Por usuario: `portfolio_benchmarks_cache` guarda comparación, recorte diario y meta; al subir `daily_data_version` global se recompute sin Yahoo por índice.
- NOW intradía índices: `benchmark_global_quote` + price-poll-one y fusión en `get_comparison_state`.
"""

from __future__ import annotations

import copy
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func

from app import db
from app.models.portfolio_benchmarks_cache import PortfolioBenchmarksCache
from app.services.metrics.benchmark_comparison import BenchmarkComparisonService, BENCHMARKS
from app.services.metrics.modified_dietz import ModifiedDietzCalculator
from app.services.benchmark_global_service import BenchmarkGlobalService


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
       meta.setdefault("benchmark_quotes_applied_at", None)
    meta.setdefault("benchmark_global_daily_version", -1)
    return meta


def _dt_as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_benchmark_quotes_applied_at(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return _dt_as_utc(raw)
    s = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return _dt_as_utc(dt)


def _max_benchmark_global_quote_updated_at() -> datetime | None:
    from app.models.benchmark_global_quote import BenchmarkGlobalQuote

    return db.session.query(func.max(BenchmarkGlobalQuote.updated_at)).scalar()


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

        # 1) Series diarias globales (Yahoo solo en mantenimiento global / refresh aquí si hace falta)
        BenchmarkGlobalService.refresh_daily_if_stale()
        benchmark_data_daily = BenchmarkGlobalService.get_sliced_daily_for_user(user_id)
        if len(benchmark_data_daily) < len(BENCHMARKS):
            BenchmarkGlobalService.refresh_daily_if_stale(force=True)
            benchmark_data_daily = BenchmarkGlobalService.get_sliced_daily_for_user(user_id)
        benchmark_data_daily, _ = PortfolioBenchmarksCacheService._merge_global_quotes_into_daily(
            copy.deepcopy(benchmark_data_daily)
        )

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
            "benchmark_global_daily_version": BenchmarkGlobalService.get_daily_data_version(),
        }
        mq = _max_benchmark_global_quote_updated_at()
        if mq:
            meta["benchmark_quotes_applied_at"] = _utc_iso_z(_dt_as_utc(mq))
        return {
            "comparison_data": comparison_data,
            "annualized_summary": annualized_summary,
            "benchmark_data_daily": benchmark_data_daily,
            "portfolio_start_date": start_date.strftime("%Y-%m-%d"),
            "meta": meta,
        }

    @staticmethod
    def _merge_global_quotes_into_daily(
        benchmark_data_daily: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        """
        Incorpora precios intradía de `benchmark_global_quote` en el último punto
        (o añade barra del día) sin llamadas HTTP.
        """
        from app.models.benchmark_global_quote import BenchmarkGlobalQuote

        out = copy.deepcopy(benchmark_data_daily)
        changed = False
        today_str = datetime.now().date().strftime("%Y-%m-%d")
        for name in BENCHMARKS.keys():
            row = BenchmarkGlobalQuote.query.filter_by(benchmark_name=name).first()
            if not row or row.regular_market_price is None:
                continue
            series = out.get(name)
            if not series:
                continue
            points = list(series.get("data_points") or [])
            if not points:
                continue
            price = float(row.regular_market_price)
            last = points[-1]
            last_date = last.get("date")
            if isinstance(last_date, str) and last_date > today_str:
                continue
            if last_date == today_str:
                try:
                    old_f = float(last.get("price")) if last.get("price") is not None else None
                except (TypeError, ValueError):
                    old_f = None
                if old_f is None or abs(old_f - price) > 1e-9:
                    last["price"] = price
                    changed = True
            else:
                points.append({"date": today_str, "price": price})
                series["data_points"] = points
                out[name] = series
                changed = True
        return out, changed

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
        meta["benchmark_global_daily_version"] = BenchmarkGlobalService.get_daily_data_version()
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

        gver = BenchmarkGlobalService.get_daily_data_version()
        if int(meta.get("benchmark_global_daily_version", -1)) < gver:
            BenchmarkGlobalService.refresh_daily_if_stale()
            sliced = BenchmarkGlobalService.get_sliced_daily_for_user(user_id)
            if sliced:
                merged_daily, _ = PortfolioBenchmarksCacheService._merge_global_quotes_into_daily(
                    copy.deepcopy(sliced)
                )
                updated = PortfolioBenchmarksCacheService._recompute_now(
                    user_id, {**cached, "benchmark_data_daily": merged_daily}
                )
                um = _meta_defaults(updated.get("meta") or {})
                um["benchmark_global_daily_version"] = gver
                mq = _max_benchmark_global_quote_updated_at()
                if mq:
                    um["benchmark_quotes_applied_at"] = _utc_iso_z(_dt_as_utc(mq))
                updated["meta"] = um
                cache.cached_data = _to_json_safe(updated)
                cache.expires_at = PortfolioBenchmarksCache.get_default_expiry()
                cache.created_at = datetime.utcnow()
                db.session.commit()
                result = copy.deepcopy(updated.get("comparison_data") or {})
                result["meta"] = updated.get("meta") or {}
                return result

        if meta.get("dirty_now"):
            daily_base = copy.deepcopy(BenchmarkGlobalService.get_sliced_daily_for_user(user_id))
            if not daily_base:
                daily_base = copy.deepcopy(cached.get("benchmark_data_daily") or {})
            merged_daily, _ = PortfolioBenchmarksCacheService._merge_global_quotes_into_daily(daily_base)
            updated = PortfolioBenchmarksCacheService._recompute_now(
                user_id, {**cached, "benchmark_data_daily": merged_daily}
            )
            mq = _max_benchmark_global_quote_updated_at()
            um = _meta_defaults(updated.get("meta") or {})
            um["benchmark_global_daily_version"] = BenchmarkGlobalService.get_daily_data_version()
            if mq:
                um["benchmark_quotes_applied_at"] = _utc_iso_z(_dt_as_utc(mq))
            updated["meta"] = um
            cache.cached_data = _to_json_safe(updated)
            cache.expires_at = PortfolioBenchmarksCache.get_default_expiry()
            cache.created_at = datetime.utcnow()
            db.session.commit()
            result = copy.deepcopy(updated.get("comparison_data") or {})
            result["meta"] = updated.get("meta") or {}
            return result

        max_qu = _max_benchmark_global_quote_updated_at()
        max_qu_utc = _dt_as_utc(max_qu)
        applied_utc = _parse_benchmark_quotes_applied_at(meta.get("benchmark_quotes_applied_at"))
        daily_for_quotes = cached.get("benchmark_data_daily") or BenchmarkGlobalService.get_sliced_daily_for_user(
            user_id
        )
        if max_qu_utc and daily_for_quotes and (applied_utc is None or max_qu_utc > applied_utc):
            merged_daily, changed = PortfolioBenchmarksCacheService._merge_global_quotes_into_daily(
                copy.deepcopy(daily_for_quotes)
            )
            new_applied = _utc_iso_z(max_qu_utc)
            if changed:
                updated = PortfolioBenchmarksCacheService._recompute_now(
                    user_id, {**cached, "benchmark_data_daily": merged_daily}
                )
                um = _meta_defaults(updated.get("meta") or {})
                um["benchmark_global_daily_version"] = BenchmarkGlobalService.get_daily_data_version()
                um["benchmark_quotes_applied_at"] = new_applied
                updated["meta"] = um
                cache.cached_data = _to_json_safe(updated)
                cache.expires_at = PortfolioBenchmarksCache.get_default_expiry()
                cache.created_at = datetime.utcnow()
                db.session.commit()
                result = copy.deepcopy(updated.get("comparison_data") or {})
                result["meta"] = updated.get("meta") or {}
                return result
            meta = dict(meta)
            meta["benchmark_quotes_applied_at"] = new_applied
            cached_mut = dict(cached)
            cached_mut["meta"] = meta
            cache.cached_data = _to_json_safe(cached_mut)
            cache.expires_at = PortfolioBenchmarksCache.get_default_expiry()
            db.session.commit()
            result = copy.deepcopy(cached_mut.get("comparison_data") or {})
            if not meta.get("sync_type"):
                meta = dict(meta)
                meta["sync_type"] = "cached"
            result["meta"] = meta
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


def get_market_indices_snapshot(user_id: int) -> list[dict[str, Any]]:
    """
    % día y último precio: prioriza `benchmark_global_quote` (job price-poll-one, sin HTTP aquí).
    Si aún no hay fila para un índice, usa caché por usuario y luego `benchmark_global_daily`.
    """
    from app.models.benchmark_global_quote import BenchmarkGlobalQuote
    from app.models.benchmark_global_daily import BenchmarkGlobalDaily

    global_by_name = {r.benchmark_name: r for r in BenchmarkGlobalQuote.query.all()}

    cache = PortfolioBenchmarksCacheService._get_cache_row(user_id)
    daily: dict[str, Any] = {}
    if cache and cache.cached_data:
        daily = (cache.cached_data or {}).get("benchmark_data_daily") or {}

    out: list[dict[str, Any]] = []
    for name, ticker in BENCHMARKS.items():
        g = global_by_name.get(name)
        if g is not None and g.regular_market_price is not None:
            last = float(g.regular_market_price)
            dcp = g.day_change_percent
            if dcp is not None:
                pct = round(float(dcp), 2)
            elif g.previous_close is not None and float(g.previous_close) > 0:
                prev = float(g.previous_close)
                pct = round(((last - prev) / prev) * 100, 2)
            else:
                pct = None
            out.append(
                {
                    "name": name,
                    "ticker": ticker,
                    "day_change_percent": pct,
                    "last_close": round(last, 2),
                }
            )
            continue

        series = daily.get(name) or {}
        points = list(series.get("data_points") or [])

        def _extract_prices(pts: list) -> list[float]:
            outv: list[float] = []
            for p in pts:
                v = p.get("price")
                if v is not None:
                    try:
                        outv.append(float(v))
                    except (TypeError, ValueError):
                        pass
            return outv

        prices = _extract_prices(points)
        if len(prices) < 2:
            gd = BenchmarkGlobalDaily.query.filter_by(benchmark_name=name).first()
            if gd and gd.data_points:
                prices = _extract_prices(list(gd.data_points))
        if len(prices) >= 2:
            prev_p, last_p = prices[-2], prices[-1]
            pct = round(((last_p - prev_p) / prev_p) * 100, 2) if prev_p else None
            out.append(
                {
                    "name": name,
                    "ticker": ticker,
                    "day_change_percent": pct,
                    "last_close": round(last_p, 2),
                }
            )
        elif len(prices) == 1:
            out.append(
                {
                    "name": name,
                    "ticker": ticker,
                    "day_change_percent": None,
                    "last_close": round(prices[0], 2),
                }
            )
        else:
            out.append(
                {
                    "name": name,
                    "ticker": ticker,
                    "day_change_percent": None,
                    "last_close": None,
                }
            )
    return out

