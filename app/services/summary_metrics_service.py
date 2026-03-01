"""
Métricas de resumen para cuadros de indicadores (Ingresos y Gastos).
Fase 6 del plan Bancos + Ajustes.
"""
from datetime import date
from dateutil.relativedelta import relativedelta
from app.services.income_expense_aggregator import (
    get_income_monthly_totals_with_adjustment,
    get_expense_monthly_totals_with_adjustment,
)


def get_income_summary_metrics(user_id, months=12):
    """
    Indicadores de resumen para ingresos.
    Returns: dict con media_mensual, total_periodo, mes_max (label, amount), meses_con_datos, tendencia
    """
    monthly = get_income_monthly_totals_with_adjustment(user_id, months=months)
    totals = [m['total'] for m in monthly]
    total_periodo = sum(totals)
    meses_con_datos = sum(1 for t in totals if t > 0)
    media_mensual = round(total_periodo / meses_con_datos, 2) if meses_con_datos > 0 else 0.0

    mes_max = {'label': '—', 'amount': 0.0}
    if totals:
        max_val = max(totals)
        if max_val > 0:
            idx = totals.index(max_val)
            mes_max = {'label': monthly[idx]['month_label'], 'amount': round(max_val, 2)}

    tendencia = '≈'
    if len(monthly) >= 2 and media_mensual > 0:
        ultimo = monthly[-1]['total']
        if ultimo > media_mensual * 1.05:
            tendencia = '↑'
        elif ultimo < media_mensual * 0.95:
            tendencia = '↓'

    return {
        'media_mensual': media_mensual,
        'total_periodo': round(total_periodo, 2),
        'mes_max': mes_max,
        'meses_con_datos': meses_con_datos,
        'tendencia': tendencia,
    }


def get_expense_summary_metrics(user_id, months=12):
    """
    Indicadores de resumen para gastos.
    Returns: dict con media_mensual, total_periodo, mes_max (label, amount), meses_con_datos, tendencia
    """
    monthly = get_expense_monthly_totals_with_adjustment(user_id, months=months)
    totals = [m['total'] for m in monthly]
    total_periodo = sum(totals)
    meses_con_datos = sum(1 for t in totals if t > 0)
    media_mensual = round(total_periodo / meses_con_datos, 2) if meses_con_datos > 0 else 0.0

    mes_max = {'label': '—', 'amount': 0.0}
    if totals:
        max_val = max(totals)
        if max_val > 0:
            idx = totals.index(max_val)
            mes_max = {'label': monthly[idx]['month_label'], 'amount': round(max_val, 2)}

    tendencia = '≈'
    if len(monthly) >= 2 and media_mensual > 0:
        ultimo = monthly[-1]['total']
        if ultimo > media_mensual * 1.05:
            tendencia = '↑'
        elif ultimo < media_mensual * 0.95:
            tendencia = '↓'

    return {
        'media_mensual': media_mensual,
        'total_periodo': round(total_periodo, 2),
        'mes_max': mes_max,
        'meses_con_datos': meses_con_datos,
        'tendencia': tendencia,
    }
