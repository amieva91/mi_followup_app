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
from app.services.reconciliation_service import (
    adjustment_amount_for_expense_metrics,
    adjustment_amount_for_income_metrics,
    get_adjustment_for_month,
    is_adjustment_included_in_metrics,
)
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


def _sort_income_category_summary_by_total(summary: List[Dict[str, Any]]) -> None:
    """Mayor total a menor (últimos N meses)."""
    summary.sort(key=lambda x: float(x.get("total") or 0), reverse=True)


def _direct_average(total: float, period_months: int, fallback: float = 0.0) -> float:
    if period_months > 0 and total > 0:
        return round(total / period_months, 2)
    return float(fallback or 0.0)


def flatten_dashboard_category_medias(summary: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filas para la tarjeta «Medias por categoría» del dashboard.
    Misma lógica en ingresos y gastos: padre e hijas por separado, solo importe directo
    (sin agregar hijas en el padre). Omite categorías sin movimiento directo.
    """
    rows: List[Dict[str, Any]] = []
    for parent in summary:
        label = parent.get('category') or parent.get('name')
        children = parent.get('children') or []
        period_months = int(parent.get('period_months') or 0)

        if children:
            children_total = sum(float(c.get('total', 0) or 0) for c in children)
            parent_direct = float(parent.get('total', 0) or 0) - children_total
            if parent_direct > 0.009:
                rows.append({
                    'id': parent['id'],
                    'name': label,
                    'icon': parent.get('icon'),
                    'total': round(parent_direct, 2),
                    'average': _direct_average(parent_direct, period_months),
                })
            for child in children:
                child_total = float(child.get('total', 0) or 0)
                if child_total <= 0.009:
                    continue
                child_label = child.get('category') or child.get('name')
                child_pm = int(child.get('period_months') or period_months)
                rows.append({
                    'id': child['id'],
                    'name': child_label,
                    'icon': child.get('icon'),
                    'total': round(child_total, 2),
                    'average': _direct_average(
                        child_total,
                        child_pm,
                        fallback=child.get('average', 0),
                    ),
                })
        else:
            total = float(parent.get('total', 0) or 0)
            if total <= 0.009:
                continue
            rows.append({
                'id': parent['id'],
                'name': label,
                'icon': parent.get('icon'),
                'total': round(total, 2),
                'average': float(parent.get('average') or _direct_average(total, period_months)),
            })

    rows.sort(key=lambda r: float(r.get('average') or 0), reverse=True)
    return rows


def _inject_broker_stock_market_summary(
    summary: List[Dict[str, Any]],
    cat,
    amount: float,
    *,
    label_key: str,
) -> None:
    """
    Inyecta totales broker en el resumen respetando parent_id de Stock Market.
    Si tiene padre, aparece como hijo; si no, como categoría raíz.
    """
    if amount <= 0:
        return
    amount = round(float(amount), 2)
    child_row = {
        'id': cat.id,
        label_key: cat.name,
        'icon': cat.icon,
        'total': amount,
        'is_stock_market': True,
        'is_synthetic': True,
    }
    if label_key == 'category':
        child_row['color'] = cat.color

    if not cat.parent_id:
        existing = next((s for s in summary if s.get('id') == cat.id), None)
        if existing:
            existing['total'] = round(float(existing.get('total', 0)) + amount, 2)
            existing['is_stock_market'] = True
        else:
            row = dict(child_row)
            row['children'] = []
            summary.append(row)
        return

    parent = cat.parent
    if not parent:
        existing = next((s for s in summary if s.get('id') == cat.id), None)
        if existing:
            existing['total'] = round(float(existing.get('total', 0)) + amount, 2)
        else:
            summary.append({**child_row, 'children': []})
        return

    parent_row = next((s for s in summary if s.get('id') == parent.id), None)
    if parent_row:
        children = parent_row.setdefault('children', [])
        existing_child = next((c for c in children if c.get('id') == cat.id), None)
        if existing_child:
            existing_child['total'] = round(float(existing_child.get('total', 0)) + amount, 2)
        else:
            children.append(dict(child_row))
        parent_row['total'] = round(float(parent_row.get('total', 0)) + amount, 2)
    else:
        parent_entry = {
            'id': parent.id,
            label_key: parent.name,
            'icon': parent.icon,
            'total': amount,
            'children': [dict(child_row)],
        }
        if label_key == 'category':
            parent_entry['color'] = parent.color
        summary.append(parent_entry)


def _apply_income_summary_averages(summary: List[Dict[str, Any]], period_months: int) -> None:
    for item in summary:
        total = float(item.get('total', 0) or 0)
        item['period_months'] = period_months
        item['average'] = (
            round(total / period_months, 2) if period_months > 0 and total else 0.0
        )
        for child in item.get('children', []):
            ct = float(child.get('total', 0) or 0)
            child['period_months'] = period_months
            child['average'] = (
                round(ct / period_months, 2) if period_months > 0 and ct else 0.0
            )


def flatten_income_category_chips_sorted(summary: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Chips de resumen de ingresos (incluye hijos y Stock Market bajo su padre)."""
    rows: List[Dict[str, Any]] = []
    for parent in summary:
        label = parent.get('category') or parent.get('name')
        children = parent.get('children') or []
        if children:
            children_total = sum(float(c.get('total', 0) or 0) for c in children)
            parent_direct = float(parent.get('total', 0) or 0) - children_total
            if parent_direct > 0.009:
                rows.append({
                    'id': parent['id'],
                    'name': label,
                    'icon': parent.get('icon'),
                    'total': round(parent_direct, 2),
                    'average': parent.get('average', 0),
                    'is_ajustes': label == 'Ajustes',
                    'is_stock_market': False,
                    'parent_name': None,
                })
            for child in children:
                child_label = child.get('category') or child.get('name')
                rows.append({
                    'id': child['id'],
                    'name': child_label,
                    'icon': child.get('icon'),
                    'total': child['total'],
                    'average': child.get('average', 0),
                    'is_ajustes': False,
                    'is_stock_market': child.get('is_stock_market', False),
                    'parent_name': label if child.get('is_stock_market') else None,
                })
        else:
            rows.append({
                'id': parent['id'],
                'name': label,
                'icon': parent.get('icon'),
                'total': parent['total'],
                'average': parent.get('average', 0),
                'is_ajustes': label == 'Ajustes',
                'is_stock_market': parent.get('is_stock_market', False),
                'parent_name': None,
            })
    rows.sort(key=lambda r: float(r.get('total') or 0), reverse=True)
    return rows


def flatten_expense_category_chips_sorted(summary: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filas listas para la UI de resumen (un chip por categoría mostrada),
    ordenadas por total descendente (mayor gasto primero).
    """
    rows: List[Dict[str, Any]] = []
    for parent in summary:
        children = parent.get("children") or []
        if children:
            for c in children:
                rows.append(
                    {
                        "id": c["id"],
                        "name": c["name"],
                        "icon": c.get("icon"),
                        "total": c["total"],
                        "average": c["average"],
                        "is_ajustes": False,
                        "is_stock_market": c.get("is_stock_market", False),
                        "parent_name": parent.get("name") if c.get("is_stock_market") else None,
                    }
                )
        else:
            rows.append(
                {
                    "id": parent["id"],
                    "name": parent["name"],
                    "icon": parent.get("icon"),
                    "total": parent["total"],
                    "average": parent["average"],
                    "is_ajustes": parent.get("name") == "Ajustes",
                    "is_stock_market": parent.get("is_stock_market", False),
                    "parent_name": None,
                }
            )
    rows.sort(key=lambda r: float(r.get("total") or 0), reverse=True)
    return rows


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
        ajustes_total += adjustment_amount_for_income_metrics(user_id, d.year, d.month)
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
        _inject_broker_stock_market_summary(
            summary,
            cat,
            broker_withdrawals_total,
            label_key='category',
        )

    _apply_income_summary_averages(summary, period_months)
    _sort_income_category_summary_by_total(summary)
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
        ajustes_total += adjustment_amount_for_expense_metrics(user_id, d.year, d.month)
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
        _inject_broker_stock_market_summary(
            summary,
            cat,
            broker_deposits_total,
            label_key='name',
        )

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
        extra = adjustment_amount_for_income_metrics(user_id, year, month)
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
        extra = adjustment_amount_for_expense_metrics(user_id, year, month)
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
            inc_metrics = (
                is_adjustment_included_in_metrics(user_id, year, month)
                if ajuste_amount > 0
                else True
            )
            result[(year, month)] = {
                'ajuste': round(ajuste_amount, 2),
                'stock_market': round(stock_market_amount, 2),
                'month_label': month_label,
                'year': year,
                'month': month,
                'include_adjustment_in_metrics': inc_metrics,
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
            inc_metrics = (
                is_adjustment_included_in_metrics(user_id, year, month)
                if ajuste_amount > 0
                else True
            )
            result[(year, month)] = {
                'ajuste': round(ajuste_amount, 2),
                'stock_market': round(stock_market_amount, 2),
                'month_label': month_label,
                'year': year,
                'month': month,
                'include_adjustment_in_metrics': inc_metrics,
            }
    
    return result
