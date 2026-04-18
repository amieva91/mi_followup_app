"""
Agregador de ingresos/gastos que incluye el ajuste de reconciliación dinámico
y los importes de broker (WITHDRAWAL→Stock Market income, DEPOSIT→Stock Market expenses).
Inyecta el ajuste calculado por ReconciliationService en totales y resúmenes por categoría.
"""
from datetime import date
from typing import Any, Dict, List

from dateutil.relativedelta import relativedelta

from app import db
from app.models import Income, Expense
from app.services.reconciliation_service import get_adjustment_for_month
from app.services.category_helpers import (
    get_or_create_ajustes_income_category,
    get_or_create_ajustes_expense_category,
    get_or_create_stock_market_income_category,
    get_or_create_stock_market_expense_category,
)
from app.services.broker_sync_service import (
    get_broker_withdrawals_by_month,
    get_broker_deposits_total_by_month,
)


def period_months_from_monthly_totals(monthly: List[Dict[str, Any]]) -> int:
    """
    Meses consecutivos del período (máx. len(monthly), típ. 12): desde el primer mes
    con total global > 0 hasta el último mes de la serie. Los meses intermedios en cero
    cuentan. Si no hay actividad, 0.
    """
    if not monthly:
        return 0
    totals = [float(m.get("total") or 0) for m in monthly]
    i_first = None
    for i, t in enumerate(totals):
        if t > 0:
            i_first = i
            break
    if i_first is None:
        return 0
    return len(monthly) - i_first


def _add_expense_average_fields(summary, period_months: int):
    """Añade average y period_months (divisor global) a padres e hijos."""
    for parent in summary:
        total = float(parent.get("total", 0) or 0)
        parent["period_months"] = period_months
        parent["average"] = (
            round(total / period_months, 2) if period_months > 0 and total else 0.0
        )
        for child in parent.get("children", []):
            ct = float(child.get("total", 0) or 0)
            child["period_months"] = period_months
            child["average"] = (
                round(ct / period_months, 2) if period_months > 0 and ct else 0.0
            )


def get_income_category_summary_with_adjustment(user_id, months=12):
    """Resumen por categoría de ingresos incluyendo ajuste y retiradas broker (Stock Market)."""
    today = date.today()
    monthly_series = get_income_monthly_totals_with_adjustment(user_id, months=months)
    period_months = period_months_from_monthly_totals(monthly_series)

    summary = Income.get_category_summary(user_id, months=months)

    # Sumar ajustes negativos (ingresos no registrados) por mes
    ajustes_total = 0.0
    broker_withdrawals_total = 0.0
    for i in range(months - 1, -1, -1):
        d = today - relativedelta(months=i)
        adj = get_adjustment_for_month(user_id, d.year, d.month)
        if adj is not None and adj < 0:
            ajustes_total += abs(adj)
        broker_withdrawals_total += get_broker_withdrawals_by_month(user_id, d.year, d.month)

    if ajustes_total > 0:
        cat = get_or_create_ajustes_income_category(user_id)
        existing = next((s for s in summary if s.get('id') == cat.id or s.get('category') == 'Ajustes'), None)
        if existing:
            existing['total'] = round(existing['total'] + ajustes_total, 2)
        else:
            summary.append({
                'id': cat.id,
                'category': cat.name,
                'icon': cat.icon,
                'color': cat.color,
                'total': round(ajustes_total, 2)
            })

    if broker_withdrawals_total > 0:
        cat = get_or_create_stock_market_income_category(user_id)
        existing = next((s for s in summary if s.get('id') == cat.id or s.get('category') == 'Stock Market'), None)
        if existing:
            existing['total'] = round(existing['total'] + broker_withdrawals_total, 2)
        else:
            summary.append({
                'id': cat.id,
                'category': cat.name,
                'icon': cat.icon,
                'color': cat.color,
                'total': round(broker_withdrawals_total, 2)
            })

    for item in summary:
        total = float(item.get("total", 0) or 0)
        item["period_months"] = period_months
        item["average"] = (
            round(total / period_months, 2) if period_months > 0 and total else 0.0
        )

    return summary


def get_expense_category_summary_with_adjustment(user_id, months=12):
    """Resumen por categoría de gastos incluyendo ajuste y depósitos broker (Stock Market)."""
    today = date.today()
    monthly_series = get_expense_monthly_totals_with_adjustment(user_id, months=months)
    period_months = period_months_from_monthly_totals(monthly_series)

    summary = Expense.get_category_summary(user_id, months=months)

    # Sumar ajustes positivos (gastos no registrados) por mes
    ajustes_total = 0.0
    broker_deposits_total = 0.0
    for i in range(months - 1, -1, -1):
        d = today - relativedelta(months=i)
        adj = get_adjustment_for_month(user_id, d.year, d.month)
        if adj is not None and adj > 0:
            ajustes_total += adj
        broker_deposits_total += get_broker_deposits_total_by_month(user_id, d.year, d.month)

    if ajustes_total > 0:
        cat = get_or_create_ajustes_expense_category(user_id)
        existing = next((s for s in summary if s.get('id') == cat.id or s.get('name') == 'Ajustes'), None)
        if existing:
            existing['total'] = round(existing['total'] + ajustes_total, 2)
        else:
            summary.append({
                'id': cat.id,
                'name': cat.name,
                'icon': cat.icon,
                'total': round(ajustes_total, 2),
                'children': []
            })

    if broker_deposits_total > 0:
        cat = get_or_create_stock_market_expense_category(user_id)
        existing = next((s for s in summary if s.get('id') == cat.id or s.get('name') == 'Stock Market'), None)
        if existing:
            existing['total'] = round(existing['total'] + broker_deposits_total, 2)
        else:
            summary.append({
                'id': cat.id,
                'name': cat.name,
                'icon': cat.icon,
                'total': round(broker_deposits_total, 2),
                'children': []
            })

    _add_expense_average_fields(summary, period_months)

    return summary


def get_income_monthly_totals_with_adjustment(user_id, months=12):
    """Totales mensuales de ingresos incluyendo ajuste y retiradas broker por mes."""
    base = Income.get_monthly_totals(user_id, months=months)
    today = date.today()

    result = []
    for i, item in enumerate(base):
        d = today - relativedelta(months=months - 1 - i)
        year, month = d.year, d.month
        adj = get_adjustment_for_month(user_id, year, month)
        extra = abs(adj) if adj is not None and adj < 0 else 0
        broker = get_broker_withdrawals_by_month(user_id, year, month)
        result.append({
            'month_label': item['month_label'],
            'total': round(item['total'] + extra + broker, 2)
        })
    return result


def get_expense_monthly_totals_with_adjustment(user_id, months=12):
    """Totales mensuales de gastos incluyendo ajuste y depósitos broker por mes."""
    base = Expense.get_monthly_totals(user_id, months=months)
    today = date.today()

    result = []
    for i, item in enumerate(base):
        d = today - relativedelta(months=months - 1 - i)
        year, month = d.year, d.month
        adj = get_adjustment_for_month(user_id, year, month)
        extra = adj if adj is not None and adj > 0 else 0
        broker = get_broker_deposits_total_by_month(user_id, year, month)
        result.append({
            'month_label': item['month_label'],
            'total': round(item['total'] + extra + broker, 2)
        })
    return result


def get_synthetic_income_entries_by_month(user_id, months=None):
    """
    Devuelve entradas sintéticas de ingresos (Ajustes y Stock Market) por mes.
    Returns: dict {(year, month): {'ajuste': amount, 'stock_market': amount, 'month_label': str}}
    Solo incluye meses con algún valor > 0.
    
    Args:
        user_id: ID del usuario
        months: Número de meses hacia atrás (None = todo el histórico desde la primera transacción)
    """
    from app.models import Transaction
    today = date.today()
    result = {}
    
    # Si months es None, calcular desde la primera transacción del usuario
    if months is None:
        first_txn = Transaction.query.filter_by(user_id=user_id).order_by(
            Transaction.transaction_date.asc()
        ).first()
        if first_txn:
            first_date = first_txn.transaction_date
            if hasattr(first_date, 'date'):
                first_date = first_date.date()
            # Calcular meses desde la primera transacción
            months = (today.year - first_date.year) * 12 + (today.month - first_date.month) + 1
        else:
            months = 12  # Default si no hay transacciones
    
    for i in range(months - 1, -1, -1):
        d = today - relativedelta(months=i)
        year, month = d.year, d.month
        
        # Ajuste negativo = ingreso no registrado
        adj = get_adjustment_for_month(user_id, year, month)
        ajuste_amount = abs(adj) if adj is not None and adj < 0 else 0
        
        # Retiradas del broker = ingreso
        stock_market_amount = get_broker_withdrawals_by_month(user_id, year, month)
        
        if ajuste_amount > 0 or stock_market_amount > 0:
            month_label = d.strftime('%b %Y')
            result[(year, month)] = {
                'ajuste': round(ajuste_amount, 2),
                'stock_market': round(stock_market_amount, 2),
                'month_label': month_label,
                'year': year,
                'month': month
            }
    
    return result


def get_synthetic_expense_entries_by_month(user_id, months=None):
    """
    Devuelve entradas sintéticas de gastos (Ajustes y Stock Market) por mes.
    Returns: dict {(year, month): {'ajuste': amount, 'stock_market': amount, 'month_label': str}}
    Solo incluye meses con algún valor > 0.
    
    Args:
        user_id: ID del usuario
        months: Número de meses hacia atrás (None = todo el histórico desde la primera transacción)
    """
    from app.models import Transaction
    today = date.today()
    result = {}
    
    # Si months es None, calcular desde la primera transacción del usuario
    if months is None:
        first_txn = Transaction.query.filter_by(user_id=user_id).order_by(
            Transaction.transaction_date.asc()
        ).first()
        if first_txn:
            first_date = first_txn.transaction_date
            if hasattr(first_date, 'date'):
                first_date = first_date.date()
            # Calcular meses desde la primera transacción
            months = (today.year - first_date.year) * 12 + (today.month - first_date.month) + 1
        else:
            months = 12  # Default si no hay transacciones
    
    for i in range(months - 1, -1, -1):
        d = today - relativedelta(months=i)
        year, month = d.year, d.month
        
        # Ajuste positivo = gasto no registrado
        adj = get_adjustment_for_month(user_id, year, month)
        ajuste_amount = adj if adj is not None and adj > 0 else 0
        
        # Depósitos al broker = gasto
        stock_market_amount = get_broker_deposits_total_by_month(user_id, year, month)
        
        if ajuste_amount > 0 or stock_market_amount > 0:
            month_label = d.strftime('%b %Y')
            result[(year, month)] = {
                'ajuste': round(ajuste_amount, 2),
                'stock_market': round(stock_market_amount, 2),
                'month_label': month_label,
                'year': year,
                'month': month
            }
    
    return result
