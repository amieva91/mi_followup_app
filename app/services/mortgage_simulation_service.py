"""
Simulación compra vivienda: gastos de compra por defecto, ITP, LTV 80/90, tasación mínima, cuota francesa.
Euribor: futuro CME EBH28 (convención precio ≈ 100 − tipo anual implícito %).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

CHART_API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FollowUp/1.0; mortgage-sim)"
}
CHART_API_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

# Valores por defecto (editables en UI; alineados con ejemplos de usuario)
DEFAULT_NOTARY = 1200.0
DEFAULT_REGISTRY = 450.0
DEFAULT_GESTORIA = 250.0
DEFAULT_TASACION = 290.0

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
    tasacion: float
    other_expenses_sum: float
    total_purchase_side: float
    total_cost: float
    savings: float
    loan_amount: float
    ltv_mode: str
    ltv_on_appraisal: float
    min_appraisal: float
    annual_interest_percent: float
    years: int
    monthly_payment: float
    total_paid_loan: float
    total_interest: float
    euribor_reference: Optional[float]
    spread_percent: float
    info_lines: List[str] = field(default_factory=list)

    def to_extra_json(self) -> str:
        payload: Dict[str, Any] = {
            "monthly_payment": round(self.monthly_payment, 2),
            "loan_amount": round(self.loan_amount, 2),
            "min_appraisal": round(self.min_appraisal, 2),
            "ltv_mode": self.ltv_mode,
            "ltv_on_appraisal": self.ltv_on_appraisal,
            "annual_interest_percent": self.annual_interest_percent,
            "years": self.years,
            "purchase_price": self.purchase_price,
            "total_cost": round(self.total_cost, 2),
            "itp_percent": self.itp_percent,
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


def fetch_euribor_implied_percent() -> Optional[float]:
    """
    Último cierre del futuro EBH28.CME (Yahoo Chart).
    Convención habitual: tipo implícito ≈ 100 − precio (en %).
    """
    try:
        url = f"{CHART_API_BASE}/{EURIBOR_YAHOO_TICKER}"
        r = requests.get(
            url,
            headers=CHART_API_HEADERS,
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
    savings: float,
    years: int,
    first_home: bool,
    ltv_mode: str,
    notary: float = DEFAULT_NOTARY,
    registry: float = DEFAULT_REGISTRY,
    gestoria: float = DEFAULT_GESTORIA,
    tasacion: float = DEFAULT_TASACION,
    annual_interest_percent: float = 3.5,
    use_euribor_plus_spread: bool = False,
    spread_percent: float = 0.75,
) -> MortgageSimulationResult:
    """
    ltv_mode: '80' o '90' → préstamo máximo como fracción de la tasación (simplificado).
    ITP: 6% primera vivienda, 8% en otro caso (heurística).
    Si use_euribor_plus_spread: tipo = Euribor (futuro EBH28) + diferencial; si falla el fetch, base 3,0%.
    """
    pp = max(0.0, float(purchase_price))
    sav = max(0.0, float(savings))
    yrs = max(1, min(40, int(years)))

    eur_ref = fetch_euribor_implied_percent()
    if use_euribor_plus_spread:
        base = eur_ref if eur_ref is not None else 3.0
        rate = max(0.0, round(base + float(spread_percent), 4))
        spr_used = float(spread_percent)
    else:
        rate = max(0.0, float(annual_interest_percent))
        spr_used = 0.0

    itp_pct = 6.0 if first_home else 8.0
    itp_amt = round(pp * (itp_pct / 100.0), 2)

    notary = float(notary)
    registry = float(registry)
    gestoria = float(gestoria)
    tasacion = float(tasacion)
    other = notary + registry + gestoria + tasacion

    total_cost = round(pp + itp_amt + other, 2)
    loan_needed = max(0.0, round(total_cost - sav, 2))

    mode = (ltv_mode or "80").strip()
    if mode not in ("80", "90"):
        mode = "80"
    ltv_on = 0.80 if mode == "80" else 0.90

    min_appr = round(loan_needed / ltv_on, 2) if loan_needed > 0 else 0.0

    monthly = french_monthly_payment(loan_needed, rate, yrs)
    n = yrs * 12
    total_paid = round(monthly * n, 2) if monthly > 0 else 0.0
    total_int = round(total_paid - loan_needed, 2) if loan_needed > 0 else 0.0

    def _eur(s: float) -> str:
        return f"{s:.2f} €"

    info: List[str] = [
        f"Coste total estimado (compra + impuestos + gastos): {_eur(total_cost)}",
        f"Préstamo necesario: {_eur(loan_needed)}",
        (
            f"Con LTV {ltv_on * 100:.0f}% sobre tasación, la tasación mínima orientativa "
            f"debe ser al menos {_eur(min_appr)} (préstamo / {ltv_on})."
        ),
        "La entidad aplica el menor entre compra y tasación; aquí solo el límite por LTV.",
    ]
    if eur_ref is not None:
        info.append(
            f"Referencia Euribor (futuro {EURIBOR_YAHOO_TICKER}, 100−precio): ~{eur_ref:.2f}%."
        )
    elif use_euribor_plus_spread:
        info.append(
            "No se pudo leer el futuro Euribor; se usó 3,00% como base hasta obtener dato."
        )

    return MortgageSimulationResult(
        purchase_price=pp,
        first_home=first_home,
        itp_percent=itp_pct,
        itp_amount=itp_amt,
        notary=notary,
        registry=registry,
        gestoria=gestoria,
        tasacion=tasacion,
        other_expenses_sum=round(other, 2),
        total_purchase_side=round(pp + itp_amt, 2),
        total_cost=total_cost,
        savings=sav,
        loan_amount=loan_needed,
        ltv_mode=mode,
        ltv_on_appraisal=ltv_on,
        min_appraisal=min_appr,
        annual_interest_percent=rate,
        years=yrs,
        monthly_payment=monthly,
        total_paid_loan=total_paid,
        total_interest=total_int,
        euribor_reference=eur_ref,
        spread_percent=spr_used,
        info_lines=info,
    )
