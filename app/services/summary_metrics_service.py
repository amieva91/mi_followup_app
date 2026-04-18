"""
Métricas de resumen para cuadros de indicadores (Ingresos y Gastos).
Fase 6 del plan Bancos + Ajustes.
"""
from app.services.income_expense_aggregator import (
    get_income_monthly_totals_with_adjustment,
    get_expense_monthly_totals_with_adjustment,
    period_months_from_monthly_totals,
)


def get_income_summary_metrics(user_id, months=12):
    """
    Indicadores de resumen para ingresos.
    meses_con_datos: meses consecutivos del período (X en X/12), mismo divisor que medias por categoría.
    """
    monthly = get_income_monthly_totals_with_adjustment(user_id, months=months)
    totals = [m['total'] for m in monthly]
    total_periodo = sum(totals)
    period_months = period_months_from_monthly_totals(monthly)
    meses_con_datos = period_months
    media_mensual = (
        round(total_periodo / period_months, 2) if period_months > 0 else 0.0
    )

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
    meses_con_datos: meses consecutivos del período (X en X/12).
    """
    monthly = get_expense_monthly_totals_with_adjustment(user_id, months=months)
    totals = [m['total'] for m in monthly]
    total_periodo = sum(totals)
    period_months = period_months_from_monthly_totals(monthly)
    meses_con_datos = period_months
    media_mensual = (
        round(total_periodo / period_months, 2) if period_months > 0 else 0.0
    )

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
