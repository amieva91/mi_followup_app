"""
Servicio de reconciliación entre saldos bancarios e ingresos/gastos.
Calcula el ajuste dinámico por mes cuando hay dos meses consecutivos con datos de bancos.
"""
from calendar import monthrange
from datetime import date
from dateutil.relativedelta import relativedelta
from app import db
from app.models import Income, Expense, IncomeCategory, ExpenseCategory
from app.services.bank_service import BankService
from app.services.category_helpers import (
    AJUSTES_CATEGORY_NAME,
    STOCK_MARKET_CATEGORY_NAME,
)
from app.services.broker_sync_service import (
    get_broker_withdrawals_by_month,
    get_broker_deposits_total_by_month,
)


def _get_prev_month(year, month):
    """Devuelve (year, month) del mes anterior."""
    d = date(year, month, 1) - relativedelta(months=1)
    return d.year, d.month


def _month_range(year, month):
    """Devuelve (start_date, end_date) para el mes dado (último día real del mes)."""
    start = date(year, month, 1)
    last_day = monthrange(year, month)[1]
    end = date(year, month, last_day)
    return start, end


def _reconciliation_excluded_income_category_ids(user_id):
    """
    Categorías cuyos importes en `incomes` no deben sumarse aquí: ya van por broker
    (Stock Market = WITHDRAWAL) o son sintéticos (Ajustes). Evita doble conteo.
    """
    rows = (
        db.session.query(IncomeCategory.id)
        .filter(
            IncomeCategory.user_id == user_id,
            IncomeCategory.name.in_(
                (STOCK_MARKET_CATEGORY_NAME, AJUSTES_CATEGORY_NAME)
            ),
        )
        .all()
    )
    return [r[0] for r in rows]


def _reconciliation_excluded_expense_category_ids(user_id):
    """Igual que ingresos: Stock Market (DEPOSIT) y Ajustes no duplican broker ni línea sintética."""
    rows = (
        db.session.query(ExpenseCategory.id)
        .filter(
            ExpenseCategory.user_id == user_id,
            ExpenseCategory.name.in_(
                (STOCK_MARKET_CATEGORY_NAME, AJUSTES_CATEGORY_NAME)
            ),
        )
        .all()
    )
    return [r[0] for r in rows]


def get_income_total_for_month(user_id, year, month):
    """Total de ingresos del mes: manuales + retiradas broker (WITHDRAWAL)."""
    start, end = _month_range(year, month)
    excl = _reconciliation_excluded_income_category_ids(user_id)
    q = db.session.query(db.func.sum(Income.amount)).filter(
        Income.user_id == user_id,
        Income.date >= start,
        Income.date <= end,
    )
    if excl:
        q = q.filter(~Income.category_id.in_(excl))
    manual = float(q.scalar() or 0)
    broker = get_broker_withdrawals_by_month(user_id, year, month)
    return manual + broker


def get_expense_total_for_month(user_id, year, month):
    """Total de gastos del mes: manuales + depósitos broker (DEPOSIT), excl. cuotas futuras deuda."""
    start, end = _month_range(year, month)
    today = date.today()
    excl = _reconciliation_excluded_expense_category_ids(user_id)
    q = db.session.query(db.func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.date >= start,
        Expense.date <= end,
        db.or_(
            Expense.debt_plan_id.is_(None),
            Expense.date <= today
        )
    )
    if excl:
        q = q.filter(~Expense.category_id.in_(excl))
    manual = q.scalar()
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
