"""
Proyección de planificación de gastos: ingreso medio, gastos fijos por categoría, saldo mensual, DSR.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

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


GOAL_COLOR_PALETTE = [
    "#D50000",  # Tomate
    "#E67C73",  # Flamenco
    "#F4511E",  # Mandarina
    "#F6BF26",  # Plátano
    "#33B864",  # Salvia
    "#0B8043",  # Albahaca
    "#039BE5",  # Pavo real
    "#3F51B5",  # Arándano
    "#7986CB",  # Lavanda
    "#8E24AA",  # Uva
    "#616161",  # Grafito
]

UI_COLOR_JSON_KEY = "ui_color"


def _parse_ui_color_from_extra(extra_json: Optional[str]) -> Optional[str]:
    try:
        d = json.loads(extra_json or "{}")
        if not isinstance(d, dict):
            return None
        c = d.get(UI_COLOR_JSON_KEY)
        if isinstance(c, str):
            t = c.strip()
            if len(t) == 7 and t.startswith("#"):
                return t
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _merge_ui_color_into_extra(extra_json: Optional[str], color: str) -> str:
    try:
        d = json.loads(extra_json or "{}")
    except (json.JSONDecodeError, TypeError):
        d = {}
    if not isinstance(d, dict):
        d = {}
    d[UI_COLOR_JSON_KEY] = color
    return json.dumps(d, ensure_ascii=False)


def _used_ui_colors_for_user(user_id: int, exclude_goal_id: Optional[int] = None) -> set:
    goals = SpendingPlanGoal.query.filter_by(user_id=user_id).all()
    used: set = set()
    for g in goals:
        if exclude_goal_id is not None and g.id == exclude_goal_id:
            continue
        c = _parse_ui_color_from_extra(g.extra_json)
        if c:
            used.add(c.lower())
    return used


def _allocate_free_ui_color(user_id: int, exclude_goal_id: Optional[int] = None) -> str:
    used = _used_ui_colors_for_user(user_id, exclude_goal_id=exclude_goal_id)
    for p in GOAL_COLOR_PALETTE:
        if p.lower() not in used:
            return p
    n = SpendingPlanGoal.query.filter_by(user_id=user_id).count()
    return GOAL_COLOR_PALETTE[n % len(GOAL_COLOR_PALETTE)]


def _ensure_extra_has_ui_color(
    prior_extra: Optional[str],
    new_extra: str,
    user_id: int,
    *,
    exclude_goal_id: Optional[int],
) -> str:
    """Conserva ui_color del objetivo al editar; asigna hueco libre al crear o si faltaba."""
    kept = _parse_ui_color_from_extra(prior_extra)
    if kept:
        return _merge_ui_color_into_extra(new_extra, kept)
    col = _allocate_free_ui_color(user_id, exclude_goal_id=exclude_goal_id)
    return _merge_ui_color_into_extra(new_extra, col)


def ensure_goal_ui_colors_backfill(user_id: int) -> None:
    """Asigna ui_color a objetivos antiguos sin clave (una vez por carga si aplica)."""
    goals = (
        SpendingPlanGoal.query.filter_by(user_id=user_id)
        .order_by(SpendingPlanGoal.id.asc())
        .all()
    )
    need = [g for g in goals if not _parse_ui_color_from_extra(g.extra_json)]
    if not need:
        return
    used = _used_ui_colors_for_user(user_id, exclude_goal_id=None)
    changed = False
    for g in need:
        chosen: Optional[str] = None
        for p in GOAL_COLOR_PALETTE:
            if p.lower() not in used:
                chosen = p
                used.add(p.lower())
                break
        if chosen is None:
            chosen = GOAL_COLOR_PALETTE[g.id % len(GOAL_COLOR_PALETTE)]
        g.extra_json = _merge_ui_color_into_extra(g.extra_json, chosen)
        changed = True
    if changed:
        db.session.commit()


def _goal_color_map_from_db(goals_db: Sequence[Any]) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for g in goals_db:
        c = _parse_ui_color_from_extra(getattr(g, "extra_json", None))
        if c:
            out[int(g.id)] = c
    return out


def _build_goal_color_and_schedule_meta(
    sch: Any,
    month_labels: List[str],
    horizon_months: int,
    goals_db: Sequence[Any],
) -> Tuple[Dict[int, dict], List[List[dict]]]:
    """
    Meta por objetivo basada en el planificador:
    - color (persistido en extra_json; estable al cambiar prioridad)
    - mes de inicio (primer mes con pago > 0)
    - nº cuotas (nº de meses con pago > 0 dentro de la ventana)
    Y una estructura por mes para pintar puntos en la proyección.
    """
    meta: Dict[int, dict] = {}
    marks: List[List[dict]] = [[] for _ in range(max(0, int(horizon_months)))]
    if not sch or not getattr(sch, "ok", False):
        return meta, marks

    color_map = _goal_color_map_from_db(goals_db)
    details = getattr(sch, "goal_details", None) or []
    for _, gd in enumerate(details):
        gid = getattr(gd, "goal_id", None)
        if gid is None:
            continue
        color = color_map.get(int(gid)) or GOAL_COLOR_PALETTE[
            int(gid) % len(GOAL_COLOR_PALETTE)
        ]
        payments = getattr(gd, "payments_by_month", None) or []

        first_idx: Optional[int] = None
        positive_months = 0
        for mi, p in enumerate(payments):
            try:
                pv = float(p or 0)
            except (TypeError, ValueError):
                pv = 0.0
            if pv > 0.001:
                positive_months += 1
                if first_idx is None:
                    first_idx = mi
                if 0 <= mi < len(marks):
                    marks[mi].append(
                        {
                            "goal_id": int(gid),
                            "title": str(getattr(gd, "title", "") or ""),
                            "amount": round(pv, 2),
                            "color": color,
                        }
                    )

        start_label = (
            month_labels[first_idx]
            if first_idx is not None and 0 <= first_idx < len(month_labels)
            else None
        )
        meta[int(gid)] = {
            "color": color,
            "start_month_label": start_label,
            "installments_planned": positive_months if positive_months > 0 else None,
        }
    return meta, marks


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
            try:
                ex = json.loads(g.extra_json or "{}")
                row["date_fixed"] = bool(ex.get("date_fixed")) if isinstance(ex, dict) else False
            except (json.JSONDecodeError, TypeError):
                row["date_fixed"] = False
        elif g.goal_type == "mortgage":
            try:
                ex = json.loads(g.extra_json or "{}")
                if isinstance(ex, dict) and "date_fixed" in ex:
                    row["date_fixed"] = bool(ex.get("date_fixed"))
                else:
                    row["date_fixed"] = bool(g.target_date)
            except (json.JSONDecodeError, TypeError):
                row["date_fixed"] = bool(g.target_date)
        else:
            row["date_fixed"] = False
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
        # Superávit (vista usuario): ingreso − fijos − cuota (DSR) estimada
        surplus = round(income_avg - fixed_monthly - goals_dsr_monthly, 2)
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

    ensure_goal_ui_colors_backfill(user_id)
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
    avg_quota_monthly_5y = 0.0
    avg_dsr_used_pct_5y: Optional[float] = None
    dsr_free_total_5y = 0.0
    if sch.ok and len(sch.surplus_monthly) >= h:
        cash_display = float(bank_cash_gross or 0)
        for i in range(h):
            d = date.today() + relativedelta(months=i)
            label = d.strftime("%b %Y")
            g_m = (
                sch.mortgage_payments_monthly[i]
                + sch.generic_payments_monthly[i]
                + sch.initial_outlay_by_month[i]
            )
            quota_m = sch.mortgage_payments_monthly[i] + sch.generic_payments_monthly[i]
            surplus_display = round(
                income_avg - fixed_total - sch.initial_outlay_by_month[i] - quota_m, 2
            )
            cash_display = round(cash_display + surplus_display, 2)
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
                    surplus=surplus_display,
                    ending_cash=cash_display,
                    max_debt_payment=max_pay,
                    dsr_margin=margin,
                )
            )
        # Métricas 5 años (DSR): media cuotas (hipoteca + genéricos), % ocupado y € libres totales.
        used_vec: List[float] = []
        for i in range(PLAN_WINDOW_MONTHS):
            mv = sch.mortgage_payments_monthly[i] if i < len(sch.mortgage_payments_monthly) else 0.0
            gv = sch.generic_payments_monthly[i] if i < len(sch.generic_payments_monthly) else 0.0
            used_vec.append(float(mv or 0) + float(gv or 0))
        avg_quota_monthly_5y = round(sum(used_vec) / PLAN_WINDOW_MONTHS, 2) if used_vec else 0.0
        if max_pay > 0:
            avg_dsr_used_pct_5y = round((avg_quota_monthly_5y / max_pay) * 100.0, 1)
            dsr_free_total_5y = round(sum(max(0.0, max_pay - u) for u in used_vec), 2)
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
        avg_quota_monthly_5y = round(float(goals_dsr or 0), 2)
        if max_pay > 0:
            avg_dsr_used_pct_5y = round((avg_quota_monthly_5y / max_pay) * 100.0, 1)
            dsr_free_total_5y = round(max(0.0, (max_pay - avg_quota_monthly_5y)) * PLAN_WINDOW_MONTHS, 2)

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
            "date_fixed": bool(gl.get("date_fixed")),
        }
        for gl in goal_lines
        if gl["goal_type"] == "generic"
    ]

    schedule_month_labels: List[str] = []
    for i in range(PLAN_WINDOW_MONTHS):
        d = date.today() + relativedelta(months=i)
        schedule_month_labels.append(d.strftime("%b %Y"))

    balance_end_5y: Optional[float] = None
    bank_vs_end_pct: Optional[float] = None
    net_liquidity_change_5y: Optional[float] = None
    if (
        sch.ok
        and sch.cash_balance_monthly
        and len(sch.cash_balance_monthly) >= PLAN_WINDOW_MONTHS
    ):
        balance_end_5y = round(
            float(sch.cash_balance_monthly[PLAN_WINDOW_MONTHS - 1]), 2
        )
        net_liquidity_change_5y = round(balance_end_5y - float(bank_cash_gross or 0), 2)
        if bank_cash_gross and float(bank_cash_gross) > 1e-6:
            bank_vs_end_pct = round(
                (balance_end_5y / float(bank_cash_gross) - 1.0) * 100.0, 1
            )

    goal_meta, month_goal_marks = _build_goal_color_and_schedule_meta(
        sch, schedule_month_labels, settings.horizon_months, goals_db
    )
    for row in goal_lines:
        gid = row.get("id")
        try:
            gid_int = int(gid) if gid is not None else None
        except (TypeError, ValueError):
            gid_int = None
        m = goal_meta.get(gid_int or -1, {})
        row["color"] = m.get("color")
        row["start_month_label"] = m.get("start_month_label")
        row["installments_planned"] = m.get("installments_planned")

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
        "dsr_cap_monthly": max_pay,
        "avg_quota_monthly_5y": avg_quota_monthly_5y,
        "avg_dsr_used_pct_5y": avg_dsr_used_pct_5y,
        "dsr_free_total_5y": dsr_free_total_5y,
        "category_options": cat_options,
        "plan_schedule": sch,
        "plan_window_months": PLAN_WINDOW_MONTHS,
        "schedule_month_labels": schedule_month_labels,
        "month_goal_marks": month_goal_marks,
        "balance_end_5y": balance_end_5y,
        "bank_vs_end_pct": bank_vs_end_pct,
        "net_liquidity_change_5y": net_liquidity_change_5y,
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
    return json.dumps(
        {"pay_mode": pm, "installment_months": im, "date_fixed": False},
        ensure_ascii=False,
    )


def _set_mortgage_date_fixed(extra_json: str, purchase_date_user_fixed: bool) -> str:
    """Marca si la fecha de compra la eligió el usuario (True) o el algoritmo (False)."""
    try:
        d = json.loads(extra_json or "{}")
    except (json.JSONDecodeError, TypeError):
        d = {}
    if not isinstance(d, dict):
        d = {}
    d["date_fixed"] = bool(purchase_date_user_fixed)
    return json.dumps(d, ensure_ascii=False)


def _set_generic_date_fixed(extra_json: str, date_fixed: bool) -> str:
    try:
        d = json.loads(extra_json or "{}")
    except (json.JSONDecodeError, TypeError):
        d = {}
    if not isinstance(d, dict):
        d = {}
    d["date_fixed"] = bool(date_fixed)
    # Mantener claves conocidas si existían
    if "pay_mode" not in d:
        d["pay_mode"] = "auto"
    if "installment_months" not in d:
        d["installment_months"] = None
    return json.dumps(d, ensure_ascii=False)


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
    date_fixed: bool = False,
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
        extra = _set_generic_date_fixed(
            _generic_extra_json(pay_mode, installment_months), date_fixed
        )
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

    mortgage_date_user_fixed = bool(gt == "mortgage" and target_date is not None)

    # Hipoteca sin fecha: buscar primera fecha viable automáticamente.
    if gt == "mortgage" and target_date is None and extra:
        auto_td = _first_viable_mortgage_date(
            user_id, extra, exclude_goal_id=None, priority=pr
        )
        if auto_td is None:
            raise ValueError(
                "No hay una fecha viable en los próximos 5 años para encajar la entrada hipotecaria "
                "con el efectivo disponible y el cupo DSR."
            )
        target_date = auto_td
        # Persistir también en extra_json como loan_payment_start para coherencia
        try:
            d = json.loads(extra)
            if isinstance(d, dict):
                d["loan_payment_start"] = auto_td.isoformat()[:10]
                extra = json.dumps(d, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass

    if gt == "mortgage" and extra:
        extra = _set_mortgage_date_fixed(extra, mortgage_date_user_fixed)

    if extra:
        extra = _ensure_extra_has_ui_color(
            None, extra, user_id, exclude_goal_id=None
        )

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
    date_fixed: bool = False,
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
    extra = _set_generic_date_fixed(_generic_extra_json(pay_mode, installment_months), date_fixed)
    extra = _ensure_extra_has_ui_color(
        g.extra_json, extra, user_id, exclude_goal_id=goal_id
    )
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
    purchase_date_user_fixed = target_date is not None
    # Si no hay fecha: buscar fecha viable automáticamente
    if target_date is None:
        auto_td = _first_viable_mortgage_date(
            user_id, raw, exclude_goal_id=goal_id, priority=pr
        )
        if auto_td is None:
            raise ValueError(
                "No hay una fecha viable en los próximos 5 años para encajar la entrada hipotecaria "
                "con el efectivo disponible y el cupo DSR."
            )
        target_date = auto_td
        purchase_date_user_fixed = False
        try:
            d = json.loads(raw)
            if isinstance(d, dict):
                d["loan_payment_start"] = auto_td.isoformat()[:10]
                raw = json.dumps(d, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass

    raw = _set_mortgage_date_fixed(raw, purchase_date_user_fixed)
    raw = _ensure_extra_has_ui_color(
        g.extra_json, raw, user_id, exclude_goal_id=goal_id
    )

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


def _first_viable_mortgage_date(
    user_id: int,
    extra_json: str,
    exclude_goal_id: Optional[int],
    priority: int = 3,
) -> Optional[date]:
    """
    Encuentra la primera fecha (mes) en la ventana de 5 años en la que la hipoteca
    encaja (entrada con liquidez + DSR). Devuelve None si no existe.
    """
    today = date.today()
    settings = _get_or_create_settings(user_id)
    fixed_ids = get_fixed_category_ids(user_id)
    income_avg = get_avg_monthly_income(user_id, 12)
    fixed_total, _ = compute_fixed_expenses_monthly(user_id, fixed_ids)
    bank_gross = get_current_bank_cash(user_id)
    goals = SpendingPlanGoal.query.filter_by(user_id=user_id).all()
    others = [g for g in goals if exclude_goal_id is None or g.id != exclude_goal_id]
    pr = max(1, min(5, int(priority)))
    for m in range(PLAN_WINDOW_MONTHS):
        td = today + relativedelta(months=m)
        cand = build_candidate_goal(
            title="(auto)",
            goal_type="mortgage",
            priority=pr,
            amount_total=1.0,
            target_date=td,
            extra_json=extra_json,
            sort_id=10**9,
        )
        sch = compute_plan_schedule(
            today=today,
            income_avg=income_avg,
            fixed_monthly=fixed_total,
            starting_cash=bank_gross,
            max_dsr_percent=settings.max_dsr_percent,
            goals=others + [cand],
        )
        if sch.ok:
            return td
    return None


def suggest_adjustments_for_generic(
    user_id: int,
    goal_id: Optional[int],
    title: str,
    amount_total: float,
    priority: int,
    target_date: Optional[date],
    raw_installment_months: Optional[str],
    date_fixed: bool,
) -> List[dict]:
    """
    Sugiere cambios aplicables para que el plan sea viable sin perder el contexto del usuario.
    Devuelve una lista de sugerencias {type, field, value, label}.
    """
    suggestions: List[dict] = []
    today = date.today()
    settings = _get_or_create_settings(user_id)
    fixed_ids = get_fixed_category_ids(user_id)
    income_avg = get_avg_monthly_income(user_id, 12)
    fixed_total, _ = compute_fixed_expenses_monthly(user_id, fixed_ids)
    bank_gross = get_current_bank_cash(user_id)
    all_goals = SpendingPlanGoal.query.filter_by(user_id=user_id).all()
    others = [g for g in all_goals if goal_id is None or g.id != goal_id]

    # Parse current pay options
    pay_mode = "auto"
    inst: Optional[int] = None
    try:
        pay_mode, inst = pay_options_from_installment_field(raw_installment_months)
    except ValueError:
        pay_mode, inst = "auto", None

    sort_id = goal_id if goal_id is not None else 10**9

    def try_schedule(
        *,
        td: Optional[date],
        pm: str,
        im: Optional[int],
        df: bool,
    ) -> Optional[PlanScheduleResult]:
        extra = _set_generic_date_fixed(_generic_extra_json(pm, im), df)
        cand = build_candidate_goal(
            title=title,
            goal_type="generic",
            priority=int(priority),
            amount_total=float(amount_total or 0),
            target_date=td,
            extra_json=extra,
            sort_id=sort_id,
        )
        merged = others + [cand]
        sch = compute_plan_schedule(
            today=today,
            income_avg=income_avg,
            fixed_monthly=fixed_total,
            starting_cash=bank_gross,
            max_dsr_percent=settings.max_dsr_percent,
            goals=merged,
        )
        return sch if sch.ok else None

    def first_payment_date_str(sch: PlanScheduleResult) -> Optional[str]:
        for gd in getattr(sch, "goal_details", []) or []:
            if getattr(gd, "goal_id", None) == sort_id:
                for i, p in enumerate(getattr(gd, "payments_by_month", []) or []):
                    try:
                        pv = float(p or 0)
                    except (TypeError, ValueError):
                        pv = 0.0
                    if pv > 0.001:
                        return (today + relativedelta(months=i)).isoformat()
        return None

    # 1) Sugerencias de fecha
    if target_date is not None:
        sch_ge = try_schedule(td=target_date, pm=pay_mode, im=inst, df=False)
        if sch_ge:
            d1 = first_payment_date_str(sch_ge)
            if d1:
                suggestions.append(
                    {
                        "type": "set_field",
                        "field": "target_date",
                        "value": d1,
                        "label": f"Fecha viable (≥ la indicada): {d1}",
                    }
                )
        sch_any = try_schedule(td=None, pm=pay_mode, im=inst, df=False)
        if sch_any:
            d2 = first_payment_date_str(sch_any)
            if d2:
                suggestions.append(
                    {
                        "type": "set_field",
                        "field": "target_date",
                        "value": d2,
                        "label": f"Primera fecha viable (auto): {d2}",
                    }
                )

    # 2) Sugerencias de cuotas
    if pay_mode == "installments":
        for k in range(2, 61):
            sch_k = try_schedule(td=target_date, pm="installments", im=k, df=date_fixed)
            if sch_k:
                suggestions.append(
                    {
                        "type": "set_field",
                        "field": "installment_months",
                        "value": str(k),
                        "label": f"Cuotas sugeridas: {k} meses",
                    }
                )
                break
        sch_auto = try_schedule(td=target_date, pm="auto", im=None, df=date_fixed)
        if sch_auto:
            suggestions.append(
                {
                    "type": "set_field",
                    "field": "installment_months",
                    "value": "",
                    "label": "Dejar cuotas en automático",
                }
            )

    return suggestions


def suggest_adjustments_for_mortgage(
    user_id: int,
    goal_id: Optional[int],
    title: str,
    amount_total: float,
    target_date: Optional[date],
    extra_json: str,
    priority: int = 3,
) -> List[dict]:
    """
    Sugiere una fecha alternativa para la hipoteca cuando la entrada no encaja por liquidez.
    Devuelve sugerencias {type, field, value, label}.
    """
    suggestions: List[dict] = []
    if target_date is None:
        return suggestions

    today = date.today()
    settings = _get_or_create_settings(user_id)
    fixed_ids = get_fixed_category_ids(user_id)
    income_avg = get_avg_monthly_income(user_id, 12)
    fixed_total, _ = compute_fixed_expenses_monthly(user_id, fixed_ids)
    bank_gross = get_current_bank_cash(user_id)

    all_goals = SpendingPlanGoal.query.filter_by(user_id=user_id).all()
    others = [g for g in all_goals if goal_id is None or g.id != goal_id]
    sort_id = goal_id if goal_id is not None else 10**9
    pr = max(1, min(5, int(priority)))

    def try_date(td: date) -> bool:
        cand = build_candidate_goal(
            title=title,
            goal_type="mortgage",
            priority=pr,
            amount_total=float(amount_total or 0),
            target_date=td,
            extra_json=extra_json,
            sort_id=sort_id,
        )
        sch = compute_plan_schedule(
            today=today,
            income_avg=income_avg,
            fixed_monthly=fixed_total,
            starting_cash=bank_gross,
            max_dsr_percent=settings.max_dsr_percent,
            goals=others + [cand],
        )
        return bool(sch.ok)

    # Buscar primer mes viable >= fecha elegida (máx ventana 5 años)
    start_m = (target_date.year - today.year) * 12 + (target_date.month - today.month)
    start_m = max(0, min(PLAN_WINDOW_MONTHS - 1, start_m))
    for m in range(start_m, PLAN_WINDOW_MONTHS):
        td = today + relativedelta(months=m)
        if try_date(td):
            v = td.isoformat()
            suggestions.append(
                {
                    "type": "set_field",
                    "field": "target_date",
                    "value": v,
                    "label": f"Fecha recomendada: {v}",
                }
            )
            break
    return suggestions


def delete_goal(user_id: int, goal_id: int) -> bool:
    g = SpendingPlanGoal.query.filter_by(id=goal_id, user_id=user_id).first()
    if not g:
        return False
    db.session.delete(g)
    db.session.commit()
    return True


def _assert_plan_viable_with_dsr(user_id: int, max_dsr_percent: float) -> None:
    """Comprueba que el plan actual encaja con el DSR propuesto; si no, lanza ValueError."""
    max_dsr_percent = max(1.0, min(80.0, float(max_dsr_percent)))
    fixed_ids = get_fixed_category_ids(user_id)
    income_avg = get_avg_monthly_income(user_id, 12)
    fixed_total, _ = compute_fixed_expenses_monthly(user_id, fixed_ids)
    bank_gross = get_current_bank_cash(user_id)
    goals = SpendingPlanGoal.query.filter_by(user_id=user_id).all()
    sch = compute_plan_schedule(
        today=date.today(),
        income_avg=income_avg,
        fixed_monthly=fixed_total,
        starting_cash=bank_gross,
        max_dsr_percent=max_dsr_percent,
        goals=goals,
    )
    if not sch.ok:
        raise ValueError(
            sch.error_message
            or "Con este % DSR el plan actual no es viable. Sube el límite o ajusta objetivos."
        )


def update_settings(user_id: int, max_dsr_percent: float, horizon_months: int = 12) -> SpendingPlanSettings:
    max_dsr = max(1.0, min(80.0, float(max_dsr_percent)))
    horizon = max(1, min(60, int(horizon_months)))
    _assert_plan_viable_with_dsr(user_id, max_dsr)
    s = _get_or_create_settings(user_id)
    s.max_dsr_percent = max_dsr
    s.horizon_months = horizon
    db.session.commit()
    return s
