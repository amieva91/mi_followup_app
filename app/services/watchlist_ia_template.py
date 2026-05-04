"""
Briefing fijo para «Informes IA» en watchlist: objetivo mínimo = 5 campos editables.

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


# Briefing principal enviado al modelo (Flash o Deep Research) para Informes IA (español).
WATCHLIST_IA_DEEP_DESCRIPTION = """\
Objetivo **único**: obtener de fuentes públicas fiables **exactamente cinco** magnitudes para la empresa \
(símbolo/ISIN indicados en el contexto). No escribas un informe de inversión largo ni recomendaciones de compra/venta.

**Entrega obligatoria (concisa, en español):**
1. Una sección titulada **«Datos watchlist (extracción)»** con una **tabla markdown** de tres columnas: \
`campo` | `valor` | `fuente breve (nombre + tipo: IR, CNMV, prensa, etc.)`.
2. Inmediatamente después, un bloque de código **```json** (y cierre ```) con **solo** este objeto (claves exactas; \
usa `null` si no hay dato verificable, nunca inventes):
```json
{"next_earnings_date": "YYYY-MM-DD o null", "per_ntm": null, "ntm_dividend_yield": null, "eps": null, "cagr_revenue_yoy": null}
```
(sustituye los null por números o fecha cuando corresponda).

**Los cinco campos (significado y formato del valor en el JSON):**
- `next_earnings_date`: próxima fecha de presentación de resultados (earnings), string `YYYY-MM-DD` o `null`.
- `per_ntm`: PER o P/E **NTM** (número decimal, sin texto).
- `ntm_dividend_yield`: dividend yield **NTM** en **porcentaje como número** (ej. `2.3` = 2,3 %) o `null`.
- `eps`: beneficio por acción (EPS), número en la moneda del activo o `null`.
- `cagr_revenue_yoy`: CAGR de ingresos interanual en **porcentaje como número** (ej. `8.0`) o `null` estimado de los próximos 2 años.

**Reglas:** si las fuentes contradicen, prioriza la más reciente con cita y una sola frase de nota. \
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


def get_watchlist_ia_deep_brief(*, use_dr_row_title: bool = False) -> tuple[str, list[str], str]:
    """(description, points, template_title) para un job Informes IA."""
    title = WATCHLIST_IA_REPORT_TITLE_DR_ROW if use_dr_row_title else WATCHLIST_IA_REPORT_TITLE
    return (WATCHLIST_IA_DEEP_DESCRIPTION, list(WATCHLIST_IA_DEEP_POINTS), title)
