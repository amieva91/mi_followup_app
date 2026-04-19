"""
Proyección de planificación de gastos: ingreso medio, gastos fijos por categoría, saldo mensual, DSR.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from dateutil.relativedelta import relativedelta

from app import db
from app.models import ExpenseCategory
from app.models.spending_plan import (
    SpendingPlanFixedCategory,
    SpendingPlanGoal,
    SpendingPlanSettings,
)
from app.services.spending_plan_scheduler import (
    PLAN_WINDOW_MONTHS,
    build_candidate_goal,
    compute_plan_schedule,
    parse_generic_pay_options,
)
from app.services.bank_service import BankService
from app.services.income_expense_aggregator import (
    get_expense_category_summary_with_adjustment,
    get_income_monthly_totals_with_adjustment,
    period_months_from_monthly_totals,
)


def _get_or_create_settings(user_id: int) -> SpendingPlanSettings:
    row = SpendingPlanSettings.query.filter_by(user_id=user_id).first()
    if row:
        return row
    row = SpendingPlanSettings(user_id=user_id, max_dsr_percent=35.0, horizon_months=12)
    db.session.add(row)
    db.session.commit()
    return row


def get_avg_monthly_income(user_id: int, months: int = 12) -> float:
    """Media mensual alineada con el resumen de ingresos (mismo período y divisor)."""
    rows = get_income_monthly_totals_with_adjustment(user_id, months=months)
    if not rows:
        return 0.0
    pm = period_months_from_monthly_totals(rows)
    if pm <= 0:
        return 0.0
    return round(sum(float(r["total"]) for r in rows) / pm, 2)


def _flatten_expense_averages(summary: List[dict]) -> Dict[int, float]:
    """id categoría -> media mensual (€)."""
    out: Dict[int, float] = {}
    for parent in summary:
        pid = parent.get("id")
        if pid is not None:
            out[int(pid)] = float(parent.get("average") or 0)
        for child in parent.get("children") or []:
            cid = child.get("id")
            if cid is not None:
                out[int(cid)] = float(child.get("average") or 0)
    return out


def get_fixed_category_ids(user_id: int) -> List[int]:
    rows = SpendingPlanFixedCategory.query.filter_by(user_id=user_id).all()
    return [r.expense_category_id for r in rows]


def set_fixed_categories(user_id: int, category_ids: List[int]) -> None:
    """Sustituye la lista de categorías fijas; valida que pertenezcan al usuario."""
    ids = sorted({int(x) for x in category_ids if x is not None})
    if ids:
        n = (
            ExpenseCategory.query.filter(
                ExpenseCategory.user_id == user_id,
                ExpenseCategory.id.in_(ids),
            ).count()
        )
        if n != len(ids):
            raise ValueError("Alguna categoría no existe o no es tuya.")
    SpendingPlanFixedCategory.query.filter_by(user_id=user_id).delete()
    for cid in ids:
        db.session.add(
            SpendingPlanFixedCategory(user_id=user_id, expense_category_id=cid)
        )
    db.session.commit()


def compute_fixed_expenses_monthly(user_id: int, category_ids: List[int]) -> tuple[float, List[dict]]:
    """
    Suma de medias mensuales de las categorías seleccionadas.
    Si se elige padre e hijo de la misma rama, se puede duplicar: la UI lo advertirá.
    """
    if not category_ids:
        return 0.0, []
    summary = get_expense_category_summary_with_adjustment(user_id, months=12)
    av = _flatten_expense_averages(summary)
    lines: List[dict] = []
    total = 0.0
    for cid in category_ids:
        cid = int(cid)
        amt = av.get(cid)
        if amt is None:
            cat = ExpenseCategory.query.filter_by(id=cid, user_id=user_id).first()
            name = cat.full_name if cat else f"#{cid}"
            amt = 0.0
        else:
            cat = ExpenseCategory.query.filter_by(id=cid, user_id=user_id).first()
            name = cat.full_name if cat else f"#{cid}"
        total += amt
        lines.append({"category_id": cid, "name": name, "average_monthly": round(amt, 2)})
    return round(total, 2), lines


def get_current_bank_cash(user_id: int) -> float:
    """Efectivo total del mes actual (suma bancos)."""
    today = date.today()
    return float(BankService.get_total_cash_by_month(user_id, today.year, today.month) or 0)


def _sum_mortgage_initial_outlays(user_id: int) -> float:
    """Suma de `initial_outlay` en objetivos tipo hipoteca (entrada + tasación de simulador)."""
    total = 0.0
    goals = SpendingPlanGoal.query.filter_by(user_id=user_id, goal_type="mortgage").all()
    for g in goals:
        if not g.extra_json:
            continue
        try:
            data = json.loads(g.extra_json)
            v = data.get("initial_outlay")
            if v is not None:
                total += float(v)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return round(total, 2)


@dataclass
class MonthProjection:
    month_label: str
    month_index: int
    income: float
    fixed_expenses: float
    goals_monthly: float
    surplus: float
    ending_cash: float
    max_debt_payment: float
    dsr_margin: float


def _months_to_spread(today: date, target: Optional[date], horizon_months: int) -> int:
    """Meses para repartir el coste del objetivo (mínimo 1)."""
    if target is None:
        return max(1, int(horizon_months))
    if target <= today:
        return 1
    m = (target.year - today.year) * 12 + (target.month - today.month)
    return max(1, m)


def goal_monthly_amount(goal: SpendingPlanGoal, today: date, horizon_months: int) -> Tuple[float, float]:
    """
    (cuota mensual desde efectivo, cuota que consume cupo DSR).
    Genéricos y cuota hipoteca: solo DSR (0 efectivo). La entrada hipotecaria va aparte al saldo.
    """
    months = _months_to_spread(today, goal.target_date, horizon_months)
    if goal.goal_type == "mortgage" and goal.extra_json:
        try:
            data = json.loads(goal.extra_json)
            mp = data.get("monthly_payment")
            if mp is not None and float(mp) > 0:
                v = round(float(mp), 2)
                return 0.0, v
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    base = round(goal.amount_total / months, 2) if months > 0 else float(goal.amount_total or 0)
    if goal.goal_type == "mortgage":
        return 0.0, base
    return 0.0, base


def sum_goal_monthlies(
    user_id: int, horizon_months: int
) -> Tuple[float, float, List[dict]]:
    """
    Suma de cuotas mensuales estimadas (efectivo ~0 salvo modelo antiguo; DSR = genéricos + hipoteca).
    """
    goals = (
        SpendingPlanGoal.query.filter_by(user_id=user_id)
        .order_by(SpendingPlanGoal.priority.asc(), SpendingPlanGoal.id.asc())
        .all()
    )
    today = date.today()
    cash_tot = 0.0
    dsr_tot = 0.0
    lines: List[dict] = []
    for g in goals:
        c, d = goal_monthly_amount(g, today, horizon_months)
        cash_tot += c
        dsr_tot += d
        row = {
            "id": g.id,
            "title": g.title,
            "priority": g.priority,
            "goal_type": g.goal_type,
            "amount_total": g.amount_total,
            "target_date": g.target_date.isoformat() if g.target_date else None,
            "monthly_cash": c,
            "monthly_dsr": d,
        }
        if g.goal_type == "generic":
            pm, im = parse_generic_pay_options(g.extra_json)
            row["pay_mode"] = pm
            row["installment_months"] = im
        lines.append(row)
    return round(cash_tot, 2), round(dsr_tot, 2), lines


def build_monthly_projection(
    income_avg: float,
    fixed_monthly: float,
    goals_monthly_display: float,
    goals_dsr_monthly: float,
    starting_cash: float,
    max_dsr_percent: float,
    horizon_months: int = 12,
) -> List[MonthProjection]:
    """
    Vista sin plan detallado: cuota máx. DSR y margen respecto a la suma DSR estimada de objetivos.
    Superávit de liquidez ≈ ingreso − fijos (los objetivos no descuentan del efectivo salvo entradas en plan completo).
    """
    out: List[MonthProjection] = []
    max_pay = round(income_avg * (max_dsr_percent / 100.0), 2) if income_avg > 0 else 0.0
    cash = starting_cash
    today = date.today()

    for i in range(horizon_months):
        d = today + relativedelta(months=i)
        label = d.strftime("%b %Y")
        surplus = round(income_avg - fixed_monthly, 2)
        cash = round(cash + surplus, 2)
        margin = round(max_pay - goals_dsr_monthly, 2)
        out.append(
            MonthProjection(
                month_label=label,
                month_index=i + 1,
                income=income_avg,
                fixed_expenses=fixed_monthly,
                goals_monthly=goals_monthly_display,
                surplus=surplus,
                ending_cash=cash,
                max_debt_payment=max_pay,
                dsr_margin=margin,
            )
        )
    return out


def get_spending_plan_page_data(user_id: int) -> Dict[str, Any]:
    """Datos para la plantilla /planificacion."""
    settings = _get_or_create_settings(user_id)
    try:
        db.session.refresh(settings)
    except Exception:
        pass
    max_dsr_pct = float(settings.max_dsr_percent or 35.0)
    max_dsr_pct = max(1.0, min(80.0, max_dsr_pct))

    fixed_ids = get_fixed_category_ids(user_id)
    income_avg = get_avg_monthly_income(user_id, 12)
    fixed_total, fixed_lines = compute_fixed_expenses_monthly(user_id, fixed_ids)
    bank_cash_gross = get_current_bank_cash(user_id)
    mortgage_entry_outlays = _sum_mortgage_initial_outlays(user_id)
    cash0 = max(0.0, round(bank_cash_gross - mortgage_entry_outlays, 2))
    goals_cash, goals_dsr, goal_lines = sum_goal_monthlies(
        user_id, min(settings.horizon_months, PLAN_WINDOW_MONTHS)
    )

    goals_db = (
        SpendingPlanGoal.query.filter_by(user_id=user_id)
        .order_by(SpendingPlanGoal.priority.asc(), SpendingPlanGoal.id.asc())
        .all()
    )
    sch = compute_plan_schedule(
        today=date.today(),
        income_avg=income_avg,
        fixed_monthly=fixed_total,
        starting_cash=bank_cash_gross,
        max_dsr_percent=max_dsr_pct,
        goals=goals_db,
    )
    h = min(settings.horizon_months, PLAN_WINDOW_MONTHS)
    months: List[MonthProjection] = []
    max_pay = (
        round(income_avg * (max_dsr_pct / 100.0), 2) if income_avg > 0 else 0.0
    )
    if sch.ok and len(sch.surplus_monthly) >= h:
        for i in range(h):
            d = date.today() + relativedelta(months=i)
            label = d.strftime("%b %Y")
            g_m = (
                sch.mortgage_payments_monthly[i]
                + sch.generic_payments_monthly[i]
                + sch.initial_outlay_by_month[i]
            )
            margin = round(
                max_pay
                - sch.mortgage_payments_monthly[i]
                - sch.generic_payments_monthly[i],
                2,
            )
            months.append(
                MonthProjection(
                    month_label=label,
                    month_index=i + 1,
                    income=income_avg,
                    fixed_expenses=fixed_total,
                    goals_monthly=round(g_m, 2),
                    surplus=sch.surplus_monthly[i],
                    ending_cash=sch.cash_balance_monthly[i],
                    max_debt_payment=max_pay,
                    dsr_margin=margin,
                )
            )
    else:
        months = build_monthly_projection(
            income_avg,
            fixed_total,
            goals_cash + goals_dsr,
            goals_dsr,
            cash0,
            max_dsr_pct,
            h,
        )

    categories = ExpenseCategory.query.filter_by(user_id=user_id).order_by(
        ExpenseCategory.name
    ).all()
    cat_options = [{"id": c.id, "label": c.full_name} for c in categories]

    generic_goals_modal = [
        {
            "id": gl["id"],
            "title": gl["title"],
            "priority": gl["priority"],
            "amount_total": gl["amount_total"],
            "target_date": gl["target_date"],
            "installment_field": installment_field_for_ui(
                gl.get("pay_mode"), gl.get("installment_months")
            ),
        }
        for gl in goal_lines
        if gl["goal_type"] == "generic"
    ]

    schedule_month_labels: List[str] = []
    for i in range(PLAN_WINDOW_MONTHS):
        d = date.today() + relativedelta(months=i)
        schedule_month_labels.append(d.strftime("%b %Y"))

    return {
        "settings": settings,
        "fixed_category_ids": fixed_ids,
        "income_avg": income_avg,
        "fixed_total": fixed_total,
        "fixed_lines": fixed_lines,
        "starting_cash": cash0,
        "bank_cash_gross": bank_cash_gross,
        "mortgage_entry_outlays_total": mortgage_entry_outlays,
        "goals_total_monthly": round(goals_cash + goals_dsr, 2),
        "goals_dsr_monthly": goals_dsr,
        "goal_lines": goal_lines,
        "generic_goals_modal": generic_goals_modal,
        "months": months,
        "category_options": cat_options,
        "plan_schedule": sch,
        "plan_window_months": PLAN_WINDOW_MONTHS,
        "schedule_month_labels": schedule_month_labels,
    }


def installment_field_for_ui(
    pay_mode: Optional[str], installment_months: Optional[int]
) -> str:
    """Valor del campo único N.º cuotas: vacío=auto, 1=pago único, ≥2=cuotas."""
    pm = (pay_mode or "auto").strip().lower()
    if pm == "lump":
        return "1"
    if pm == "installments" and installment_months is not None:
        try:
            return str(max(1, int(installment_months)))
        except (TypeError, ValueError):
            return ""
    return ""


def pay_options_from_installment_field(
    raw: Optional[str],
) -> Tuple[str, Optional[int]]:
    """
    Interpreta el campo único de cuotas del formulario.
    Vacío → automático; 1 → pago único; 2–60 → cuotas en N meses.
    """
    if raw is None or str(raw).strip() == "":
        return "auto", None
    try:
        n = int(str(raw).strip())
    except ValueError as e:
        raise ValueError(
            "N.º cuotas: introduce un número entero o déjalo vacío para automático."
        ) from e
    if n < 1:
        raise ValueError("N.º cuotas debe ser al menos 1, o vacío para automático.")
    n = min(60, n)
    if n == 1:
        return "lump", None
    return "installments", n


def _generic_extra_json(
    pay_mode: Optional[str], installment_months: Optional[int]
) -> str:
    raw_pm = (pay_mode or "").strip().lower()
    if not raw_pm:
        pm = "auto"
    elif raw_pm in ("lump", "installments", "auto"):
        pm = raw_pm
    else:
        pm = "auto"
    im: Optional[int] = None
    if pm == "installments" and installment_months is not None:
        if str(installment_months).strip() != "":
            try:
                im = max(1, int(installment_months))
            except (TypeError, ValueError):
                im = None
    return json.dumps({"pay_mode": pm, "installment_months": im}, ensure_ascii=False)


def add_goal(
    user_id: int,
    title: str,
    amount_total: float,
    priority: int,
    target_date: Optional[date],
    goal_type: str = "generic",
    extra_json: Optional[str] = None,
    pay_mode: Optional[str] = None,
    installment_months: Optional[int] = None,
) -> SpendingPlanGoal:
    title = (title or "").strip()
    if not title:
        raise ValueError("El nombre del objetivo es obligatorio.")
    amt = float(amount_total)
    if amt <= 0:
        raise ValueError("El importe debe ser mayor que cero.")
    pr = int(priority)
    if pr < 1 or pr > 5:
        raise ValueError("La prioridad debe estar entre 1 y 5 (1 = más alta).")
    gt = (goal_type or "generic").strip().lower()
    if gt not in ("generic", "mortgage"):
        gt = "generic"
    extra: Optional[str] = None
    if gt == "generic":
        extra = _generic_extra_json(pay_mode, installment_months)
    elif extra_json is not None:
        raw = str(extra_json).strip()
        if raw:
            if len(raw) > 32000:
                raise ValueError("Datos extra demasiado largos.")
            try:
                json.loads(raw)
            except json.JSONDecodeError:
                raise ValueError("extra_json no es JSON válido.")
            extra = raw

    settings = _get_or_create_settings(user_id)
    fixed_ids = get_fixed_category_ids(user_id)
    income_avg = get_avg_monthly_income(user_id, 12)
    fixed_total, _ = compute_fixed_expenses_monthly(user_id, fixed_ids)
    bank_gross = get_current_bank_cash(user_id)
    existing = SpendingPlanGoal.query.filter_by(user_id=user_id).all()
    cand = build_candidate_goal(
        title=title,
        goal_type=gt,
        priority=pr,
        amount_total=amt,
        target_date=target_date,
        extra_json=extra,
    )
    merged = existing + [cand]
    sch = compute_plan_schedule(
        today=date.today(),
        income_avg=income_avg,
        fixed_monthly=fixed_total,
        starting_cash=bank_gross,
        max_dsr_percent=settings.max_dsr_percent,
        goals=merged,
    )
    if not sch.ok:
        raise ValueError(
            sch.error_message
            or "No se puede registrar el objetivo: plan no viable en el horizonte de 5 años."
        )

    g = SpendingPlanGoal(
        user_id=user_id,
        title=title[:200],
        goal_type=gt,
        priority=pr,
        amount_total=amt,
        target_date=target_date,
        extra_json=extra,
    )
    db.session.add(g)
    db.session.commit()
    return g


def update_generic_goal(
    user_id: int,
    goal_id: int,
    title: str,
    amount_total: float,
    priority: int,
    target_date: Optional[date],
    pay_mode: Optional[str] = None,
    installment_months: Optional[int] = None,
) -> SpendingPlanGoal:
    g = SpendingPlanGoal.query.filter_by(
        id=goal_id, user_id=user_id, goal_type="generic"
    ).first()
    if not g:
        raise ValueError("Objetivo no encontrado o no es genérico.")
    title = (title or "").strip()
    if not title:
        raise ValueError("El nombre del objetivo es obligatorio.")
    amt = float(amount_total)
    if amt <= 0:
        raise ValueError("El importe debe ser mayor que cero.")
    pr = int(priority)
    if pr < 1 or pr > 5:
        raise ValueError("La prioridad debe estar entre 1 y 5 (1 = más alta).")
    extra = _generic_extra_json(pay_mode, installment_months)
    settings = _get_or_create_settings(user_id)
    fixed_ids = get_fixed_category_ids(user_id)
    income_avg = get_avg_monthly_income(user_id, 12)
    fixed_total, _ = compute_fixed_expenses_monthly(user_id, fixed_ids)
    bank_gross = get_current_bank_cash(user_id)
    others = [
        x
        for x in SpendingPlanGoal.query.filter_by(user_id=user_id).all()
        if x.id != goal_id
    ]
    cand = build_candidate_goal(
        title=title,
        goal_type="generic",
        priority=pr,
        amount_total=amt,
        target_date=target_date,
        extra_json=extra,
        sort_id=goal_id,
    )
    merged = others + [cand]
    sch = compute_plan_schedule(
        today=date.today(),
        income_avg=income_avg,
        fixed_monthly=fixed_total,
        starting_cash=bank_gross,
        max_dsr_percent=settings.max_dsr_percent,
        goals=merged,
    )
    if not sch.ok:
        raise ValueError(
            sch.error_message
            or "No se puede guardar: plan no viable en el horizonte de 5 años."
        )
    g.title = title[:200]
    g.amount_total = amt
    g.priority = pr
    g.target_date = target_date
    g.extra_json = extra
    db.session.commit()
    return g


def update_mortgage_goal(
    user_id: int,
    goal_id: int,
    title: str,
    amount_total: float,
    priority: int,
    target_date: Optional[date],
    extra_json: str,
) -> SpendingPlanGoal:
    g = SpendingPlanGoal.query.filter_by(
        id=goal_id, user_id=user_id, goal_type="mortgage"
    ).first()
    if not g:
        raise ValueError("Objetivo hipoteca no encontrado.")
    title = (title or "").strip()
    if not title:
        raise ValueError("El nombre del objetivo es obligatorio.")
    amt = float(amount_total)
    if amt <= 0:
        raise ValueError("El importe debe ser mayor que cero.")
    pr = int(priority)
    if pr < 1 or pr > 5:
        raise ValueError("La prioridad debe estar entre 1 y 5 (1 = más alta).")
    raw = str(extra_json or "").strip()
    if not raw:
        raise ValueError("Faltan datos de la simulación.")
    if len(raw) > 32000:
        raise ValueError("Datos extra demasiado largos.")
    try:
        json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("Datos de simulación no válidos.")
    settings = _get_or_create_settings(user_id)
    fixed_ids = get_fixed_category_ids(user_id)
    income_avg = get_avg_monthly_income(user_id, 12)
    fixed_total, _ = compute_fixed_expenses_monthly(user_id, fixed_ids)
    bank_gross = get_current_bank_cash(user_id)
    others = [
        x
        for x in SpendingPlanGoal.query.filter_by(user_id=user_id).all()
        if x.id != goal_id
    ]
    cand = build_candidate_goal(
        title=title,
        goal_type="mortgage",
        priority=pr,
        amount_total=amt,
        target_date=target_date,
        extra_json=raw,
        sort_id=goal_id,
    )
    merged = others + [cand]
    sch = compute_plan_schedule(
        today=date.today(),
        income_avg=income_avg,
        fixed_monthly=fixed_total,
        starting_cash=bank_gross,
        max_dsr_percent=settings.max_dsr_percent,
        goals=merged,
    )
    if not sch.ok:
        raise ValueError(
            sch.error_message
            or "No se puede guardar: plan no viable en el horizonte de 5 años."
        )
    g.title = title[:200]
    g.amount_total = amt
    g.priority = pr
    g.target_date = target_date
    g.extra_json = raw
    db.session.commit()
    return g


def delete_goal(user_id: int, goal_id: int) -> bool:
    g = SpendingPlanGoal.query.filter_by(id=goal_id, user_id=user_id).first()
    if not g:
        return False
    db.session.delete(g)
    db.session.commit()
    return True


def update_settings(user_id: int, max_dsr_percent: float, horizon_months: int = 12) -> SpendingPlanSettings:
    s = _get_or_create_settings(user_id)
    s.max_dsr_percent = max(1.0, min(80.0, float(max_dsr_percent)))
    s.horizon_months = max(1, min(60, int(horizon_months)))
    db.session.commit()
    return s
