# Plan de implementación — Watchlist: valoración, inputs y sectores especiales

Documento vivo: consolida lo acordado para la evolución de la pestaña **Watchlist** (métricas, BD, UI, ajuste numérico tipo B, no rentables, bancos y real estate).

---

## 1. Objetivo

- Unificar **inputs** (niveles A / B / C), **fórmulas** (vista ~12 meses y **5 años**), **ajuste de riesgo/calidad (estilo B)** y **modos sectoriales** (General, Banks, Real Estate).
- Persistir todo lo que entre en fórmulas en **base de datos** (`watchlist` + `watchlist_config`).
- UI: fila compacta + **columna expandir (`+`)** para inputs detallados (por defecto contraído).

---

## 2. Alcance por fases

| Fase | Contenido |
|------|-----------|
| **2.1** | General (no banks / no RE): nuevos campos, blend de crecimiento, PER fair, estilo B, EPS ≤ 0, fila expandible, migración BD, IA extracción. |
| **2.2** | **Banks** y **Real Estate**: mappings usuario Sector+Industria en Ajustes, inputs y fórmulas específicas, sin mezclar con Net debt/EBITDA “industrial”. |

---

## 3. Clasificación del activo (`valuation_mode`)

El `Asset` ya tiene `sector` y `industry` (`app/models/asset.py`).

**Resolución del modo** (orden sugerido):

1. Si `(sector, industry)` del activo coincide con una entrada configurada por el usuario como **Banks** → modo `banks`.
2. Si coincide con **Real Estate** → modo `realestate`.
3. En caso contrario → modo `general`.

**Empate:** si un par apareciera en ambas listas (error de configuración), regla explícita en código: p. ej. priorizar `banks` o bloquear guardado en Ajustes con validación.

**Valores vacíos:** si `sector` o `industry` del activo están vacíos → siempre `general` hasta que el usuario complete el asset.

---

## 4. Ajustes de watchlist — configuración Sector + Industria

En el modal **⚙️ Ajustes de watchlist** (`watchlist.html`), añadir una sección (p. ej. “Clasificación sectorial”):

### 4.1 Estructura en `WatchlistConfig`

Guardar en JSON existente o nuevo campo dedicado; propuesta **clave dentro de `color_thresholds` o JSON paralelo** `valuation_sector_rules`:

```json
{
  "valuation_sector_rules": {
    "banks": [
      { "sector": "Financials", "industry": "Banks" },
      { "sector": "Financials", "industry": "Regional Banks" }
    ],
    "realestate": [
      { "sector": "Real Estate", "industry": "REITs" },
      { "sector": "Real Estate", "industry": "Real Estate Services" }
    ]
  }
}
```

- Comparación **case-sensitive o normalizada** (definir en implementación; recomendado: `strip()` + comparación insensible a mayúsculas para robustez con datos TIKR).
- Opcional futuro: `industry: null` = “todo el sector” (wildcard); no es obligatorio en v1.

### 4.2 Comportamiento UX

- El usuario **añade filas** (Sector + Industria) a la lista Banks y otra lista RE.
- Al **editar inputs** de un asset cuyo par coincide → mostrar **solo el formulario y las ayudas** del modo correspondiente (labels, tooltips, campos obligatorios).
- Si el usuario **no configuró** listas → todos los activos se tratan como **general** (comportamiento actual ampliado).

### 4.3 Backend

- Helper único: `resolve_valuation_mode(asset, watchlist_config) -> "general" | "banks" | "realestate"`.
- `WatchlistMetricsService.update_all_metrics` (o sucesor) **delega** en estrategia por modo.

### 4.4 Selector Sector → Industria (cascada) y casos límite

**Objetivo:** al elegir **Sector**, el desplegable de **Industria** solo muestra industrias **compatibles** con ese sector.

**Origen de datos (recomendado v1):**

- Consulta sobre `assets`: pares distintos `(sector, industry)` no nulos; construir mapa `{ sector: [industrias…] }` ordenado.
- Opcional: filtrar a activos del usuario o unión “cartera ∪ watchlist” para reducir ruido.
- Si un sector tiene una sola industria en el catálogo, el segundo select puede preseleccionarla.

**Al cambiar sector en la fila de Ajustes:**

- Si la industria elegida **no** pertenece al nuevo sector → **limpiar industria** (o reset) y mensaje: *“Selecciona una industria del sector elegido.”*
- Al guardar, validar que el par es coherente con el catálogo (v1); texto libre total posible en fase posterior.

**Quitar activos de la watchlist:**

- Las listas Banks/RE en Ajustes **no** dependen de que el ticker esté en watchlist; al quitar un activo **no** se borran reglas.

**Usuario elimina o cambia un par en Ajustes que aún coincide con algún `Asset`:**

- Ese activo pasa a modo **`general`** en el siguiente cálculo.
- Opcional: al guardar Ajustes, aviso *“N activos dejarán de clasificarse como Banco/RE”* (conteo por join `Watchlist` + `Asset`).
- Valores ya guardados en columnas específicas banco/RE en `watchlist`: **conservar en BD** pero **no usar** en fórmulas hasta que el modo vuelva a aplicar (no borrar trabajo del usuario).

**Asset sin sector o sin industria:**

- Siempre modo `general` hasta completar ficha.

**Industria deseada que no está en el catálogo:**

- v1: editar el **Asset** para alinear texto con pares ya vistos en BD.
- v2 opcional: pares manuales por usuario en JSON (`custom_sector_industry_pairs`).

---

## 5. Nivel A — Core (inputs)

**Principio v1:** ningún campo obligatorio u opcional en watchlist solo para “contexto” o semáforos: **debe entrar** en PEGY/`valoracion_12m`, fair, target 5y, rentabilidades, y/o **\(F_{\text{final}}\)** (estilo B). *Excepción aceptada:* datos de **calendario** fuera del motor numérico (ver `next_earnings_date` abajo).

| Campo | Obligatorio (general rentable) | Si falta |
|-------|--------------------------------|----------|
| Precio actual (caché) | Sí | Sin rentabilidades ni % vs fair. |
| PER NTM | Sí | Sin PEGY / valoración 12m / target clásico que dependa de él. |
| EPS NTM | Sí | Sin fair PER×EPS ni target beneficio en modo rentable. |
| Revenue CAGR 2–3y (%) | Sí | Sin PEGY completo; definir fallback (solo EPS CAGR) con aviso. |
| EPS CAGR 2–3y (%) | Sí | Mezcla `g` solo revenue; aviso “incompleto”. |
| Dividendo NTM (%) | No | Tratar como **0%**. |
| PER fair | No | Sin `P_fair = EPS × PER_fair`; sí PEGY si hay datos. |
| Próximos resultados (`next_earnings_date`) | No | **No entra en fórmulas de precio/rentabilidad**; solo calendario / IA / UX. Opción: mover a ficha `Asset` y no duplicar en inputs de valoración. |

**Excluido v1 (no campo watchlist):** **PER LTM**, **crecimiento EPS 1y** — no estaban en el núcleo de fórmulas; eran apoyo visual / semáforos.

---

## 6. Nivel B — Precisión (general)

| Campo | Si falta | Notas |
|-------|----------|--------|
| Net debt / EBITDA | Factor 1.00 | **No usar** en modo banks/RE (N/A). |
| FCF / Beneficio neto (o FCF/acción ÷ EPS) | Factor 1.00 | Si BN o EPS ≤ 0: no forzar ratio; ver régimen no rentable. |

---

## 7. Nivel C — Calidad (general)

Dos columnas:

- **Margen EBITDA (%)**
- **Margen operativo (%)**
- **ROIC (%)**

Combinación para estilo B: \(f_{\text{margin}} = \sqrt{f_{\text{ebitda}} \cdot f_{\text{op}}}\); si solo uno existe, usar ese factor.

---

## 8. Fórmulas — modo `general`

### 8.1 Vista ~12 meses

- **PEGY / valoración 12m** (convención % como hoy):  
  \(\text{PEGY} = \text{PER}_{NTM} / (\text{CAGR\%} + d)\), luego signo invertido para UI (`valoracion_12m`).
- Denominador: **misma lógica de crecimiento** que el producto (p. ej. media aritmética o geométrica de revenue CAGR y EPS CAGR en %).
- **Fair explícito** (si PER fair y EPS NTM > 0):  
  \(P_{\text{fair}} = \text{EPS}_{NTM} \times \text{PER}_{fair}\).

### 8.2 Vista 5 años

- **Target bruto:**  
  \(P_{5y}^{\text{bruto}} = \text{EPS}_{NTM} \times (1 + g_{\text{eff}})^5 \times \text{PER}_T\)  
  - \(g_{\text{eff}}\): blend revenue + EPS CAGR (arith / geom / ponderado; documentar elección en código).  
  - \(\text{PER}_T = \text{PER}_{fair}\) si existe; si no, \(\text{PER}_{NTM}\).  
  - Opcional posterior: tope o “fade” sobre \(g_{\text{eff}}\).
- **Rentabilidad 5y y anualizada:** misma filosofía que hoy (`calculate_rentabilidad_*`), con precio actual y dividendo (0 si falta).

**Código actual:** `calculate_target_price_5yr` usa solo revenue CAGR y PER NTM; este plan sustituye/ampliña en fase 2.1.

---

## 9. Estilo B — factores (solo `general`, no banks/RE en v1 del ajuste)

Agregación:

\[
F = f_{\text{deuda}} \cdot f_{\text{fcf}} \cdot f_{\text{margin}} \cdot f_{\text{roic}}
\]

\[
F_{\text{final}} = \min(1.06,\ \max(0.72,\ F))
\]

\[
P_{5y}^{\text{adj}} = P_{5y}^{\text{bruto}} \cdot F_{\text{final}}
\]

### 9.1 Tablas de umbrales (defaults; persistir en `WatchlistConfig` para tunear)

**Net debt / EBITDA**

| ND/EBITDA | Factor | Motivo breve |
|-----------|--------|----------------|
| ≤ 2.0 | 1.00 | Deuda moderada vs EBITDA. |
| 2.0–3.0 | 0.98 | Zona habitual; menor colchón. |
| 3.0–4.0 | 0.94 | Elevado; más sensibilidad a ciclo y tipos. |
| 4.0–5.0 | 0.88 | Alto. |
| > 5.0 o EBITDA ≤ 0 | 0.80 | Muy alto / métrica rota. |

**FCF / Beneficio neto**

| Ratio | Factor | Motivo breve |
|-------|--------|----------------|
| ≥ 0,90 | 1.00 | Resultado bien respaldado por caja. |
| 0,75–0,90 | 0.97 | WC/capex razonables. |
| 0,50–0,75 | 0.92 | Calidad de beneficio débil. |
| < 0,50 | 0.85 | Poco respaldo en caja. |
| FCF ≤ 0 y BN > 0 | 0.85 | Gana en cuenta, no en caja. |

**ROIC %**

| ROIC | Factor | Motivo breve |
|------|--------|----------------|
| < 6 | 0.93 | Bajo coste de capital típico. |
| 6–9 | 0.97 | Cerca del filo. |
| 9–12 | 1.00 | Neutro. |
| 12–18 | 1.02 | Creación de valor clara. |
| > 18 | 1.03 | Tope de bonus. |

**Margen EBITDA %** (defaults “industrial/consumer” genéricos)

| EBITDA % | Factor |
|----------|--------|
| < 12 | 0.96 |
| 12–18 | 0.99 |
| 18–28 | 1.00 |
| > 28 | 1.02 |

**Margen operativo %**

| Op % | Factor |
|------|--------|
| < 8 | 0.95 |
| 8–12 | 0.99 |
| 12–22 | 1.00 |
| > 22 | 1.02 |

Dato ausente → factor **1.00** para ese bloque.

---

## 10. EPS negativo / no rentables (`general`)

- No usar \( \text{EPS} \times \text{PER} \) ni PEGY clásico como si fuera rentable.
- Objetivos **12m y 5y** con lógica alternativa: **ingresos**, CAGR revenue, múltiplo sobre ventas o **precio objetivo manual**, FCF si aplica; modo visible en UI (“No rentable”).
- EPS CAGR puede ser **N/A** si hay cruce por cero.
- FCF/BN: en pérdidas, neutral o regla FCF/Revenue en fase posterior.

---

## 11. UI — columna expandir

- Columna **+** / chevron por fila: **expandir/contraer** bloque de inputs del usuario.
- Por defecto **contraído**; tabla muestra columnas esenciales (ticker, precio, tier, target, valoración, etc.).
- Accesibilidad: `aria-expanded`, foco teclado.

---

## 12. Base de datos

- Nuevas columnas en `watchlist` para todos los inputs de niveles A/B/C (nombres finales en migración).
- Ampliar `WATCHLIST_MANUAL_FIELD_KEYS` y extracción IA (`watchlist_report_extract_service`, `watchlist_ia_template`).
- Opcional: columnas caché `target_price_5yr_gross`, `valuation_adjustment_factor`, `target_price_5yr` (ajustado) para auditoría.
- `WatchlistConfig`: JSON `valuation_sector_rules` + JSON `risk_adjustment_rules` (copia de tablas 9.1 para overrides por usuario).

---

## 13. Modo **Banks** — enfoque (fase 2.2)

**Problema:** PER × EPS “puro” y **Net debt/EBITDA industrial** no interpretan el balance de un banco (el pasivo con depósitos no es “deuda” comparable a una industrial).

**Principio:** valoración y riesgo se centran en **capital (CET1)**, **rentabilidad (ROE)**, **valor contable (P/B, P/TBV)**, **calidad de activos (NPL, provisiones)** y **eficiencia / NIM**. Misma fila `watchlist` que otros modos; en UI solo se muestran y validan campos del modo banco.

### 13.1 Reutilización vs columnas nuevas

Leyenda: **Reutiliza** = campo BD existente; **Nuevo** = columna dedicada; **No usar** = oculto en este modo / factor 1 / N/A.

| Métrica / uso | Tipo | Obl. | Opc. | Notas |
|---------------|------|------|------|--------|
| Precio actual (`precio_actual`) | Reutiliza | Sí | — | Cotización / caché. |
| Próximos resultados (`next_earnings_date`) | Reutiliza | No | Sí | Calendario / IA. |
| Dividendo NTM % (`ntm_dividend_yield`) | Reutiliza | No | Sí | Si falta → 0%. Muy relevante en bancos. |
| EPS NTM (`eps`) | Reutiliza | Sí* | — | *Banco rentable; base si se usa trayectoria por beneficio. |
| PER NTM (`per_ntm`) | Reutiliza | No | Sí | Referencia; **no** sustituye P/B en el núcleo. |
| Revenue CAGR 2–3y (`cagr_revenue_yoy`) | Reutiliza | No | Sí | En UI: “Crecimiento ingresos / NII (2–3y) %” si el usuario usa esa fila TIKR. |
| EPS CAGR 2–3y (campo general) | Reutiliza | No | Sí | Si TIKR da CAGR EPS; alternativa **BVPS CAGR** (`bvps_cagr_yoy` nuevo, opcional). |
| PER fair (`per_fair`) | No usar como PER | — | — | En modo banco usar **`pb_fair`** (nuevo); no reutilizar `per_fair` como P/B sin renombrar en UI. |
| Net debt/EBITDA, FCF/BN, márgenes EBITDA/op, ROIC industrial | No usar | — | — | No entrar en fórmulas banco; columnas pueden existir pero N/A. |
| **P/B** (precio / book value per share) | Nuevo (`price_to_book`) | Sí | — | Eje principal de valoración relativa. |
| **P/B fair** (objetivo) | Nuevo (`pb_fair`) | No | Sí | Análogo a PER fair en general; desviación 12m vs precio implícito. |
| **ROE %** (LTM o NTM según TIKR) | Nuevo (`roe_pct`) | Sí | — | Documentar en UI si es LTM o NTM. |
| **CET1 ratio %** (o “Common Equity Tier 1” según fuente) | Nuevo (`cet1_ratio_pct`) | Sí | — | Solvencia regulatoria; estilo B. |
| **NPL ratio %** (non-performing loans / préstamos, o stage 3 según jurisdicción) | Nuevo (`npl_ratio_pct`) | No | Sí | Calidad de activo; estilo B. |
| **Cost-to-income %** (o **efficiency ratio** si TIKR lo nombra así) | Nuevo (`cost_to_income_pct`) | No | Sí | Menor = más eficiente (confirmar convención TIKR: a veces como % de ingresos). |
| **NIM %** (net interest margin) | Nuevo (`nim_pct`) | No | Sí | Motor de ingresos por balance. |
| **Book value per share** (`bvps`) | Nuevo opcional | No | Sí | Para \(P_{\text{fair}}=\text{BVPS}\times\text{P/B}_{\text{fair}}\) y proyección BVPS; si falta, usar equivalencia con precio y P/B. |
| **Liquidity / LDR** (loans-to-deposits o similar) | Nuevo (`loan_to_deposit_pct`) | No | Sí | Si disponible en TIKR; estilo B. |
| **Cost of risk %** (coste de riesgo / préstamos medios o definición IFRS local) | Nuevo (`cost_of_risk_pct`) | No | Sí | Complementa NPL en \(F_{\text{bank}}\). Ej. **HSBK ~0,8%**. |

**Fuera de alcance v1 (no columnas, no \(F_{\text{bank}}\), no semáforos):** **P/Tangible book**, **cobertura mora (Allowance/NPL)**, **charge-offs / provision rate** como input separado, **Texas ratio**, **leverage ratio** Basel adicional — no aportan suficiente precisión incremental frente a la complejidad; CET1 + NPL + cost of risk cubren capital y crédito.

**Resumen obligatorios modo banco (mínimo viable):** precio, **P/B**, **ROE %**, **CET1 %**, **EPS NTM** (banco con beneficios positivos). **Recomendado:** **P/B fair**, dividendo, **NPL %**, **efficiency / cost-to-income**, **NIM**, **cost of risk**, **LDR** si existe en TIKR.

**Referencia HSBK (usuario, no exhaustiva):** NIM **6,4%**, Efficiency **19,2%**, CET1 **18,2%** (mapeado desde Tier 1), Cost of risk **0,8%** — validar convención “efficiency” (en muchos mercados **menor % = más eficiente**).

### 13.2 Fórmulas — predicción ~12 meses y 5 años (esbozo)

**Convención:** \(\text{BVPS}_0\) o EPS como ancla; \(M_T\) = **P/B** objetivo (fair) si existe; si no, \(M_0\) = P/B actual.

#### A) Vista ~12m — fair transversal

\[
P_{\text{fair}} = \text{BVPS}_{\text{ref}} \times \text{P/B}_{\text{fair}}
\]

- Si el usuario no tiene **BVPS** explícito: \(P_{\text{fair}} = P_0 \times (\text{P/B}_{\text{fair}} / \text{P/B}_0)\) (equiv. al desplazamiento del múltiplo).
- **Upside %:** \((P_{\text{fair}} / P_0 - 1) \times 100\).

#### B) Proyección ~12m (opcional, análoga a REIT)

- **\(g_{1y}\):** blend **crecimiento EPS NTM** implícito, **CAGR EPS/BVPS 2y**, o **crecimiento préstamos/NII** (campo opcional); clamp conservador banco (p. ej. −5% … +15%).
- **\(P_{1y}^{\text{bruto}} \approx \text{EPS}_{1y} \times \text{PER}_{1y}\)** o **\(\text{BVPS}_{1y} \times \text{P/B}_{1y}\)** según implementación elegida (documentar una vía principal para v1).
- Aplicar **\(F_{\text{bank}}\)** (estilo B).

#### C) Proyección 5 años

\[
P_{5y}^{\text{bruto}} = \text{BVPS}_{\text{base}} \times (1 + g_{\text{BVPS}})^5 \times \text{P/B}_T
\quad\text{o}\quad
\text{EPS}_{\text{base}} \times (1 + g_{\text{EPS}})^5 \times \text{PER}_T
\]

- **Preferencia producto:** **BVPS** + **P/B terminal** suele ser más estable que PER × EPS en bancos; si el usuario solo mantiene EPS, usar vía EPS coherente.
- \(g_{\text{BVPS}}\): blend **ROE × (1 − payout)** aproximación, o CAGR BVPS TIKR, o input usuario; **cap** bajo (crecimiento book value raramente sostenido >10–12% nominal salvo casos extremos).
- \(\text{P/B}_T\): **P/B fair** o P/B actual.
- **Rentabilidad 5y / anualizada:** igual espíritu que modos anteriores (capital + dividendo \(d\) lineal sobre precio actual).

### 13.3 Estilo B — bancos (`F_bank`)

**No confundir con “datos calculados por el servidor sin input”:** los ratios (CET1, NPL, etc.) deben **existir en BD** (usuario o IA). El **factor** \(F_{\text{bank}}\) sí se **calcula** en servidor a partir de esos inputs.

**Agregación recomendada:**

\[
f_{\text{asset}} = \sqrt{f_{\text{npl}} \cdot f_{\text{cor}}}
\quad\text{(NPL y cost of risk muy correlacionados)}
\]

\[
F_{\text{bank}} = f_{\text{cet1}} \times f_{\text{eff}} \times f_{\text{nim}} \times f_{\text{asset}} \times f_{\text{ldr}}
\]

\[
F_{\text{bank,final}} = \min(1{,}06,\; \max(0{,}72,\; F_{\text{bank}}))
\]

- **Efficiency / cost-to-income:** en el producto se asume convención **menor % = más eficiente** (gastos no interés / ingresos operativos típicos). Si la fuente del usuario usa la **inversa**, documentar inversión en UI antes de aplicar tabla.
- Dato ausente → factor **1,00** para ese bloque. **`f_ldr`:** si no hay LDR, omitir del producto (o = 1,00).

### 13.4 Estilo B bancos — umbrales y factores por defecto

*Defaults para `bank_risk_adjustment_rules`; afinables por usuario. Referencia mental: bancos emergentes / retail con CET1 alto y NPL en single digits.*

#### 1) CET1 % (más alto = más colchón regulatorio)

| CET1 % | Factor | Por qué |
|--------|--------|--------|
| ≥ 14,0 | 1,00 | Por encima de mínimos habituales y con margen en la mayoría de jurisdicciones. |
| ≥ 12,0 y < 14,0 | 0,98 | Aún razonable; menor margen ante pérdidas. |
| ≥ 10,0 y < 12,0 | 0,93 | Zona de tensión relativa al “comfort” del mercado. |
| < 10,0 | 0,86 | Cerca o bajo estándares exigibles; riesgo de ampliación / restricción al dividendo. |

*(HSBK ~18,2% → factor 1,00.)*

#### 2) Efficiency / cost-to-income % (**menor = mejor**)

| Efficiency % | Factor | Por qué |
|--------------|--------|--------|
| ≤ 40 | 1,02 | Muy eficiente vs banca universal típica (suele 50–65%). |
| > 40 y ≤ 55 | 1,00 | Zona sana. |
| > 55 y ≤ 70 | 0,96 | Estructura de costes pesada. |
| > 70 | 0,90 | Ineficiencia marcada; presiona ROE sin palanca de ingresos. |

*(Si el dato del usuario es **19,2%** con la misma convención “menor mejor”, cae en **1,02**; si fuera otra definición, recalibrar tabla.)*

#### 3) NIM % (mayor suele ser mejor en banca tradicional; contexto país)

| NIM % | Factor | Por qué |
|-------|--------|--------|
| ≥ 5,5 | 1,00 | Motor de margen de intereses sólido en muchos mercados. |
| ≥ 4,0 y < 5,5 | 0,98 | Aceptable. |
| ≥ 3,0 y < 4,0 | 0,94 | Presión en spread / mix de activos. |
| < 3,0 | 0,88 | NIM muy bajo salvo modelo de negocio especial. |

*(HSBK **6,4%** → 1,00.)*

#### 4) NPL % (non-performing / préstamos; **menor = mejor**)

| NPL % | Factor | Por qué |
|-------|--------|--------|
| ≤ 3,0 | 1,02 | Cartera muy saneada. |
| > 3,0 y ≤ 5,0 | 1,00 | Zona habitual “normalizada”. |
| > 5,0 y ≤ 8,0 | 0,96 | Mora material. |
| > 8,0 y ≤ 12,0 | 0,90 | Estrés crediticio significativo. |
| > 12,0 | 0,84 | Riesgo elevado; mercado suele exigir mayor prima. |

*(HSBK ~7,7% → ~0,96.)*

#### 5) Cost of risk % (**menor = mejor**, provisiones netas / activos en riesgo según definición)

| Cost of risk % | Factor | Por qué |
|----------------|--------|--------|
| ≤ 1,0 | 1,00 | Coste de riesgo contenido. |
| > 1,0 y ≤ 2,0 | 0,97 | Subida moderada del ciclo. |
| > 2,0 y ≤ 3,5 | 0,92 | Deterioro claro. |
| > 3,5 | 0,85 | Ciclo de crédito adverso. |

*(HSBK **0,8%** → 1,00.)*

#### 6) Loans / deposits (LDR) % — **opcional** (mayor = más iliquididad relativa)

| LDR % | Factor | Por qué |
|-------|--------|--------|
| ≤ 85 | 1,00 | Colchón de funding cómodo. |
| > 85 y ≤ 95 | 0,99 | Zona habitual. |
| > 95 y ≤ 105 | 0,94 | Préstamos cerca o por encima de depósitos; dependencia de wholesale. |
| > 105 | 0,88 | Estructura de funding más frágil. |

#### Coherencia

- **NPL** y **cost of risk** se combinan con **\(\sqrt{f_{\text{npl}} f_{\text{cor}}}\)** para no penalizar dos veces el mismo deterioro.
- Umbrales son **orientativos globales**; Kazajistán / HSBK pueden requerir ajuste en `WatchlistConfig` tras más ejemplos.

### 13.5 Qué entra en la fórmula “precio” vs solo en \(F_{\text{bank}}\)

| Dato | Trayectoria 12m / 5y (precio bruto) | Estilo B \(F_{\text{bank}}\) |
|------|-------------------------------------|------------------------------|
| Precio, P/B, BVPS, EPS, P/B fair, \(g\) | Sí | No |
| ROE, PER (vía EPS) | Sí (vía \(g\) BVPS o vía EPS) | No |
| Dividendo \(d\) | Sí (rentabilidad total) | No |
| CET1, NIM, efficiency, NPL, cost of risk, LDR | No | Sí |

### 13.6 Estado de implementación

- Documentado en este plan; **código y migración BD pendientes** (fase 2.2).

---

## 14. Modo **Real Estate** / REIT — enfoque (fase 2.2)

### 14.1 Reutilización vs columnas nuevas

| Métrica / uso | Tipo | Obl. | Opc. | Notas |
|---------------|------|------|------|--------|
| Precio actual | Reutiliza | Sí | — | Igual. |
| Próximos resultados | Reutiliza | No | Sí | Igual. |
| Dividendo NTM % | Reutiliza | No | Sí | **Muy** relevante REIT; si falta → 0%. |
| PER NTM / EPS NTM | Reutiliza | No | — | En REIT clásico el núcleo es **FFO/AFFO**, no GAAP EPS; **no obligar** PER/EPS salvo como “EPS GAAP” secundario. |
| Revenue CAGR 2–3y | Reutiliza | No | Sí | Proxy de crecimiento de ingresos por activos; útil si es “same-store” o ingreso operativo; etiqueta clara en UI. |
| Net debt/EBITDA (industrial) | — | — | — | **No**; usar ratio REIT (deuda/activos o deuda/EBITDA ajustado REIT). |
| FCF/BN (industrial) | — | — | — | No aplica modo RE. |
| Márgenes / ROIC industrial | — | — | — | No aplica modo RE. |
| **FFO / acción** (NTM o último) | Nuevo (`ffo_per_share`) | Sí* | — | *Mínimo uno entre FFO y AFFO como base de múltiplo. |
| **AFFO / acción** | Nuevo (`affo_per_share`) | No | Sí | Preferido si disponible (más cercano a caja distribuible). |
| **P/FFO o P/AFFO** (múltiplo NTM) | Nuevo (`p_ffo` o `p_affo`) | Sí | — | Análogo al PER en general; puede ser un solo campo `price_to_ffo` con tooltip. |
| **P/FFO fair** o **P/AFFO fair** | Nuevo (`p_ffo_fair`) | No | Sí | Análogo a PER fair. |
| **Crecimiento FFO/AFFO 2–3y %** | Nuevo (`cagr_ffo_yoy`) | No | Sí | Mejor que EPS CAGR para 5y; si falta, usar revenue CAGR con aviso. |
| **Deuda / activos brutos** o **deuda/EBITDA ajust.** | Nuevo (`reit_leverage_ratio` + tipo) | No | Sí | Estilo B; definir numerador/denominador según TIKR. |
| **Ocupación %** | Nuevo (`occupancy_pct`) | No | Sí | Riesgo ingresos; fuente usuario (IR, Google verificado, etc.). |
| **WALT (años)** | Nuevo (`walt_years`) | No | Sí | Vida media ponderada de arrendamientos; entra sobre todo en **estilo B**. |
| **Same-store / comparable growth %** | Nuevo (`same_store_growth_pct`) | No | Sí | Crecimiento anual **homogéneo** (rental revenue, NOI o “comp” según informe); etiquetar en UI el **tipo** si hace falta. No es exactamente NOI en todos los comunicados; el usuario alinea con la fila que use. |

**Excluido v1:** **Prima / descuento vs NAV** como input separado (exigiría **NAV/sh** y segunda lógica de fair; no entra en las fórmulas actuales sin ampliar el modelo).

**Resumen obligatorios modo RE (mínimo viable):** precio, **FFO o AFFO por acción**, **P/FFO (o P/AFFO)**, dividendo (puede ser 0). **Recomendado:** **crecimiento** vía `cagr_ffo_yoy` y/o **same_store_growth_pct**, ratios **estilo B** (apalancamiento REIT, coberturas FFO, ocupación, WALT).

### 14.2 Fórmulas — predicción ~12 meses y 5 años (REIT)

**Convención:** base de flujo **AFFO/acción** si existe; si no, **FFO/acción**. Se denota \(\text{AFFO}\) por brevedad. Dividendo \(d\) en % (como en general). Múltiplo **P/AFFO** actual \(M_0\) (NTM). Múltiplo objetivo \(M_T\): **P/AFFO fair** del usuario si existe; si no, \(M_T = M_0\) (neutral).

#### A) Vista “fair” transversal (ancla a 12m sin proponer trayectoria de mercado)

\[
P_{\text{fair}} = \text{AFFO}_{\text{NTM}} \times M_T
\quad\text{con } M_T = \text{P/AFFO}_{\text{fair}} \text{ si está definido, si no } M_0.
\]

- **Upside vs precio actual:** \((P_{\text{fair}} / P_0 - 1) \times 100\).

Esto responde a “¿cara/barata **hoy** frente a tu múltiplo y a AFFO NTM?”.

#### B) Proyección explícita **~1 año** (precio objetivo operativo simple)

Idea: en 1 año el beneficio por acción “operativo” crece con el **crecimiento homogéneo (same-store)** y el múltiplo converge suavemente hacia el fair (o se mantiene).

1. **Crecimiento AFFO 1y** (en decimal), combinando lo que el usuario aporta:

\[
g_{1y} = w_{\text{ss}} \cdot \frac{\text{same\_store\_growth\_pct}}{100}
+ w_{\text{ffo}} \cdot \frac{g_{\text{FFO,implícito 1y}}}{100}
\]

- Por defecto sugerido: \(w_{\text{ss}} = 0{,}6\), \(w_{\text{ffo}} = 0{,}4\) si hay **CAGR o revisiones**; si solo hay same-store, \(w_{\text{ss}}=1\).
- \(g_{\text{FFO,implícito 1y}}\) puede derivarse de **CAGR FFO 2y** de TIKR / \(\sqrt{1+\text{CAGR}_2}-1\) o dejar un campo opcional “growth FFO 1y %” en v2.
- **Clamp** prudente REIT: p. ej. \(g_{1y} \in [-3\%,\, 8\%]\) salvo que el usuario fuerce override.

2. **AFFO esperado en ~1 año:**

\[
\text{AFFO}_{1y} \approx \text{AFFO}_{\text{NTM}} \times (1 + g_{1y})
\]

(NTM ya es forward; esta fórmula es una **segunda capa** de ajuste por same-store vs consenso; si se prefiere evitar doble conteo, usar solo \(g_{1y}\) cuando el usuario **no** confía en NTM y usa LTM × (1+same-store) — documentar modo “base LTM” en implementación.)

3. **Múltiplo en 1 año:** interpolación lineal hacia fair en un año:

\[
M_{1y} = M_0 + \alpha \cdot (M_T - M_0), \quad \alpha \in [0{,}5,\, 1{,}0] \text{ (default } 1 \text{ = plena convergencia en 12m).}
\]

4. **Precio objetivo ~1 año (bruto):**

\[
P_{1y}^{\text{bruto}} = \text{AFFO}_{1y} \times M_{1y}
\]

5. **Estilo B:** \(P_{1y}^{\text{adj}} = P_{1y}^{\text{bruto}} \times F_{\text{RE}}\) (mismo bloque de factores que abajo, con clamp).

**Same-store en la captura (ej. Realty Income):** “same-store rental revenue growth” YoY o **guidance** anual (p. ej. 1,0–1,3% → el usuario puede meter **1,15%** como `same_store_growth_pct`). Si en otro REIT informan **NOI comparable**, usar esa fila y el mismo campo.

#### C) Proyección **5 años** (bruto + estilo B)

\[
P_{5y}^{\text{bruto}} = \text{AFFO}_{\text{base}} \times (1 + g_{\text{eff}})^5 \times M_T
\]

- \(\text{AFFO}_{\text{base}}\): **AFFO NTM** (recomendado). Alternativa: LTM si el usuario desactiva NTM.
- \(g_{\text{eff}}\): **crecimiento compuesto anual** per share, mezcla prudente:

\[
g_{\text{eff}} = v_{\text{ffo}} \cdot \frac{\text{CAGR FFO/AFFO 2–3y}}{100}
+ v_{\text{ss}} \cdot \frac{\text{same\_store\_growth\_pct}}{100}
\]

- Defaults: \(v_{\text{ffo}} = v_{\text{ss}} = 0{,}5\) si ambos existen; si solo uno, peso 1 en el disponible.
- **Tope y suelo** para REIT maduro: p. ej. \(g_{\text{eff}} \in [-2\%,\, 7\%]\) tras el blend (ajustable en `WatchlistConfig`), para no extrapolar M&A/dilución como si fuera orgánico 5 años seguidos.

- \(M_T\): P/AFFO fair si existe; si no, \(M_0\).

**Rentabilidades 5y / anualizada:** mismas expresiones que en modo general (capital + aportación de dividendo \(d\) lineal), sustituyendo \(P_{5y}^{\text{adj}}\).

#### D) Estilo B REIT (`F_RE`) — dónde entran **WALT**, ocupación, apalancamiento, coberturas

Factores multiplicativos (con **clamp** global análogo al modo general, p. ej. \([0{,}72,\, 1{,}06]\)), datos ausentes → factor 1.

| Bloque | Rol |
|--------|-----|
| **Net debt / EBITDA** (ratio REIT de TIKR) | Penalizar apalancamiento alto (tabla dedicada REIT, distinta a industrial). |
| **FFO / intereses** o **FFO a deuda** | Penalizar cobertura baja. |
| **Ocupación %** | p. ej. &lt; 95% penalización leve; &lt; 90% fuerte. |
| **WALT (años)** | Cartera con vencimientos más cercanos = más riesgo de rollover: p. ej. WALT &lt; 6 → factor &lt; 1; 6–12 → neutro; &gt; 12 → ligero bonus acotado. **Realty Income ~9–10 a** → zona neutra/bonus suave según tabla. |

**WALT y same-store no sustituyen** a \(g_{\text{eff}}\) en la exponencial de 5 años de forma duplicada: el **crecimiento homogéneo** alimenta \(g\); **WALT** y **ocupación** ajustan el target vía **\(F_{\text{RE}}\)** (riesgo operativo).

#### E) Estilo B REIT — **umbrales y factores por defecto** (coherentes entre sí)

Todos los factores son **1,00** si el dato falta. Combinación:

\[
F_{\text{RE}} = f_{\text{lev}} \times f_{\text{ffc}} \times f_{\text{ftd}} \times f_{\text{occ}} \times f_{\text{walt}}
\]

\[
F_{\text{RE,final}} = \min(1{,}06,\; \max(0{,}72,\; F_{\text{RE}}))
\]

*(Mismo espíritu que el modo general: recorte acotado, bonus moderado.)*

**1) Net debt / EBITDA** (ratio REIT tal como lo muestra TIKR; no el cut industrial de bancos.)

| Net debt / EBITDA | Factor | Motivo (default) |
|-------------------|--------|------------------|
| ≤ 5,5× | **1,00** | Apalancamiento habitual en REITs grandes “investment grade”. |
| > 5,5× y ≤ 7,0× | **0,98** | Zona elevada; menor margen ante subida de tipos. |
| > 7,0× y ≤ 9,0× | **0,94** | Apretado; más sensibilidad a refinanciación. |
| > 9,0× | **0,88** | Muy elevado para el universo REIT típico del producto. |

**2) FFO / gastos financieros** (cobertura de intereses con FFO; “FFO Interest Coverage” en TIKR.)

| Cobertura (×) | Factor | Motivo |
|---------------|--------|--------|
| ≥ 4,5× | **1,00** | Cómoda para deuda a largo plazo. |
| ≥ 3,5× y < 4,5× | **0,98** | Aceptable (muchas triple-net cotizan ~3,5–4,5×). |
| ≥ 2,5× y < 3,5× | **0,93** | Tensión si el ciclo empeora. |
| < 2,5× | **0,85** | Riesgo alto de estrés. |

**3) FFO / deuda total** (FFO to Total Debt en TIKR; en × o % según pantalla — usar **mismo numerador** que en TIKR.)

| FFO / Total debt | Factor | Motivo |
|------------------|--------|--------|
| ≥ 0,15× | **1,00** | Servicio de deuda bien cubierto por FFO. |
| ≥ 0,11× y < 0,15× | **0,98** | Zona habitual en REITs maduros (~0,12–0,14). |
| ≥ 0,08× y < 0,11× | **0,94** | Bajo vs histórico sectorial. |
| < 0,08× | **0,88** | Débil; dependencia de mercados de capital. |

**4) Ocupación %**

| Ocupación | Factor | Motivo |
|-----------|--------|--------|
| ≥ 98,0 % | **1,02** | Cartera muy estable (bonus suave, tope ya limitado por clamp global). |
| ≥ 95,0 % y < 98,0 % | **1,00** | Normal en calidad REIT. |
| ≥ 90,0 % y < 95,0 % | **0,96** | Vacancia material. |
| < 90,0 % | **0,88** | Riesgo operativo alto. |

**5) WALT (años)**

| WALT | Factor | Motivo |
|------|--------|--------|
| < 5 | **0,94** | Renovaciones relativamente cercanas; riesgo de rollover. |
| ≥ 5 y < 7 | **0,97** | Aún aceptable pero menos colchón. |
| ≥ 7 y ≤ 12 | **1,00** | Zona neutra (**Realty Income ~9–10 a** cae aquí). |
| > 12 y ≤ 15 | **1,01** | Arrendamientos largos; bonus muy acotado. |
| > 15 | **1,02** | Bonus tope por WALT (el clamp global limita el efecto total). |

**Coherencia:** cobertura FFO/intereses y FFO/deuda están **correlacionadas** con apalancamiento; multiplicarlas puede ser severo. **Recomendación de implementación:** usar **media geométrica** solo entre \(f_{\text{ffc}}\) y \(f_{\text{ftd}}\): \(f_{\text{cov}} = \sqrt{f_{\text{ffc}} \cdot f_{\text{ftd}}}\), y luego \(F_{\text{RE}} = f_{\text{lev}} \times f_{\text{cov}} \times f_{\text{occ}} \times f_{\text{walt}}\).

Estos valores son **defaults** en `WatchlistConfig` (`re_risk_adjustment_rules`) y se pueden afinar tras backtesting con casos reales (p. ej. O, otros REIT).

---

### 14.3 Fórmulas (resumen ejecutivo)

| Horizonte | Núcleo |
|-----------|--------|
| **~12m** | \(P_{\text{fair}} = \text{AFFO}_{\text{NTM}} \times M_T\); opción **\(P_{1y}\)** con \(g_{1y}\) (same-store + FFO) y convergencia de múltiplo. |
| **5y** | \(P_{5y} = \text{AFFO}_{\text{base}} (1+g_{\text{eff}})^5 M_T \times F_{\text{RE}}\) con \(g_{\text{eff}}\) = blend CAGR FFO/AFFO + same-store, caps REIT. |

---

## 14.4 Ejemplos numéricos (opcional)

No son necesarios para cerrar el diseño de campos; **sí** ayudan a calibrar umbrales estilo B y a validar nombres TIKR. Cuando se implemente 2.2, conviene un caso **banco** y un **REIT** con capturas (como NVDA) para fijar defaults.

---

## 15. IA (Deep Research → watchlist)

- Plantillas de extracción **por modo**: prompts distintos para general / banks / RE.
- Tras clasificar el asset, encolar o aplicar extracción con el **prompt del modo** correspondiente.

---

## 16. Checklist de implementación técnica

- [ ] Migración SQL: columnas `watchlist` + JSON en `watchlist_config`.
- [ ] `resolve_valuation_mode` + tests.
- [ ] Refactor métricas: estrategia por modo (`GeneralValuation`, `BankValuation`, `RealEstateValuation`).
- [ ] Modal Ajustes: listas editables Banks / RE + guardado JSON + **select Sector → Industria en cascada** (API de pares desde `assets`).
- [ ] `watchlist.html`: fila expandible; formularios condicionados por modo.
- [ ] API/rutas: validación al guardar inputs según modo.
- [ ] Actualizar extracción IA y `WATCHLIST_MANUAL_FIELD_KEYS` por modo (o subconjuntos documentados).
- [ ] Documentar en UI tooltips qué métricas usa cada modo.

---

## 17. Referencias en código actual

- Modelos: `app/models/watchlist.py` (`Watchlist`, `WatchlistConfig`).
- Cálculos: `app/services/watchlist_metrics_service.py`.
- UI Ajustes: `app/templates/portfolio/watchlist.html` (modal ⚙️).
- Asset: `app/models/asset.py` (`sector`, `industry`).
