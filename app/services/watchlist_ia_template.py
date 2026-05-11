"""
Briefing para «Informes IA» en watchlist: núcleo de 5 campos + extracción ampliada por modo
de valoración (general / banks / realestate).

Por defecto la app usa **Gemini Flash** (``generate_content``, rápido y barato). Opcional:
Deep Research con ``GEMINI_WATCHLIST_IA_USE_DEEP_RESEARCH=1``.

No usa ReportTemplate del usuario: una petición por activo.
Salida esperada: breve + tabla de extracción + bloque de código JSON; si falta, el extractor puede usar Flash de nuevo.
"""
from __future__ import annotations

# Título guardado en company_reports (sin plantilla FK): lote global barato (Flash).
WATCHLIST_IA_REPORT_TITLE = "Watchlist IA (Flash)"
# Una fila encolada desde Acciones: Deep Research (misma extracción; no pisa origen usuario).
WATCHLIST_IA_REPORT_TITLE_DR_ROW = "Watchlist IA (Deep Research, fila)"

# Cinco claves mínimas (lote IA histórico + siempre presentes en el JSON).
WATCHLIST_IA_CORE_JSON_KEYS: tuple[str, ...] = (
    "next_earnings_date",
    "per_ntm",
    "ntm_dividend_yield",
    "eps",
    "cagr_revenue_yoy",
)

_WATCHLIST_IA_TITLE_ALIASES = frozenset(
    {
        WATCHLIST_IA_REPORT_TITLE,
        WATCHLIST_IA_REPORT_TITLE_DR_ROW,
        "Watchlist IA (Deep Research)",
    }
)


def is_watchlist_ia_report_title(title: str | None) -> bool:
    """True si el informe pertenece al lote Informes IA (título actual o legado)."""
    return (title or "").strip() in _WATCHLIST_IA_TITLE_ALIASES


# Títulos con «ranura» única por (usuario, activo): al generar otro del mismo tipo se borra el anterior.
WATCHLIST_IA_UNIQUE_SLOT_TITLES = frozenset(
    {
        WATCHLIST_IA_REPORT_TITLE,
        WATCHLIST_IA_REPORT_TITLE_DR_ROW,
    }
)


def delete_prior_watchlist_ia_reports_same_slot(
    user_id: int, asset_id: int, template_title: str
) -> int:
    """
    Elimina informes previos con el mismo ``template_title`` para dejar como máximo uno
    por activo (solo Flash y Deep Research fila). Libera huecos dentro del límite de 5 informes.
    """
    t = (template_title or "").strip()
    if t not in WATCHLIST_IA_UNIQUE_SLOT_TITLES:
        return 0
    from app import db
    from app.models.company_report import CompanyReport

    q = CompanyReport.query.filter_by(
        user_id=user_id, asset_id=asset_id, template_title=t
    )
    rows = q.all()
    n = len(rows)
    for r in rows:
        db.session.delete(r)
    if n:
        db.session.flush()
    return n


# Orden estable de claves JSON adicionales por modo (debe coincidir con columnas watchlist / manual keys).
WATCHLIST_IA_EXTRA_KEYS_ORDER: dict[str, tuple[str, ...]] = {
    "general": (
        "per_fair",
        "cagr_eps_yoy",
        "net_debt_to_ebitda",
        "fcf_margin_pct",
        "net_income_margin_pct",
        "fcf_to_net_income",
        "ebitda_margin_pct",
        "operating_margin_pct",
        "roic_pct",
    ),
    "banks": (
        "price_to_book",
        "pb_fair",
        "roe_pct",
        "cet1_ratio_pct",
        "npl_ratio_pct",
        "cost_to_income_pct",
        "nim_pct",
        "bvps",
        "loan_to_deposit_pct",
        "cost_of_risk_pct",
        "bvps_cagr_yoy",
    ),
    "realestate": (
        "ffo_per_share",
        "affo_per_share",
        "price_to_ffo",
        "p_ffo_fair",
        "cagr_ffo_yoy",
        "reit_leverage_ratio",
        "reit_leverage_kind",
        "occupancy_pct",
        "walt_years",
        "same_store_growth_pct",
        "ffo_interest_coverage",
        "ffo_to_total_debt",
    ),
}

_IA_EXTRA_KEY_HELP: dict[str, dict[str, str]] = {
    "general": {
        "per_fair": "PER fair u objetivo (múltiplo ×), número o null.",
        "cagr_eps_yoy": "CAGR EPS 2–3 años, **porcentaje numérico** (ej. 10.0) o null.",
        "net_debt_to_ebitda": "Net debt / EBITDA (×) o null.",
        "fcf_margin_pct": "TIKR **Levered Free Cash Flow Margin %**, columna **LTM** (Ratios → Margin analysis), **% numérico** o null.",
        "net_income_margin_pct": "TIKR **Normalized Net Income Margin %**, columna **LTM** (Ratios → Margin analysis), **% numérico** o null.",
        "fcf_to_net_income": "Ratio FCF/BN directo (0–1 típico) **solo** si no hay ambos márgenes LTM (`Levered Free Cash Flow Margin %` y `Normalized Net Income Margin %`); si ambos vienen, preferir null aquí.",
        "ebitda_margin_pct": "Margen EBITDA **% numérico** o null.",
        "operating_margin_pct": "Margen operativo **% numérico** o null.",
        "roic_pct": "ROIC **% numérico** o null.",
    },
    "banks": {
        "price_to_book": "P/B actual (×) o null.",
        "pb_fair": "P/B objetivo / fair (×) o null.",
        "roe_pct": "ROE **% numérico** o null.",
        "cet1_ratio_pct": "CET1 **% numérico** o null.",
        "npl_ratio_pct": "NPL / préstamos **% numérico** o null.",
        "cost_to_income_pct": "Cost-to-income / eficiencia **%** (menor suele ser mejor) o null.",
        "nim_pct": "NIM **% numérico** o null.",
        "bvps": "Valor contable por acción (moneda por acción) o null.",
        "loan_to_deposit_pct": "Préstamos / depósitos (LDR) **%** o null.",
        "cost_of_risk_pct": "Cost of risk **%** o null.",
        "bvps_cagr_yoy": "CAGR BVPS 2–3 años **% numérico** o null.",
    },
    "realestate": {
        "ffo_per_share": "FFO por acción (número) o null.",
        "affo_per_share": "AFFO por acción (número) o null; preferido si hay dato.",
        "price_to_ffo": "P/FFO o P/AFFO (×) coherente con el numerador usado, o null.",
        "p_ffo_fair": "P/FFO fair objetivo (×) o null.",
        "cagr_ffo_yoy": "CAGR FFO/AFFO 2–3 años **% numérico** o null.",
        "reit_leverage_ratio": "Apalancamiento tipo net debt/EBITDA REIT (×) o null.",
        "reit_leverage_kind": "Texto breve (≤32 caracteres) describiendo el ratio de apalancamiento, o null.",
        "occupancy_pct": "Ocupación **% numérico** o null.",
        "walt_years": "WALT en años (número) o null.",
        "same_store_growth_pct": "Crecimiento same-store **% numérico** anual o null.",
        "ffo_interest_coverage": "FFO / gastos financieros (× cobertura) o null.",
        "ffo_to_total_debt": "FFO / deuda total (×, convención TIKR) o null.",
    },
}

_IA_MODE_LABEL = {
    "general": "general (PEGY / ajuste estilo B; activo no clasificado como banco ni REIT en Ajustes)",
    "banks": "banco — rellena también ratios P/B, capital (CET1), rentabilidad y calidad de activo",
    "realestate": "REIT / inmobiliario — rellena FFO/AFFO, P/FFO, ocupación, WALT y coberturas",
}


def watchlist_ia_all_keys_for_mode(mode: str) -> tuple[str, ...]:
    """Claves JSON que el informe debe incluir (núcleo + ampliación por modo)."""
    m = mode if mode in WATCHLIST_IA_EXTRA_KEYS_ORDER else "general"
    return WATCHLIST_IA_CORE_JSON_KEYS + WATCHLIST_IA_EXTRA_KEYS_ORDER[m]


def _ia_mode_appendix(valuation_mode: str) -> str:
    m = valuation_mode if valuation_mode in WATCHLIST_IA_EXTRA_KEYS_ORDER else "general"
    label = _IA_MODE_LABEL.get(m, _IA_MODE_LABEL["general"])
    help_map = _IA_EXTRA_KEY_HELP[m]
    key_lines = "\n".join(
        f"- `{k}`: {help_map[k]}" for k in WATCHLIST_IA_EXTRA_KEYS_ORDER[m]
    )
    return f"""

---
**Modo para este informe (definido por la aplicación según sector/industria y tus listas en Ajustes): {label}**

En el **mismo** objeto JSON que las cinco claves obligatorias, incluye **todas** las claves siguientes \
(usa `null` si no hay cifra verificable en fuentes públicas; no inventes):

{key_lines}
---
"""


# Briefing principal enviado al modelo (Flash o Deep Research) para Informes IA (español).
WATCHLIST_IA_DEEP_DESCRIPTION = """\
Objetivo: obtener de fuentes públicas fiables magnitudes para la empresa \
(símbolo/ISIN en el contexto). **Mínimo** las cinco magnitudes núcleo; **además** todas las claves \
del bloque «Modo para este informe» que aparece al final de estas instrucciones. \
No escribas un informe de inversión largo ni recomendaciones de compra/venta.

**Entrega obligatoria (concisa, en español):**
1. Una sección titulada **«Datos watchlist (extracción)»** con una **tabla markdown** de tres columnas: \
`campo` | `valor` | `fuente breve (nombre + tipo: IR, CNMV, prensa, etc.)`.
2. Inmediatamente después, un bloque de código **```json** (y cierre ```) con **un solo objeto** (claves exactas; \
usa `null` si no hay dato verificable, nunca inventes). El objeto debe incluir **las cinco claves núcleo** y \
**todas las claves adicionales** indicadas en la sección «Modo para este informe» al final.

**Ejemplo de forma (sustituye null por valores reales; añade las claves del modo):**
```json
{"next_earnings_date": "YYYY-MM-DD o null", "per_ntm": null, "ntm_dividend_yield": null, "eps": null, "cagr_revenue_yoy": null}
```

**Las cinco claves núcleo (significado y formato):**
- `next_earnings_date`: próxima fecha de presentación de resultados (earnings), string `YYYY-MM-DD` o `null`.
- `per_ntm`: PER o P/E **NTM** (número decimal, sin texto).
- `ntm_dividend_yield`: dividend yield **NTM** en **porcentaje como número** (ej. `2.3` = 2,3 %) o `null`.
- `eps`: beneficio por acción (EPS), número en la moneda del activo o `null`.
- `cagr_revenue_yoy`: CAGR de ingresos interanual en **porcentaje como número** (ej. `8.0`) o `null` estimado de los próximos 2 años.

**Reglas:** si las fuentes contradicen, prioriza la más reciente con cita y una sola frase de nota. \
Los porcentajes en el JSON son siempre **números** (ej. 12.5 para 12,5 %), salvo `reit_leverage_kind` que es texto. \
Mantén el cuerpo **breve** (prioriza la tabla + JSON; evita capítulos largos).
"""

# Puntos de control (lista breve) que recibe el job Informes IA como `points`.
WATCHLIST_IA_DEEP_POINTS: list[str] = [
    "Verificar empresa = símbolo/ISIN del contexto (no confundir con homónimos).",
    "Earnings: fecha explícita de próximos resultados (IR, exchange, o prensa verificable).",
    "PER NTM: indicar en la tabla si es forward/NTM y la fuente del dato.",
    "Dividend yield NTM: mismo convenio (NTM); en JSON como porcentaje numérico.",
    "EPS: unidad y moneda coherentes con el activo.",
    "CAGR ingresos YoY: definición (periodo) y fuente; en JSON como % numérico.",
]


def get_watchlist_ia_deep_brief(
    *, use_dr_row_title: bool = False, valuation_mode: str = "general"
) -> tuple[str, list[str], str]:
    """(description, points, template_title) para un job Informes IA."""
    title = WATCHLIST_IA_REPORT_TITLE_DR_ROW if use_dr_row_title else WATCHLIST_IA_REPORT_TITLE
    mode = valuation_mode if valuation_mode in WATCHLIST_IA_EXTRA_KEYS_ORDER else "general"
    description = WATCHLIST_IA_DEEP_DESCRIPTION + _ia_mode_appendix(mode)
    points = list(WATCHLIST_IA_DEEP_POINTS)
    if mode == "banks":
        points.append(
            "Modo banco: en la tabla y JSON prioriza P/B, CET1, ROE, NIM, mora (NPL) y cost of risk si constan en IR o fuentes comparables."
        )
    elif mode == "realestate":
        points.append(
            "Modo REIT: prioriza AFFO o FFO por acción, P/FFO, ocupación, WALT, same-store growth y ratios deuda/cobertura (FFO/interés, FFO/deuda) si constan."
        )
    else:
        points.append(
            "Modo general: deuda neta/EBITDA; FCF/ventas y BN/ventas en % (o ratio FCF/BN legado); márgenes EBITDA/operativo y ROIC si constan."
        )
    return (description, points, title)
