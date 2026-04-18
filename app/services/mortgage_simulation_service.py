"""
Simulación compra vivienda: gastos de compra por defecto, ITP, límite préstamo 80% valor tasación,
cuota francesa a tipo fijo. Referencia Euribor (opcional, no usada en la cuota).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

CHART_API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FollowUp/1.0; mortgage-sim)"
}
CHART_API_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

# Valores por defecto (editables en UI)
DEFAULT_NOTARY = 1200.0
DEFAULT_REGISTRY = 450.0
DEFAULT_GESTORIA = 250.0
DEFAULT_TASACION = 290.0

LOAN_CAP_ON_APPRAISAL = 0.80
EURIBOR_YAHOO_TICKER = "EBH28.CME"


@dataclass
class MortgageSimulationResult:
    purchase_price: float
    first_home: bool
    itp_percent: float
    itp_amount: float
    notary: float
    registry: float
    gestoria: float
    tasacion_fee: float
    other_expenses_sum: float
    total_purchase_side: float
    total_cost: float
    savings_cash: float
    effective_entry_total: float
    loan_amount: float
    valor_tasacion_inmueble: float
    ltv_percent: float
    max_loan_by_policy: float
    min_savings_cash: float
    annual_interest_percent: float
    years: int
    monthly_payment: float
    total_paid_loan: float
    total_interest: float
    initial_outlay: float
    info_lines: List[str] = field(default_factory=list)

    def to_extra_json(self) -> str:
        payload: Dict[str, Any] = {
            "monthly_payment": round(self.monthly_payment, 2),
            "loan_amount": round(self.loan_amount, 2),
            "ltv_percent": round(self.ltv_percent, 4),
            "annual_interest_percent": self.annual_interest_percent,
            "years": self.years,
            "purchase_price": self.purchase_price,
            "total_cost": round(self.total_cost, 2),
            "itp_percent": self.itp_percent,
            "initial_outlay": round(self.initial_outlay, 2),
            "effective_entry_total": round(self.effective_entry_total, 2),
            "savings_cash": round(self.savings_cash, 2),
            "tasacion_fee": round(self.tasacion_fee, 2),
        }
        return json.dumps(payload, ensure_ascii=False)


def french_monthly_payment(
    principal: float, annual_interest_percent: float, years: int
) -> float:
    """Cuota mensual (préstamo a tipo fijo anual, en %)."""
    if principal <= 0 or years <= 0:
        return 0.0
    r = float(annual_interest_percent) / 100.0 / 12.0
    n = int(years) * 12
    if r <= 0:
        return round(principal / n, 2)
    return round(
        principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1),
        2,
    )


def total_purchase_cost_breakdown(
    purchase_price: float,
    first_home: bool,
    notary: float,
    registry: float,
    gestoria: float,
    tasacion_fee: float,
) -> Tuple[float, float, float, float]:
    """ITP %, importe ITP, total coste (compra + ITP + gastos incl. tasación)."""
    pp = max(0.0, float(purchase_price))
    itp_pct = 6.0 if first_home else 8.0
    itp_amt = round(pp * (itp_pct / 100.0), 2)
    notary = float(notary)
    registry = float(registry)
    gestoria = float(gestoria)
    tasacion_fee = float(tasacion_fee)
    other = notary + registry + gestoria + tasacion_fee
    total_cost = round(pp + itp_amt + other, 2)
    return itp_pct, itp_amt, other, total_cost


def min_savings_cash_hint(
    total_cost: float,
    valor_tasacion: float,
    tasacion_fee: float,
    loan_cap: float = LOAN_CAP_ON_APPRAISAL,
) -> float:
    """
    Mínimo a indicar en «ahorros a aportar» (efectivo), asumiendo que a la simulación
    se suma aparte el gasto de tasación. Mínimo total aportado = total_cost − 80%·valor_tasación.
    """
    vt = max(0.0, float(valor_tasacion))
    tc = max(0.0, float(total_cost))
    fee = max(0.0, float(tasacion_fee))
    max_loan = round(vt * loan_cap, 2)
    min_total_equity = max(0.0, tc - max_loan)
    return max(0.0, round(min_total_equity - fee, 2))


def fetch_euribor_implied_percent() -> Optional[float]:
    """
    Último cierre del futuro EBH28.CME (Yahoo Chart v8).
    Convención habitual: tipo implícito ≈ 100 − precio (en %).
    """
    try:
        url = f"{CHART_API_BASE}/{EURIBOR_YAHOO_TICKER}"
        r = requests.get(
            url,
            headers={
                **CHART_API_HEADERS,
                "Accept": "application/json",
                "Referer": "https://finance.yahoo.com/",
            },
            params={"range": "1mo", "interval": "1d"},
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        res = (data.get("chart") or {}).get("result") or []
        if not res:
            return None
        quotes = (res[0].get("indicators") or {}).get("quote") or [{}]
        closes = (quotes[0] or {}).get("close") or []
        for v in reversed(closes):
            if v is not None and isinstance(v, (int, float)) and v > 0:
                implied = max(0.0, round(100.0 - float(v), 4))
                return implied
    except Exception as e:
        logger.warning("Euribor Yahoo fetch failed: %s", e)
    return None


def run_simulation(
    purchase_price: float,
    savings_cash: float,
    years: int,
    first_home: bool,
    notary: float = DEFAULT_NOTARY,
    registry: float = DEFAULT_REGISTRY,
    gestoria: float = DEFAULT_GESTORIA,
    tasacion_fee: float = DEFAULT_TASACION,
    valor_tasacion_inmueble: Optional[float] = None,
    annual_interest_percent: float = 3.5,
) -> MortgageSimulationResult:
    """
    Préstamo máximo regulado: LOAN_CAP_ON_APPRAISAL × valor de tasación del inmueble.
    Si valor_tasacion_inmueble es None o 0, se usa el precio de compra.
    Efectivo aportado en simulación = ahorros (casilla) + importe gasto tasación.
    Solo tipo fijo nominal anual.
    """
    pp = max(0.0, float(purchase_price))
    sav = max(0.0, float(savings_cash))
    yrs = max(1, min(40, int(years)))
    rate = max(0.0, float(annual_interest_percent))

    notary = float(notary)
    registry = float(registry)
    gestoria = float(gestoria)
    tasacion_fee = float(tasacion_fee)

    itp_pct, itp_amt, other_sum, total_cost = total_purchase_cost_breakdown(
        pp, first_home, notary, registry, gestoria, tasacion_fee
    )

    vt_raw = valor_tasacion_inmueble
    if vt_raw is None or float(vt_raw) <= 0:
        valor_tas = pp
    else:
        valor_tas = max(0.0, float(vt_raw))

    max_loan = round(valor_tas * LOAN_CAP_ON_APPRAISAL, 2)
    effective_entry = round(sav + tasacion_fee, 2)
    loan_needed = round(total_cost - effective_entry, 2)

    min_cash = min_savings_cash_hint(total_cost, valor_tas, tasacion_fee)

    if sav > pp + 1e-6:
        raise ValueError(
            "Los ahorros a aportar no pueden superar el precio de compra de la vivienda."
        )
    if sav + 1e-6 < min_cash:
        raise ValueError(
            f"Ahorros insuficientes: el mínimo orientativo es {min_cash:.2f} € "
            f"(límite préstamo {LOAN_CAP_ON_APPRAISAL:.0%} sobre valor de tasación)."
        )

    if loan_needed > max_loan + 0.02:
        raise ValueError(
            f"El préstamo necesario ({loan_needed:.2f} €) supera el "
            f"{LOAN_CAP_ON_APPRAISAL:.0%} del valor de tasación ({max_loan:.2f} €). "
            "Aumenta los ahorros o revisa el valor de tasación."
        )

    loan = max(0.0, loan_needed)
    ltv_pct = round((loan / valor_tas) * 100.0, 2) if valor_tas > 0 else 0.0

    monthly = french_monthly_payment(loan, rate, yrs)
    n = yrs * 12
    total_paid = round(monthly * n, 2) if monthly > 0 else 0.0
    total_int = round(total_paid - loan, 2) if loan > 0 else 0.0

    initial_outlay = effective_entry

    def _eur(x: float) -> str:
        return f"{x:.2f} €"

    info: List[str] = [
        f"Coste total estimado (compra + ITP + gastos, incl. tasación): {_eur(total_cost)}",
        f"Valor tasación (límite préstamo {LOAN_CAP_ON_APPRAISAL:.0%}): {_eur(valor_tas)} → máx. {_eur(max_loan)}",
        f"Aportación efectiva (ahorros + gasto tasación): {_eur(effective_entry)}",
        f"Préstamo: {_eur(loan)} (LTV sobre valor tasación: {ltv_pct:.2f}%)",
    ]

    return MortgageSimulationResult(
        purchase_price=pp,
        first_home=first_home,
        itp_percent=itp_pct,
        itp_amount=itp_amt,
        notary=notary,
        registry=registry,
        gestoria=gestoria,
        tasacion_fee=tasacion_fee,
        other_expenses_sum=round(other_sum, 2),
        total_purchase_side=round(pp + itp_amt, 2),
        total_cost=total_cost,
        savings_cash=sav,
        effective_entry_total=effective_entry,
        loan_amount=loan,
        valor_tasacion_inmueble=valor_tas,
        ltv_percent=ltv_pct,
        max_loan_by_policy=max_loan,
        min_savings_cash=min_cash,
        annual_interest_percent=rate,
        years=yrs,
        monthly_payment=monthly,
        total_paid_loan=total_paid,
        total_interest=total_int,
        initial_outlay=initial_outlay,
        info_lines=info,
    )
