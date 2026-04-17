"""
Proyección de planificación de gastos: ingreso medio, gastos fijos por categoría, saldo mensual, DSR.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List

from dateutil.relativedelta import relativedelta

from app import db
from app.models import ExpenseCategory
from app.models.spending_plan import SpendingPlanFixedCategory, SpendingPlanSettings
from app.services.bank_service import BankService
from app.services.income_expense_aggregator import (
    get_expense_category_summary_with_adjustment,
    get_income_monthly_totals_with_adjustment,
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
    """Media mensual de ingresos (últimos N meses), con ajustes y broker."""
    rows = get_income_monthly_totals_with_adjustment(user_id, months=months)
    if not rows:
        return 0.0
    return round(sum(float(r["total"]) for r in rows) / len(rows), 2)


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


@dataclass
class MonthProjection:
    month_label: str
    month_index: int
    income: float
    fixed_expenses: float
    surplus: float
    ending_cash: float
    max_debt_payment: float
    dsr_margin: float


def build_monthly_projection(
    income_avg: float,
    fixed_monthly: float,
    starting_cash: float,
    max_dsr_percent: float,
    horizon_months: int = 12,
) -> List[MonthProjection]:
    """
    Proyección mes a mes: saldo acumulado y margen bajo DSR (sin cuotas hipotecarias aún).
    max_debt_payment = income * (max_dsr/100); dsr_margin = eso menos cuotas futuras (0 por ahora).
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
        # Sin cuotas de objetivos aún: todo el cupo disponible
        margin = round(max_pay - 0.0, 2)
        out.append(
            MonthProjection(
                month_label=label,
                month_index=i + 1,
                income=income_avg,
                fixed_expenses=fixed_monthly,
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
    fixed_ids = get_fixed_category_ids(user_id)
    income_avg = get_avg_monthly_income(user_id, 12)
    fixed_total, fixed_lines = compute_fixed_expenses_monthly(user_id, fixed_ids)
    cash0 = get_current_bank_cash(user_id)
    months = build_monthly_projection(
        income_avg,
        fixed_total,
        cash0,
        settings.max_dsr_percent,
        settings.horizon_months,
    )

    categories = ExpenseCategory.query.filter_by(user_id=user_id).order_by(
        ExpenseCategory.name
    ).all()
    cat_options = [{"id": c.id, "label": c.full_name} for c in categories]

    return {
        "settings": settings,
        "fixed_category_ids": fixed_ids,
        "income_avg": income_avg,
        "fixed_total": fixed_total,
        "fixed_lines": fixed_lines,
        "starting_cash": cash0,
        "months": months,
        "category_options": cat_options,
    }


def update_settings(user_id: int, max_dsr_percent: float, horizon_months: int = 12) -> SpendingPlanSettings:
    s = _get_or_create_settings(user_id)
    s.max_dsr_percent = max(1.0, min(80.0, float(max_dsr_percent)))
    s.horizon_months = max(1, min(36, int(horizon_months)))
    db.session.commit()
    return s
