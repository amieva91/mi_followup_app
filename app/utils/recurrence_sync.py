"""Sincroniza cuotas recurrentes pendientes (catch-up hasta hoy)."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func

from app import db
from app.utils.recurrence_contract import generate_recurrence_dates_after


def _catch_up_model_series(model_class, user_id: int, today: date) -> tuple[int, list[date]]:
    """Genera cuotas faltantes por serie activa. No hace commit."""
    debt_attr = hasattr(model_class, 'debt_plan_id')
    group_rows = (
        db.session.query(
            model_class.recurrence_group_id,
            func.max(model_class.date).label('max_date'),
            func.max(model_class.recurrence_early_terminated).label('early_terminated'),
        )
        .filter(
            model_class.user_id == user_id,
            model_class.is_recurring.is_(True),
            model_class.recurrence_group_id.isnot(None),
        )
        .group_by(model_class.recurrence_group_id)
        .all()
    )

    created = 0
    dates_touch: list[date] = []

    for group_id, max_date, early_terminated in group_rows:
        if not group_id or early_terminated or not max_date:
            continue

        rows = (
            model_class.query.filter_by(user_id=user_id, recurrence_group_id=group_id)
            .order_by(model_class.date.asc())
            .all()
        )
        if not rows:
            continue

        template = rows[-1]
        if debt_attr and template.debt_plan_id:
            continue

        frequency = template.recurrence_frequency
        if not frequency:
            continue

        contract_end = template.recurrence_end_date
        if contract_end and max_date >= contract_end:
            continue

        cap = today
        if contract_end and contract_end < today:
            cap = contract_end

        existing_dates = {row.date for row in rows if row.date}
        new_dates = [
            d
            for d in generate_recurrence_dates_after(
                max_date,
                frequency,
                cap,
                include_future=False,
            )
            if d not in existing_dates
        ]
        if not new_dates:
            continue

        for installment_date in new_dates:
            instance = model_class(
                user_id=user_id,
                category_id=template.category_id,
                amount=template.amount,
                description=template.description,
                date=installment_date,
                notes=template.notes,
                is_recurring=True,
                recurrence_frequency=frequency,
                recurrence_end_date=contract_end,
                recurrence_group_id=group_id,
                recurrence_early_terminated=False,
                recurrence_original_end_date=None,
            )
            if debt_attr:
                instance.debt_plan_id = None
            db.session.add(instance)
            dates_touch.append(installment_date)
            created += 1

    return created, dates_touch


def ensure_recurring_installments_current(user_id: int) -> tuple[int, list[date]]:
    """
    Crea cuotas de ingresos/gastos recurrentes que falten hasta hoy.
    Returns (created_count, dates_touch). Hace commit solo si creó filas.
    """
    from app.models import Expense, Income

    today = datetime.now().date()
    created = 0
    dates_touch: list[date] = []

    for model_class in (Expense, Income):
        n, touched = _catch_up_model_series(model_class, user_id, today)
        created += n
        dates_touch.extend(touched)

    if created:
        db.session.commit()

    return created, dates_touch


def sync_recurring_and_touch_dashboard_cache(user_id: int) -> int:
    """Catch-up recurrente; invalida/recomputa caché del dashboard solo si hubo cambios."""
    from app.services.dashboard_summary_cache import DashboardSummaryCacheService

    created, dates_touch = ensure_recurring_installments_current(user_id)
    if created:
        DashboardSummaryCacheService.touch_for_dates(user_id, dates=dates_touch)
    return created
