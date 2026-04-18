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

# Descripción fija para movimientos creados al integrar el ajuste en una categoría.
RECONCILIATION_INTEGRATION_DESCRIPTION = "Integrado desde reconciliación bancaria"


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


def is_adjustment_included_in_metrics(user_id, year, month):
    """
    Si el ajuste de reconciliación de ese mes cuenta en totales / gráficos / métricas.
    Sin fila en BD ⇒ True (comportamiento histórico).
    """
    from app.models.reconciliation_adjustment_metric_pref import (
        ReconciliationAdjustmentMetricPreference,
    )

    row = ReconciliationAdjustmentMetricPreference.query.filter_by(
        user_id=user_id, year=year, month=month
    ).first()
    if row is None:
        return True
    return bool(row.include_in_metrics)


def adjustment_amount_for_income_metrics(user_id, year, month):
    """Parte del ajuste que suma como ingreso en métricas (0 si excluido o ajuste ≥ 0)."""
    adj = get_adjustment_for_month(user_id, year, month)
    if adj is None or adj >= 0:
        return 0.0
    if not is_adjustment_included_in_metrics(user_id, year, month):
        return 0.0
    return float(abs(adj))


def adjustment_amount_for_expense_metrics(user_id, year, month):
    """Parte del ajuste que suma como gasto en métricas (0 si excluido o ajuste ≤ 0)."""
    adj = get_adjustment_for_month(user_id, year, month)
    if adj is None or adj <= 0:
        return 0.0
    if not is_adjustment_included_in_metrics(user_id, year, month):
        return 0.0
    return float(adj)


def set_adjustment_included_in_metrics(user_id, year, month, include: bool):
    """
    Persiste si el ajuste cuenta en métricas. include=True elimina la fila (vuelve al default).
    """
    from app.models.reconciliation_adjustment_metric_pref import (
        ReconciliationAdjustmentMetricPreference,
    )

    row = ReconciliationAdjustmentMetricPreference.query.filter_by(
        user_id=user_id, year=year, month=month
    ).first()
    if include:
        if row:
            db.session.delete(row)
        db.session.commit()
        return
    if row:
        row.include_in_metrics = False
    else:
        db.session.add(
            ReconciliationAdjustmentMetricPreference(
                user_id=user_id,
                year=year,
                month=month,
                include_in_metrics=False,
            )
        )
    db.session.commit()


def _integration_reserved_category_names():
    return (AJUSTES_CATEGORY_NAME, STOCK_MARKET_CATEGORY_NAME)


def _resolve_integration_expense_date(user_id, year, month, category_id):
    """
    Último día del mes si no hay gastos sin plan en esa categoría; si los hay, reutiliza
    la fecha del movimiento más reciente (misma categoría, mismo mes, debt_plan_id nulo).
    """
    start, end = _month_range(year, month)
    row = (
        Expense.query.filter(
            Expense.user_id == user_id,
            Expense.category_id == category_id,
            Expense.date >= start,
            Expense.date <= end,
            Expense.debt_plan_id.is_(None),
        )
        .order_by(Expense.date.desc(), Expense.id.desc())
        .first()
    )
    if row:
        return row.date
    last_day = monthrange(year, month)[1]
    return date(year, month, last_day)


def _resolve_integration_income_date(user_id, year, month, category_id):
    start, end = _month_range(year, month)
    row = (
        Income.query.filter(
            Income.user_id == user_id,
            Income.category_id == category_id,
            Income.date >= start,
            Income.date <= end,
        )
        .order_by(Income.date.desc(), Income.id.desc())
        .first()
    )
    if row:
        return row.date
    last_day = monthrange(year, month)[1]
    return date(year, month, last_day)


def _expenses_no_debt_in_category_month(user_id, year, month, category_id):
    """Gastos del mes/categoría sin plan de deuda."""
    start, end = _month_range(year, month)
    return (
        Expense.query.filter(
            Expense.user_id == user_id,
            Expense.category_id == category_id,
            Expense.date >= start,
            Expense.date <= end,
            Expense.debt_plan_id.is_(None),
        )
        .order_by(Expense.date.desc(), Expense.id.desc())
        .all()
    )


def _pick_expense_merge_target(rows):
    """
    Prioriza una fila de serie recurrente en el mes; si no hay, una única fila.
    Varias filas sin recurrencia => None (crear movimiento aparte).
    """
    if not rows:
        return None
    recurring = [r for r in rows if r.recurrence_group_id]
    if recurring:
        return max(recurring, key=lambda r: (r.date, r.id))
    if len(rows) == 1:
        return rows[0]
    return None


def _incomes_in_category_month(user_id, year, month, category_id):
    start, end = _month_range(year, month)
    return (
        Income.query.filter(
            Income.user_id == user_id,
            Income.category_id == category_id,
            Income.date >= start,
            Income.date <= end,
        )
        .order_by(Income.date.desc(), Income.id.desc())
        .all()
    )


def _pick_income_merge_target(rows):
    if not rows:
        return None
    recurring = [r for r in rows if r.recurrence_group_id]
    if recurring:
        return max(recurring, key=lambda r: (r.date, r.id))
    if len(rows) == 1:
        return rows[0]
    return None


def integrate_reconciliation_adjustment_as_expense(user_id, year, month, category_id):
    """
    Integra el ajuste positivo de gasto: suma a un gasto existente del mes (prioriza serie
    recurrente) o crea una línea nueva si no aplica fusión.

    Returns:
        tuple: (Expense | None, str | None, bool, float)
        — (objeto, None, merged, importe_aplicado) si OK; (None, mensaje, False, 0.0) si error.
    """
    if not year or not month or month < 1 or month > 12:
        return None, "Mes o año inválidos.", False, 0.0

    adj = get_adjustment_for_month(user_id, year, month)
    if adj is None:
        return None, "No se puede integrar: faltan saldos bancarios en este mes o en el anterior.", False, 0.0

    if adj <= 0:
        return None, "No hay ajuste de gasto pendiente en este mes (el ajuste no es positivo).", False, 0.0

    cat = ExpenseCategory.query.filter_by(id=category_id, user_id=user_id).first()
    if not cat:
        return None, "Categoría no válida.", False, 0.0

    if cat.name in _integration_reserved_category_names():
        return None, "No se puede integrar en la categoría Ajustes ni en Stock Market.", False, 0.0

    amount = round(float(adj), 2)
    if amount <= 0:
        return None, "Importe de ajuste no válido.", False, 0.0

    rows = _expenses_no_debt_in_category_month(user_id, year, month, category_id)
    target = _pick_expense_merge_target(rows)
    if target is not None:
        target.amount = round(float(target.amount) + amount, 2)
        db.session.commit()
        return target, None, True, amount

    d = _resolve_integration_expense_date(user_id, year, month, category_id)
    expense = Expense(
        user_id=user_id,
        category_id=category_id,
        amount=amount,
        description=RECONCILIATION_INTEGRATION_DESCRIPTION,
        date=d,
        notes=None,
        debt_plan_id=None,
        is_recurring=False,
        recurrence_frequency=None,
        recurrence_end_date=None,
        recurrence_group_id=None,
    )
    db.session.add(expense)
    db.session.commit()
    return expense, None, False, amount


def integrate_reconciliation_adjustment_as_income(user_id, year, month, category_id):
    """
    Integra el ajuste negativo (ingreso no registrado): suma a un ingreso del mes si aplica
    la misma regla de fusión que en gastos, o crea línea nueva.

    Returns:
        tuple: (Income | None, str | None, bool, float)
    """
    if not year or not month or month < 1 or month > 12:
        return None, "Mes o año inválidos.", False, 0.0

    adj = get_adjustment_for_month(user_id, year, month)
    if adj is None:
        return None, "No se puede integrar: faltan saldos bancarios en este mes o en el anterior.", False, 0.0

    if adj >= 0:
        return None, "No hay ajuste de ingreso pendiente en este mes (el ajuste no es negativo).", False, 0.0

    cat = IncomeCategory.query.filter_by(id=category_id, user_id=user_id).first()
    if not cat:
        return None, "Categoría no válida.", False, 0.0

    if cat.name in _integration_reserved_category_names():
        return None, "No se puede integrar en la categoría Ajustes ni en Stock Market.", False, 0.0

    amount = round(float(abs(adj)), 2)
    if amount <= 0:
        return None, "Importe de ajuste no válido.", False, 0.0

    rows = _incomes_in_category_month(user_id, year, month, category_id)
    target = _pick_income_merge_target(rows)
    if target is not None:
        target.amount = round(float(target.amount) + amount, 2)
        db.session.commit()
        return target, None, True, amount

    d = _resolve_integration_income_date(user_id, year, month, category_id)
    income = Income(
        user_id=user_id,
        category_id=category_id,
        amount=amount,
        description=RECONCILIATION_INTEGRATION_DESCRIPTION,
        date=d,
        notes=None,
        is_recurring=False,
        recurrence_frequency=None,
        recurrence_end_date=None,
        recurrence_group_id=None,
    )
    db.session.add(income)
    db.session.commit()
    return income, None, False, amount
