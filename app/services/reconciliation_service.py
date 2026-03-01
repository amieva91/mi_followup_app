"""
Servicio de reconciliación entre saldos bancarios e ingresos/gastos.
Calcula el ajuste dinámico por mes cuando hay dos meses consecutivos con datos de bancos.
"""
from datetime import date
from dateutil.relativedelta import relativedelta
from app import db
from app.models import Income, Expense
from app.services.bank_service import BankService
from app.services.broker_sync_service import (
    get_broker_withdrawals_by_month,
    get_broker_deposits_total_by_month,
)


def _get_prev_month(year, month):
    """Devuelve (year, month) del mes anterior."""
    d = date(year, month, 1) - relativedelta(months=1)
    return d.year, d.month


def _month_range(year, month):
    """Devuelve (start_date, end_date) para el mes dado."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = (date(year, month, 28) + relativedelta(months=1)) - relativedelta(days=1)
    return start, end


def get_income_total_for_month(user_id, year, month):
    """Total de ingresos del mes: manuales + retiradas broker (WITHDRAWAL)."""
    start, end = _month_range(year, month)
    manual = float(Income.get_total_by_period(user_id, start, end) or 0)
    broker = get_broker_withdrawals_by_month(user_id, year, month)
    return manual + broker


def get_expense_total_for_month(user_id, year, month):
    """Total de gastos del mes: manuales + depósitos broker (DEPOSIT), excl. cuotas futuras deuda."""
    start, end = _month_range(year, month)
    today = date.today()
    manual = db.session.query(db.func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.date >= start,
        Expense.date <= end,
        db.or_(
            Expense.debt_plan_id.is_(None),
            Expense.date <= today
        )
    ).scalar()
    broker = get_broker_deposits_total_by_month(user_id, year, month)
    return float(manual or 0) + broker


def get_adjustment_for_month(user_id, year, month):
    """
    Calcula el ajuste de reconciliación para un mes.

    Fórmula:
        Gastos_reales = Cash(mes-1) + Ingresos(mes) - Cash(mes)
        Ajuste = Gastos_reales - Gastos_registrados

    Requiere saldos bancarios en (year, month) y en el mes anterior.

    Returns:
        float positivo: gasto no registrado → va a Expense (Ajustes)
        float negativo: ingreso no registrado → va a Income (Ajustes)
        None: no se puede calcular (faltan datos de bancos)
    """
    cash_current = BankService.get_total_cash_by_month(user_id, year, month)
    prev_year, prev_month = _get_prev_month(year, month)
    cash_prev = BankService.get_total_cash_by_month(user_id, prev_year, prev_month)

    # Requerir que existan registros de saldo bancario en ambos meses
    if not _has_any_balance_for_month(user_id, prev_year, prev_month):
        return None
    if not _has_any_balance_for_month(user_id, year, month):
        return None

    income = get_income_total_for_month(user_id, year, month)
    expenses_recorded = get_expense_total_for_month(user_id, year, month)

    # Gastos_reales = lo que "salió" del banco
    # Cash_final = Cash_inicial + Ingresos - Gastos
    # Gastos = Cash_inicial + Ingresos - Cash_final
    real_expenses = cash_prev + income - cash_current

    adjustment = real_expenses - expenses_recorded

    return round(adjustment, 2)


def _has_any_balance_for_month(user_id, year, month):
    """Indica si existe al menos un registro de saldo para ese mes."""
    from app.models import BankBalance
    count = BankBalance.query.filter_by(
        user_id=user_id, year=year, month=month
    ).count()
    return count > 0
