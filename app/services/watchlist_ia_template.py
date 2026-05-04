"""
Briefing fijo para «Informes IA» en watchlist: solo Deep Research, objetivo mínimo = 5 campos editables.

No usa ReportTemplate del usuario: una sola petición optimizada por activo.
Salida esperada: breve + sección/tablas para extracción; idealmente un bloque ```json final
(Flash sigue como respaldo si falta el JSON).

En ``run_deep_research_report`` el lote Informes IA usa ``research_prompt_style="watchlist_minimal"``:
prompt corto sin el bloque largo de informe completo de ficha (menos tokens / contradicciones).
Presupuesto de polling por activo: 20 min por defecto (``GEMINI_WATCHLIST_IA_MAX_WAIT_SECONDS``).
Velocidad/coste: por defecto **modo directo** Deep Research (sin fase de plan colaborativo); para el bucle
lento plan+aprobación: ``GEMINI_WATCHLIST_IA_COLLAB_PLAN=1``.
"""
from __future__ import annotations

# Título guardado en company_reports (sin plantilla FK).
WATCHLIST_IA_REPORT_TITLE = "Watchlist IA (Deep Research)"

# Briefing principal enviado al agente Deep Research (español).
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

# Puntos de control (lista breve) que recibe `run_deep_research_report` como `points`.
WATCHLIST_IA_DEEP_POINTS: list[str] = [
    "Verificar empresa = símbolo/ISIN del contexto (no confundir con homónimos).",
    "Earnings: fecha explícita de próximos resultados (IR, exchange, o prensa verificable).",
    "PER NTM: indicar en la tabla si es forward/NTM y la fuente del dato.",
    "Dividend yield NTM: mismo convenio (NTM); en JSON como porcentaje numérico.",
    "EPS: unidad y moneda coherentes con el activo.",
    "CAGR ingresos YoY: definición (periodo) y fuente; en JSON como % numérico.",
]


def get_watchlist_ia_deep_brief() -> tuple[str, list[str], str]:
    """(description, points, template_title) para un job Informes IA."""
    return (
        WATCHLIST_IA_DEEP_DESCRIPTION,
        list(WATCHLIST_IA_DEEP_POINTS),
        WATCHLIST_IA_REPORT_TITLE,
    )
