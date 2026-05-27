"""Terminar y reanudar series recurrentes de ingresos/gastos."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta
from sqlalchemy import func

from app import db


def _next_recurrence_date(current_date: date, frequency: str | None) -> date | None:
    if not frequency or not current_date:
        return None
    if frequency == 'daily':
        return current_date + timedelta(days=1)
    if frequency == 'weekly':
        return current_date + timedelta(weeks=1)
    if frequency == 'monthly':
        return current_date + relativedelta(months=1)
    if frequency == 'yearly':
        return current_date + relativedelta(years=1)
    return None


def generate_recurrence_dates_after(
    last_date: date,
    frequency: str | None,
    end_date: date | None = None,
    *,
    include_future: bool = False,
) -> list[date]:
    """Genera fechas de cuota estrictamente posteriores a last_date."""
    if not last_date or not frequency:
        return []

    if end_date is None:
        end_date = datetime.now().date()
    elif not include_future:
        today = datetime.now().date()
        if end_date > today:
            end_date = today

    dates: list[date] = []
    current = _next_recurrence_date(last_date, frequency)
    while current and current <= end_date:
        dates.append(current)
        current = _next_recurrence_date(current, frequency)
    return dates


def build_recurrence_group_meta(model_class, user_id: int) -> dict[str, dict]:
    """Metadatos por recurrence_group_id para la columna de acciones en listas."""
    rows = (
        db.session.query(
            model_class.recurrence_group_id,
            func.max(model_class.date).label('max_date'),
            func.max(model_class.recurrence_early_terminated).label('early_terminated'),
        )
        .filter(
            model_class.user_id == user_id,
            model_class.recurrence_group_id.isnot(None),
            model_class.is_recurring.is_(True),
        )
        .group_by(model_class.recurrence_group_id)
        .all()
    )

    meta: dict[str, dict] = {}
    for group_id, max_date, early_terminated in rows:
        if not group_id:
            continue
        sample = model_class.query.filter_by(
            user_id=user_id,
            recurrence_group_id=group_id,
        ).first()
        end_date = sample.recurrence_end_date if sample else None
        original_end = sample.recurrence_original_end_date if sample else None
        paused = bool(early_terminated) or bool(end_date and max_date and max_date == end_date)
        meta[group_id] = {
            'paused': paused,
            'resume_until': original_end,
            'effective_end': end_date,
        }
    return meta


def series_is_paused(group_meta: dict | None) -> bool:
    return bool(group_meta and group_meta.get('paused'))


def terminate_recurrence_series(model_class, user_id: int, anchor, *, allow_debt: bool = False):
    """
    Termina una serie desde la fila anchor (pivot = anchor.date).
    Returns (dates_touch, error_message).
    """
    if anchor.user_id != user_id:
        return [], 'No tienes permiso'

    if not anchor.recurrence_group_id:
        return [], 'Esta acción solo aplica a series recurrentes.'

    if getattr(anchor, 'debt_plan_id', None) and not allow_debt:
        return [], 'Esta acción no aplica a cuotas de un plan de deuda.'

    gid = anchor.recurrence_group_id
    pivot = anchor.date

    remaining = model_class.query.filter_by(
        user_id=user_id,
        recurrence_group_id=gid,
    ).all()
    if not remaining:
        return [], 'No se encontró la serie recurrente.'

    original_contract_end = remaining[0].recurrence_end_date

    future_rows = model_class.query.filter(
        model_class.user_id == user_id,
        model_class.recurrence_group_id == gid,
        model_class.date > pivot,
    ).all()

    dates_touch = [row.date for row in future_rows if row.date]
    future_ids = {row.id for row in future_rows}
    for row in future_rows:
        db.session.delete(row)

    for row in remaining:
        if row.id in future_ids or not row.date or row.date > pivot:
            continue
        if not row.recurrence_early_terminated and row.recurrence_original_end_date is None:
            if original_contract_end and original_contract_end != pivot:
                row.recurrence_original_end_date = original_contract_end
        row.recurrence_end_date = pivot
        row.recurrence_early_terminated = True
        dates_touch.append(row.date)

    return dates_touch, None


def resume_recurrence_series(model_class, user_id: int, anchor, *, allow_debt: bool = False):
    """
    Reanuda una serie terminada anticipadamente regenerando cuotas futuras.
    Returns (created_count, dates_touch, error_message).
    """
    if anchor.user_id != user_id:
        return 0, [], 'No tienes permiso'

    if not anchor.recurrence_group_id:
        return 0, [], 'Esta acción solo aplica a series recurrentes.'

    if getattr(anchor, 'debt_plan_id', None) and not allow_debt:
        return 0, [], 'Esta acción no aplica a cuotas de un plan de deuda.'

    gid = anchor.recurrence_group_id
    rows = (
        model_class.query.filter_by(user_id=user_id, recurrence_group_id=gid)
        .order_by(model_class.date.asc())
        .all()
    )
    if not rows:
        return 0, [], 'No se encontró la serie recurrente.'

    if not any(r.recurrence_early_terminated for r in rows):
        max_date = max(r.date for r in rows if r.date)
        end_date = rows[0].recurrence_end_date
        if not (end_date and max_date == end_date):
            return 0, [], 'Esta serie no está terminada.'

    template = rows[-1]
    frequency = template.recurrence_frequency
    if not frequency or not template.date:
        return 0, [], 'No se puede reanudar: falta la frecuencia de la serie.'

    restored_end = template.recurrence_original_end_date

    if restored_end:
        new_dates = generate_recurrence_dates_after(
            template.date,
            frequency,
            restored_end,
            include_future=True,
        )
    else:
        new_dates = generate_recurrence_dates_after(
            template.date,
            frequency,
            datetime.now().date(),
            include_future=False,
        )

    dates_touch: list[date] = []
    for row in rows:
        row.recurrence_end_date = restored_end
        row.recurrence_early_terminated = False
        row.recurrence_original_end_date = None
        if row.date:
            dates_touch.append(row.date)

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
            recurrence_end_date=restored_end,
            recurrence_group_id=gid,
            recurrence_early_terminated=False,
            recurrence_original_end_date=None,
        )
        if hasattr(instance, 'debt_plan_id'):
            instance.debt_plan_id = None
        db.session.add(instance)
        dates_touch.append(installment_date)

    return len(new_dates), dates_touch, None
