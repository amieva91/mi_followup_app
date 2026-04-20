"""
Planificador multi-objetivo (ventana 5 años): prioridades, DSR, saldo no negativo,
reparto en pago único o cuotas para objetivos genéricos; hipotecas con entrada y
primera cuota parametrizables.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from dateutil.relativedelta import relativedelta

PLAN_WINDOW_MONTHS = 60

_SPANISH_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def _plan_slot_calendar_label(today: date, month_index: int) -> str:
    """Etiqueta mes/año del slot `month_index` (0 = mes calendario de `today`)."""
    d = today + relativedelta(months=int(month_index))
    return f"{_SPANISH_MONTHS[d.month - 1]} {d.year}"


def _month_offset_from_today(today: date, d: Optional[date], cap: int) -> int:
    if d is None:
        return cap
    mi = (d.year - today.year) * 12 + (d.month - today.month)
    return max(0, min(cap, mi))


def _parse_extra_dict(raw: Optional[str]) -> Dict[str, Any]:
    if not raw or not str(raw).strip():
        return {}
    try:
        d = json.loads(raw)
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def parse_generic_pay_options(extra_json: Optional[str]) -> Tuple[str, Optional[int]]:
    d = _parse_extra_dict(extra_json)
    raw = d.get("pay_mode")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        mode = "auto"
    else:
        mode = str(raw).strip().lower()
        if mode not in ("lump", "installments", "auto"):
            mode = "auto"
    im = d.get("installment_months")
    try:
        im_int = int(im) if im is not None else None
        if im_int is not None and im_int < 1:
            im_int = None
    except (TypeError, ValueError):
        im_int = None
    return mode, im_int


def _mortgage_monthly(extra: Dict[str, Any]) -> float:
    try:
        return max(0.0, float(extra.get("monthly_payment") or 0))
    except (TypeError, ValueError):
        return 0.0


def _mortgage_initial(extra: Dict[str, Any]) -> float:
    try:
        return max(0.0, float(extra.get("initial_outlay") or 0))
    except (TypeError, ValueError):
        return 0.0


def _loan_years(extra: Dict[str, Any]) -> int:
    try:
        y = int(extra.get("years") or 30)
        return max(1, min(40, y))
    except (TypeError, ValueError):
        return 30


@dataclass
class GoalScheduleDetail:
    goal_id: Optional[int]
    title: str
    goal_type: str
    priority: int
    amount_total: float
    pay_mode: str
    """lump | installments | auto-resolved"""
    payments_by_month: List[float] = field(default_factory=list)
    adjusted_message: Optional[str] = None


@dataclass
class PlanScheduleResult:
    ok: bool
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    generic_payments_monthly: List[float] = field(default_factory=list)
    mortgage_payments_monthly: List[float] = field(default_factory=list)
    initial_outlay_by_month: List[float] = field(default_factory=list)
    goal_details: List[GoalScheduleDetail] = field(default_factory=list)
    surplus_monthly: List[float] = field(default_factory=list)
    cash_balance_monthly: List[float] = field(default_factory=list)
    dsr_ok_each_month: List[bool] = field(default_factory=list)


def _zero(W: int) -> List[float]:
    return [0.0] * W


def _add_vec(a: Sequence[float], b: Sequence[float]) -> List[float]:
    return [float(a[i]) + float(b[i]) for i in range(len(a))]


def _simulate_cash_initial_only(
    cash0: float,
    income: float,
    fixed: float,
    initial: Sequence[float],
) -> bool:
    """
    Saldo acumulado solo se ve afectado por ingresos, gastos fijos y entrada hipotecaria.
    Las cuotas de préstamo y los objetivos genéricos no descuentan del efectivo (van por cupo DSR).
    """
    W = len(initial)
    cash = cash0
    for m in range(W):
        cash += income - fixed
        cash -= initial[m]
        if cash < -1e-4:
            return False
    return True


def _dsr_within_cap(
    income: float,
    max_dsr_pct: float,
    mortgage: Sequence[float],
    generic: Sequence[float],
) -> bool:
    cap = income * (max_dsr_pct / 100.0) if income > 0 else 0.0
    W = len(mortgage)
    for m in range(W):
        if mortgage[m] + generic[m] > cap + 1e-4:
            return False
    return True


def _dsr_violation(
    income: float, mortgage: Sequence[float], max_dsr_pct: float
) -> Optional[int]:
    if income <= 0:
        return None
    cap = income * (max_dsr_pct / 100.0)
    for m, mp in enumerate(mortgage):
        if mp > cap + 1e-4:
            return m
    return None


def _goal_priority_value(g: Any) -> int:
    pr = getattr(g, "priority", None)
    try:
        return int(pr) if pr is not None else 3
    except (TypeError, ValueError):
        return 3


def _goal_schedule_sort_key(g: Any) -> Tuple[int, int]:
    prio = _goal_priority_value(g)
    gid = getattr(g, "id", None)
    try:
        iid = int(gid) if gid is not None else 0
    except (TypeError, ValueError):
        iid = 0
    return (prio, iid)


def _accumulate_mortgage_initial_and_notes(
    today: date, goals: Sequence[Any], W: int
) -> Tuple[List[float], List[str]]:
    """Suma entradas hipotecarias (todos los objetivos hipoteca) para simulación de efectivo."""
    initial = _zero(W)
    notes: List[str] = []
    for g in goals:
        if getattr(g, "goal_type", "") != "mortgage":
            continue
        _, ini, n = _mortgage_vectors_for_goal(today, g, W)
        for i in range(W):
            initial[i] += ini[i]
        if n:
            notes.append(n)
    return initial, notes


def _first_combined_dsr_conflict_index(
    income: float,
    max_dsr_pct: float,
    mortgage: Sequence[float],
    generic: Sequence[float],
) -> Optional[int]:
    if income <= 0:
        return None
    cap = income * (max_dsr_pct / 100.0)
    W = len(mortgage)
    for m in range(W):
        if mortgage[m] + generic[m] > cap + 1e-4:
            return m
    return None


def _mortgage_vectors_for_goal(
    today: date, g: Any, W: int
) -> Tuple[List[float], List[float], Optional[str]]:
    """
    Cuotas hipoteca + entrada en el mes de compra para un único objetivo hipoteca.
    """
    mortgage_pay = _zero(W)
    initial_pay = _zero(W)
    note: Optional[str] = None
    extra = _parse_extra_dict(getattr(g, "extra_json", None))
    mp = _mortgage_monthly(extra)
    ini = _mortgage_initial(extra)
    tgt = getattr(g, "target_date", None)
    if tgt is None:
        purchase_m = 0
    else:
        purchase_m = _month_offset_from_today(today, tgt, W - 1)

    raw_start = extra.get("loan_payment_start")
    loan_start_m = purchase_m
    if raw_start:
        try:
            if isinstance(raw_start, str) and raw_start.strip():
                from datetime import datetime as dt_mod

                d = dt_mod.strptime(raw_start.strip()[:10], "%Y-%m-%d").date()
                loan_start_m = _month_offset_from_today(today, d, W - 1)
        except (ValueError, TypeError):
            loan_start_m = purchase_m
    loan_start_m = max(purchase_m, loan_start_m)

    initial_pay[purchase_m] += ini
    loan_months_cap = min(W - loan_start_m, _loan_years(extra) * 12)
    for k in range(loan_months_cap):
        if loan_start_m + k < W:
            mortgage_pay[loan_start_m + k] += mp

    if ini > 0 and purchase_m > 0:
        note = (
            f"«{g.title}»: entrada {ini:.0f} € en mes {purchase_m + 1} (desde hoy)."
        )
    return mortgage_pay, initial_pay, note


def build_mortgage_arrays(
    today: date,
    goals: Sequence[Any],
    W: int = PLAN_WINDOW_MONTHS,
) -> Tuple[List[float], List[float], List[str]]:
    """
    Suma aportaciones hipoteca: initial_outlay en mes de compra (target_date),
    cuota desde loan_payment_start en extra_json (misma fecha que compra si coinciden).
    Sin target_date en el objetivo: mes 0 (cuanto antes), no fin de ventana.
    """
    mortgage_pay = _zero(W)
    initial_pay = _zero(W)
    notes: List[str] = []

    for g in goals:
        if getattr(g, "goal_type", "") != "mortgage":
            continue
        mp, ini, n = _mortgage_vectors_for_goal(today, g, W)
        for i in range(W):
            mortgage_pay[i] += mp[i]
            initial_pay[i] += ini[i]
        if n:
            notes.append(n)
    return mortgage_pay, initial_pay, notes


def _try_generic_allocation(
    amount: float,
    start_m: int,
    pay_mode: str,
    user_installments: Optional[int],
    date_fixed: bool,
    W: int,
    base_generic: List[float],
    cash0: float,
    income: float,
    fixed: float,
    mortgage: Sequence[float],
    initial: Sequence[float],
    max_dsr_pct: float,
) -> Optional[Tuple[List[float], Optional[str]]]:
    """Devuelve incremento a generic por mes o None si no cabe (DSR + efectivo solo entrada)."""

    def check(extra: List[float]) -> bool:
        g = _add_vec(base_generic, extra)
        if not _dsr_within_cap(income, max_dsr_pct, mortgage, g):
            return False
        return _simulate_cash_initial_only(cash0, income, fixed, initial)

    if amount <= 1e-6:
        z = _zero(W)
        return z, None

    start_m = max(0, min(W - 1, start_m))

    if pay_mode == "auto":
        # Con fecha indicada: nunca empezar antes de start_m. Sin fecha (start_m=0): libre.
        if date_fixed:
            inc = _zero(W)
            inc[start_m] = amount
            if check(inc):
                return inc, f"Pago único automático en el mes fijado ({start_m + 1})."
        for m in range(start_m, W):
            inc = _zero(W)
            inc[m] = amount
            if check(inc):
                return (
                    inc,
                    f"Pago único automático en mes {m + 1} (primera fecha viable).",
                )
        for k in range(1, W + 1):
            if date_fixed:
                start = start_m
                end = start + k - 1
                if end >= W:
                    continue
                pay = amount / k
                inc = _zero(W)
                for j in range(k):
                    inc[start + j] = pay
                if check(inc):
                    return (
                        inc,
                        f"Automático: {k} cuotas iguales desde mes {start + 1}.",
                    )
                continue
            for start in range(start_m, W - k + 1):
                pay = amount / k
                inc = _zero(W)
                for j in range(k):
                    inc[start + j] = pay
                if check(inc):
                    return (
                        inc,
                        f"Automático: {k} cuotas iguales desde mes {start + 1}.",
                    )
        return None

    if pay_mode == "lump":
        if date_fixed:
            inc = _zero(W)
            inc[start_m] = amount
            if check(inc):
                return inc, None
            return None
        for m in range(start_m, W):
            inc = _zero(W)
            inc[m] = amount
            if check(inc):
                return (
                    inc,
                    None,
                )
        return None

    # installments
    ks: List[int] = []
    if user_installments is not None:
        ks = [max(1, min(W, user_installments))]
    else:
        ks = list(range(1, W + 1))

    for k in ks:
        # Con cuotas explícitas: mantener k y permitir mover el inicio >= start_m.
        if user_installments is not None and not date_fixed:
            for start in range(start_m, W - k + 1):
                pay = amount / k
                inc = _zero(W)
                for j in range(k):
                    inc[start + j] = pay
                if check(inc):
                    return inc, None
        else:
            start = start_m
            end = start + k - 1
            if end >= W:
                continue
            pay = amount / k
            inc = _zero(W)
            for j in range(k):
                inc[start + j] = pay
            if check(inc):
                return inc, None

    if not date_fixed:
        # Solo si el usuario NO especificó cuotas: buscar k y start.
        if user_installments is None:
            for k in range(1, W + 1):
                for start in range(start_m, W - k + 1):
                    pay = amount / k
                    inc = _zero(W)
                    for j in range(k):
                        inc[start + j] = pay
                    if check(inc):
                        return (
                            inc,
                            f"Cuotas repartidas en {k} meses (desde mes {start + 1}) dentro del cupo DSR.",
                        )
    return None


def compute_plan_schedule(
    *,
    today: date,
    income_avg: float,
    fixed_monthly: float,
    starting_cash: float,
    max_dsr_percent: float,
    goals: Sequence[Any],
) -> PlanScheduleResult:
    W = PLAN_WINDOW_MONTHS
    out = PlanScheduleResult(ok=True, generic_payments_monthly=_zero(W))

    # Entradas hipotecarias totales (todas las hipotecas): el efectivo debe contemplarlas siempre.
    full_initial, mnotes = _accumulate_mortgage_initial_and_notes(today, goals, W)
    out.warnings.extend(mnotes)

    schedulable = [
        g
        for g in goals
        if getattr(g, "goal_type", "generic") in ("generic", "mortgage")
    ]
    schedulable.sort(key=_goal_schedule_sort_key)

    combined_mortgage = _zero(W)
    base = _zero(W)
    mortgage_details: List[GoalScheduleDetail] = []
    details: List[GoalScheduleDetail] = []

    for g in schedulable:
        gt = getattr(g, "goal_type", "generic")
        if gt == "mortgage":
            mp, ini, _ = _mortgage_vectors_for_goal(today, g, W)
            combined_mortgage = _add_vec(combined_mortgage, mp)
            conflict = _first_combined_dsr_conflict_index(
                income_avg, max_dsr_percent, combined_mortgage, base
            )
            if conflict is not None:
                title_g = str(getattr(g, "title", "") or "")
                viol_m_only = _dsr_violation(
                    income_avg, combined_mortgage, max_dsr_percent
                )
                if viol_m_only is not None:
                    when_m = _plan_slot_calendar_label(today, viol_m_only)
                    return PlanScheduleResult(
                        ok=False,
                        error_message=(
                            "La suma de cuotas hipoteca supera el límite DSR en uno o más meses "
                            f"(primer conflicto en {when_m}). Reduce cuotas o sube ingreso/DSR."
                        ),
                        mortgage_payments_monthly=combined_mortgage,
                        initial_outlay_by_month=full_initial,
                    )
                when = _plan_slot_calendar_label(today, conflict)
                return PlanScheduleResult(
                    ok=False,
                    error_message=(
                        f"No cabe la hipoteca «{title_g}» en el cupo DSR junto con los objetivos "
                        f"ya colocados hasta esta prioridad (primer conflicto en {when}). "
                        "Ajusta prioridades, fecha o importe, o sube el % DSR."
                    ),
                    mortgage_payments_monthly=combined_mortgage,
                    initial_outlay_by_month=full_initial,
                )
            amt = float(getattr(g, "amount_total", 0) or 0)
            prio = _goal_priority_value(g)
            combined_row = [round(mp[i] + ini[i], 2) for i in range(W)]
            mortgage_details.append(
                GoalScheduleDetail(
                    goal_id=getattr(g, "id", None),
                    title=str(getattr(g, "title", "") or ""),
                    goal_type="mortgage",
                    priority=prio,
                    amount_total=amt,
                    pay_mode="mortgage",
                    payments_by_month=combined_row,
                    adjusted_message=None,
                )
            )
        else:
            extra = _parse_extra_dict(getattr(g, "extra_json", None))
            mode, inst = parse_generic_pay_options(getattr(g, "extra_json", None))
            amt = float(getattr(g, "amount_total", 0) or 0)
            tgt = getattr(g, "target_date", None)
            start_m = (
                _month_offset_from_today(today, tgt, W - 1) if tgt is not None else 0
            )
            date_fixed = bool(extra.get("date_fixed")) if isinstance(extra, dict) else False

            res = _try_generic_allocation(
                amt,
                start_m,
                mode,
                inst,
                date_fixed,
                W,
                base,
                starting_cash,
                income_avg,
                fixed_monthly,
                combined_mortgage,
                full_initial,
                max_dsr_percent,
            )
            if res is None:
                return PlanScheduleResult(
                    ok=False,
                    error_message=(
                        f"No se puede encajar el objetivo «{g.title}» ({amt:.2f} €) en el cupo DSR "
                        f"o la entrada hipotecaria agota el efectivo disponible. "
                        "Reduce importe, sube el % DSR o ajusta prioridades."
                    ),
                    mortgage_payments_monthly=combined_mortgage,
                    initial_outlay_by_month=full_initial,
                )
            inc_vec, adj = res[0], res[1]
            base = _add_vec(base, inc_vec)
            details.append(
                GoalScheduleDetail(
                    goal_id=getattr(g, "id", None),
                    title=g.title,
                    goal_type="generic",
                    priority=g.priority,
                    amount_total=amt,
                    pay_mode=mode,
                    payments_by_month=list(inc_vec),
                    adjusted_message=adj,
                )
            )

    out.mortgage_payments_monthly = combined_mortgage
    out.initial_outlay_by_month = full_initial
    out.generic_payments_monthly = base
    out.goal_details = sorted(
        mortgage_details + details,
        key=lambda d: (d.priority, d.goal_id or 0),
    )

    cap = income_avg * (max_dsr_percent / 100.0) if income_avg > 0 else 0.0
    dsr_ok: List[bool] = []
    for m in range(W):
        ok = income_avg <= 0 or (combined_mortgage[m] + base[m] <= cap + 1e-4)
        dsr_ok.append(ok)
    out.dsr_ok_each_month = dsr_ok

    surplus: List[float] = []
    cash_tr: List[float] = []
    cash = starting_cash
    for m in range(W):
        s = income_avg - fixed_monthly - full_initial[m]
        surplus.append(round(s, 2))
        cash += s
        cash_tr.append(round(cash, 2))
        if cash < -1e-4:
            out.ok = False
            out.error_message = (
                "El efectivo disponible no cubre la entrada hipotecaria prevista; revisa datos o prioridades."
            )
    out.surplus_monthly = surplus
    out.cash_balance_monthly = cash_tr

    for d in details:
        if d.adjusted_message:
            out.warnings.append(f"{d.title}: {d.adjusted_message}")

    low = min(cash_tr) if cash_tr else 0.0
    if low < 1e-2 and low >= 0:
        out.warnings.append("El saldo proyectado llega casi a cero en algún mes; margen muy ajustado.")

    return out


def validate_goals_for_user(
    *,
    income_avg: float,
    fixed_monthly: float,
    starting_cash: float,
    max_dsr_percent: float,
    goals: Sequence[Any],
    today: Optional[date] = None,
) -> PlanScheduleResult:
    """Valida lista de objetivos (p. ej. antes de guardar uno nuevo)."""
    t = today or date.today()
    return compute_plan_schedule(
        today=t,
        income_avg=income_avg,
        fixed_monthly=fixed_monthly,
        starting_cash=starting_cash,
        max_dsr_percent=max_dsr_percent,
        goals=goals,
    )


CANDIDATE_SORT_ID = 10**9


def build_candidate_goal(
    *,
    title: str,
    goal_type: str,
    priority: int,
    amount_total: float,
    target_date: Optional[date],
    extra_json: Optional[str],
    sort_id: Optional[int] = None,
) -> Any:
    """Objeto anónimo compatible con compute_plan_schedule (id alto = último en misma prioridad salvo sort_id)."""
    return _CandidateGoal(
        id=sort_id if sort_id is not None else CANDIDATE_SORT_ID,
        title=title,
        goal_type=goal_type,
        priority=priority,
        amount_total=amount_total,
        target_date=target_date,
        extra_json=extra_json,
    )


@dataclass
class _CandidateGoal:
    id: int
    title: str
    goal_type: str
    priority: int
    amount_total: float
    target_date: Optional[date]
    extra_json: Optional[str]
