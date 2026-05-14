"""
Persistencia global de cierres diarios Yahoo para el motor de estrategia global.

Job: `flask global-strategy-macro-daily-once` (cron diario tras cierre US; ver scripts/).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from flask import current_app

from app import db
from app.models.global_strategy_macro_daily import GlobalStrategyMacroDaily, GlobalStrategyMacroState
from app.services.global_strategy.macro_series_math import last_close_and_ma200, merge_point_maps
from app.services.metrics.benchmark_comparison import BenchmarkComparisonService

# Claves estables en BD (no confundir con yahoo_ticker)
MACRO_SERIES: tuple[tuple[str, str], ...] = (
    ("vix", "^VIX"),
    ("spy", "SPY"),
    ("fez", "FEZ"),
    ("asia_hk", "3188.HK"),
)


class GlobalStrategyMacroService:
    """Mantiene `global_strategy_macro_daily` + versión global para invalidación futura."""

    @staticmethod
    def get_data_version() -> int:
        st = GlobalStrategyMacroState.query.get(1)
        return int(st.data_version) if st else 0

    @staticmethod
    def bump_data_version() -> int:
        st = GlobalStrategyMacroState.get_singleton()
        st.data_version = int(st.data_version or 0) + 1
        st.updated_at = datetime.utcnow()
        db.session.commit()
        return st.data_version

    @staticmethod
    def _backfill_start(today: date, calendar_days: int) -> date:
        return today - timedelta(days=int(calendar_days))

    @staticmethod
    def refresh_daily_if_stale(force: bool = False) -> bool:
        """
        Actualiza series si no hay datos, faltan días hasta hoy, o force=True.
        Primer carga: al menos GLOBAL_STRATEGY_MACRO_BACKFILL_CALENDAR_DAYS de historia (~250+ sesiones).
        """
        today = datetime.now().date()
        today_str = today.strftime("%Y-%m-%d")
        backfill_days = int(current_app.config.get("GLOBAL_STRATEGY_MACRO_BACKFILL_CALENDAR_DAYS", 450))

        st = GlobalStrategyMacroState.get_singleton()
        cfg_mode = str(current_app.config.get("GLOBAL_STRATEGY_USA_SCORE_MODE", "vix")).strip().lower()
        if cfg_mode not in ("vix", "spy"):
            cfg_mode = "vix"
        if st.usa_score_mode != cfg_mode:
            st.usa_score_mode = cfg_mode
            st.updated_at = datetime.utcnow()
            db.session.commit()

        any_data_change = False
        meta_fix = False

        for series_key, yahoo_ticker in MACRO_SERIES:
            row = GlobalStrategyMacroDaily.query.filter_by(series_key=series_key).first()
            hist_end = (row.hist_end_date or "") if row else ""
            need = force or row is None or hist_end < today_str
            if not need:
                continue

            points = list(row.data_points) if row and row.data_points else []

            if force or not points:
                start_d = GlobalStrategyMacroService._backfill_start(today, backfill_days)
                new_data = BenchmarkComparisonService.fetch_yahoo_chart_daily_points(
                    yahoo_ticker, start_d, today
                )
                if not new_data or not new_data.get("data_points"):
                    continue
                merged = new_data["data_points"]
            else:
                last_d: Optional[str] = None
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
                new_data = BenchmarkComparisonService.fetch_yahoo_chart_daily_points(
                    yahoo_ticker, start_fetch, today
                )
                if not new_data or not new_data.get("data_points"):
                    continue
                merged = merge_point_maps(points, new_data["data_points"])

            if row:
                row.yahoo_ticker = yahoo_ticker
                row.data_points = merged
                row.hist_end_date = merged[-1]["date"] if merged else today_str
                row.updated_at = datetime.utcnow()
            else:
                row = GlobalStrategyMacroDaily(
                    series_key=series_key,
                    yahoo_ticker=yahoo_ticker,
                    data_points=merged,
                    hist_end_date=merged[-1]["date"] if merged else today_str,
                    updated_at=datetime.utcnow(),
                )
                db.session.add(row)
            any_data_change = True

        if any_data_change:
            db.session.commit()
            GlobalStrategyMacroService.bump_data_version()
        elif meta_fix:
            db.session.commit()

        return any_data_change

    @staticmethod
    def snapshot_for_scores() -> dict[str, Any]:
        """
        Lectura para capa de scoring (futuro job SG): últimos valores y MA200 por serie.
        Respeta `usa_score_mode` en estado singleton.
        """
        st = GlobalStrategyMacroState.get_singleton()
        out: dict[str, Any] = {"usa_score_mode": st.usa_score_mode, "series": {}}
        for series_key, _yahoo in MACRO_SERIES:
            row = GlobalStrategyMacroDaily.query.filter_by(series_key=series_key).first()
            if not row or not row.data_points:
                out["series"][series_key] = None
                continue
            last, ma200, last_d = last_close_and_ma200(list(row.data_points))
            n = len([p for p in row.data_points if p.get("price") is not None])
            out["series"][series_key] = {
                "yahoo_ticker": row.yahoo_ticker,
                "close": last,
                "ma200": ma200,
                "as_of_date": last_d,
                "n_closes": n,
            }
        return out
