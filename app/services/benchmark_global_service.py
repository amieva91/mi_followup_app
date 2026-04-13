"""
Mantenimiento global de series diarias de benchmarks (Yahoo una vez para todos los usuarios).
NOW intradía sigue en `benchmark_global_quote` + price-poll-one.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from app import db
from app.models.benchmark_global_daily import BenchmarkGlobalDaily, BenchmarkGlobalState
from app.models.user import User
from app.services.metrics.benchmark_comparison import BENCHMARKS, BenchmarkComparisonService


class BenchmarkGlobalService:
    """Serie diaria HIST compartida; cada usuario recorta por su fecha de inicio."""

    FIXED_GLOBAL_START = date(1990, 1, 1)

    @staticmethod
    def _any_benchmark_comparison_service() -> BenchmarkComparisonService | None:
        row = db.session.query(User.id).order_by(User.id).first()
        if not row:
            return None
        return BenchmarkComparisonService(row[0])

    @staticmethod
    def _merge_point_maps(
        existing_points: list[dict[str, Any]],
        new_points: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        by_date: dict[str, dict[str, Any]] = {}
        for p in existing_points or []:
            d = p.get("date")
            if d:
                by_date[str(d)] = dict(p)
        for p in new_points or []:
            d = p.get("date")
            if d:
                by_date[str(d)] = dict(p)
        return [by_date[k] for k in sorted(by_date.keys())]

    @staticmethod
    def get_daily_data_version() -> int:
        st = BenchmarkGlobalState.query.get(1)
        return int(st.daily_data_version) if st else 0

    @staticmethod
    def bump_daily_data_version() -> int:
        st = BenchmarkGlobalState.get_singleton()
        st.daily_data_version = int(st.daily_data_version or 0) + 1
        st.updated_at = datetime.utcnow()
        db.session.commit()
        return st.daily_data_version

    @staticmethod
    def refresh_daily_if_stale(force: bool = False) -> bool:
        """
        Actualiza filas en `benchmark_global_daily` si falta serie o hist_end_date < hoy.
        Tras cambios en datos (Yahoo), incrementa `daily_data_version`.
        Devuelve True si hubo al menos una actualización de serie.
        """
        bc = BenchmarkGlobalService._any_benchmark_comparison_service()
        if bc is None:
            return False

        today = datetime.now().date()
        today_str = today.strftime("%Y-%m-%d")
        any_data_change = False
        meta_fix = False

        for name, ticker in BENCHMARKS.items():
            row = BenchmarkGlobalDaily.query.filter_by(benchmark_name=name).first()
            hist_end = (row.hist_end_date or "") if row else ""
            need = force or row is None or hist_end < today_str
            if not need:
                continue

            points = list(row.data_points) if row and row.data_points else []

            if force or not points:
                new_data = bc.get_benchmark_historical_data(
                    ticker, BenchmarkGlobalService.FIXED_GLOBAL_START, end_date=today
                )
                if not new_data or not new_data.get("data_points"):
                    continue
                merged = new_data["data_points"]
            else:
                last_d: str | None = None
                for p in reversed(points):
                    if p.get("date"):
                        last_d = str(p["date"])
                        break
                if last_d and last_d >= today_str:
                    if row.hist_end_date != last_d:
                        row.hist_end_date = last_d
                        row.updated_at = datetime.utcnow()
                        meta_fix = True
                    continue
                start_fetch = datetime.strptime(last_d, "%Y-%m-%d").date() + timedelta(days=1)
                if start_fetch > today:
                    continue
                new_data = bc.get_benchmark_historical_data(ticker, start_fetch, end_date=today)
                if not new_data or not new_data.get("data_points"):
                    continue
                merged = BenchmarkGlobalService._merge_point_maps(points, new_data["data_points"])

            if row:
                row.yahoo_ticker = ticker
                row.data_points = merged
                row.hist_end_date = merged[-1]["date"] if merged else today_str
                row.updated_at = datetime.utcnow()
            else:
                row = BenchmarkGlobalDaily(
                    benchmark_name=name,
                    yahoo_ticker=ticker,
                    data_points=merged,
                    hist_end_date=merged[-1]["date"] if merged else today_str,
                    updated_at=datetime.utcnow(),
                )
                db.session.add(row)
            any_data_change = True

        if any_data_change:
            db.session.commit()
            BenchmarkGlobalService.bump_daily_data_version()
        elif meta_fix:
            db.session.commit()
        return any_data_change

    @staticmethod
    def get_sliced_daily_for_user(user_id: int) -> dict[str, Any]:
        """Recorte de la serie global desde la fecha de inicio del portfolio del usuario."""
        svc = BenchmarkComparisonService(user_id)
        start = svc.start_date
        if not start:
            return {}
        start_str = start.strftime("%Y-%m-%d")
        out: dict[str, Any] = {}
        for name, ticker in BENCHMARKS.items():
            row = BenchmarkGlobalDaily.query.filter_by(benchmark_name=name).first()
            if not row or not row.data_points:
                continue
            pts = [p for p in row.data_points if p.get("date") and str(p["date"]) >= start_str]
            if pts:
                out[name] = {"ticker": ticker, "data_points": pts}
        return out
