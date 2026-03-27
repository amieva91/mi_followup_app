"""
Orquestación de flags pendientes de rebuild de cachés (HIST/NOW).

Regla:
- FULL domina NOW
- El worker procesa como máximo 1 usuario por ciclo
"""
from __future__ import annotations

from datetime import date, datetime

from app import db
from app.models.cache_rebuild_state import CacheRebuildState


class CacheRebuildStateService:
    @staticmethod
    def _get_or_create(user_id: int) -> CacheRebuildState:
        row = CacheRebuildState.query.filter_by(user_id=user_id).first()
        if row:
            return row
        row = CacheRebuildState(
            user_id=user_id,
            pending_full_history=False,
            pending_now=False,
        )
        db.session.add(row)
        db.session.flush()
        return row

    @staticmethod
    def mark_full_history(user_id: int) -> None:
        row = CacheRebuildStateService._get_or_create(user_id)
        row.pending_full_history = True
        row.pending_now = False
        row.updated_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def mark_now(user_id: int) -> None:
        row = CacheRebuildStateService._get_or_create(user_id)
        if not row.pending_full_history:
            row.pending_now = True
        row.updated_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def mark_for_dates(user_id: int, dates: list[date] | None = None, month_refs=None) -> None:
        """
        Replica el criterio actual:
        - cualquier fecha/mes pasado => FULL
        - solo hoy/mes actual => NOW
        """
        today = datetime.utcnow().date()
        any_past = False
        any_today_or_current = False

        if dates:
            for d in dates:
                if isinstance(d, datetime):
                    d = d.date()
                if not isinstance(d, date):
                    continue
                if d < today:
                    any_past = True
                elif d == today:
                    any_today_or_current = True

        if month_refs:
            for year, month in month_refs:
                try:
                    year = int(year)
                    month = int(month)
                except (TypeError, ValueError):
                    continue
                if year == today.year and month == today.month:
                    any_today_or_current = True
                else:
                    any_past = True

        if any_past:
            CacheRebuildStateService.mark_full_history(user_id)
        elif any_today_or_current:
            CacheRebuildStateService.mark_now(user_id)

    @staticmethod
    def pick_next_pending() -> CacheRebuildState | None:
        return (
            CacheRebuildState.query
            .filter(
                (CacheRebuildState.pending_full_history.is_(True))
                | (CacheRebuildState.pending_now.is_(True))
            )
            .order_by(CacheRebuildState.updated_at.asc())
            .first()
        )

    @staticmethod
    def clear_after_success(user_id: int, action: str) -> None:
        row = CacheRebuildState.query.filter_by(user_id=user_id).first()
        if not row:
            return
        if action == "full":
            row.pending_full_history = False
            row.pending_now = False
        elif action == "now":
            row.pending_now = False
        row.updated_at = datetime.utcnow()
        db.session.commit()

