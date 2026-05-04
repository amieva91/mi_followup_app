# 🎯 SPRINT 6 - DIVERSIFICACIÓN Y WATCHLIST
## 🚧 EN PROGRESO

**Versión**: v6.0.0  
**Inicio**: 24 Diciembre 2025  
**Duración estimada**: 2 semanas  
**Estado**: ✅ COMPLETADO (HITO 3 descoped)

**Última actualización**: 6 Febrero 2026  
**Progreso**: ~85% completado

---

## 🎯 OBJETIVOS DEL SPRINT

Implementar funcionalidades avanzadas de análisis de diversificación y gestión de watchlist para mejorar la toma de decisiones de inversión.

---

## 📋 HITOS PLANIFICADOS

### **HITO 1: Análisis de Concentración** 
**Prioridad**: 🔴 ALTA  
**Estado**: ✅ COMPLETADO (Sprint 4)

**Objetivos completados**:
- ✅ Identificar concentración de riesgo en el portfolio
- ✅ Análisis de diversificación por sector, país, industria, asset
- ✅ Visualización de concentración en dashboard (gráficos de distribución)

**Tareas completadas**:
- [x] Calcular métricas de concentración por asset (Top 10 + Otros)
- [x] Calcular métricas de concentración por sector/país/industria/broker/tipo
- [x] Visualización de concentración en dashboard del portfolio
  - Gráficos de distribución: País, Sector, Asset (Top 10), Industria, Broker, Tipo
  - Implementado en: `app/templates/portfolio/dashboard.html`

**Notas**:
- Las métricas de concentración ya están implementadas y visibles en el dashboard del portfolio
- No se requiere página dedicada adicional
- El índice de Herfindahl-Hirschman no es necesario
- Las alertas configurables se implementan en el HITO 2 (Watchlist)

---

### **HITO 2: Watchlist con Indicadores de Operativa y Métricas Avanzadas**
**Prioridad**: 🟡 MEDIA  
**Duración estimada**: 4-5 días  
**Estado**: 🚧 EN PROGRESO (Implementación avanzada)

**Objetivos**:
- ✅ Crear lista de assets a seguir (watchlist) y gestión completa
- ✅ Tabla única combinada con assets en cartera y watchlist
- ✅ Indicadores de operativa y métricas avanzadas por asset
- ✅ Sistema de Tier automático basado en valoración
- ✅ Alertas visuales basadas en peso en cartera y umbrales configurables
- ✅ Integración completa con AssetRegistry existente

**Progreso actual**:
- ✅ Modelos Watchlist y WatchlistConfig creados
- ✅ Servicios: WatchlistService, WatchlistMetricsService, WatchlistPriceUpdateService
- ✅ Rutas API completas (GET, POST, UPDATE, DELETE)
- ✅ Página watchlist.html con tabla combinada completa
- ✅ Sistema de colores implementado (parcialmente probado)
- ✅ Configuración de umbrales y rangos (Ajustes modal)
- ✅ Edición de métricas manuales
- ✅ Actualización de precios en batch
- ✅ Añadir assets desde Yahoo URL o AssetRegistry
- ✅ Integración con navegación principal
- ✅ Tooltips informativos en columnas calculadas
- ✅ Toast notifications personalizadas
- ✅ Modal de confirmación personalizado
- ✅ Ordenación por fecha próximos resultados (orden descendente por defecto)
- ✅ Header fijo (sticky header) implementado
- ✅ Sistemas de colores implementados y funcionando
- ✅ Todas las funcionalidades principales completadas

---

### **HITO 2bis: Informes de Investigación con API Gemini**
**Prioridad**: 🟡 MEDIA  
**Estado**: ✅ COMPLETADO (Ene-Feb 2026)

**Nota**: Esta funcionalidad no estaba estipulada originalmente en el Sprint 6; se implementó como extensión del detalle de asset (accesible desde Portfolio y Watchlist al hacer clic en un asset).

**Objetivos implementados**:

1. **Generación de informes Deep Research** (API Gemini Interactions)
   - Informes detallados sobre compañías usando el agente `deep-research-max-preview-04-2026`
   - Ejecución en segundo plano (varios minutos, hasta ~20-60 min)
   - Máximo 5 informes por (usuario, asset); al generar el 6º se elimina el más antiguo
   - Contenido en Markdown, renderizado a HTML en frontend (marked.js)

2. **Plantillas configurables** (modelo `ReportTemplate`)
   - Cada usuario define plantillas con: **título**, **descripción** (obligatoria), **puntos/preguntas** (opcionales)
   - Modal "Ajustes" en tab Informes para gestionar plantillas
   - Botón "Generar informe" habilitado solo si existe al menos una plantilla con descripción válida
   - Se selecciona plantilla antes de generar

3. **Resumen "About the Company"**
   - Descripción corta (3-5 líneas) de qué hace la compañía
   - API `generate_content` con `gemini-2.5-flash` (respuesta rápida, segundos)
   - Sección en tab Overview del asset
   - Se sobrescribe al volver a generar

4. **Envío por correo**
   - Botón "Enviar por correo" en el detalle del informe (solo si status=completed)
   - Envía el informe al **email registrado del usuario** (Flask-Mail)
   - Contenido Markdown convertido a HTML (librería `markdown`)
   - Requiere: `MAIL_SERVER`, `MAIL_USERNAME`, `MAIL_PASSWORD` (Gmail: **Contraseña de aplicación**, no la contraseña normal)

5. **Audio resumen TTS**
   - Botón "Generar audio resumen" en el detalle del informe
   - Generación en segundo plano con Gemini 3.1 Flash TTS (`gemini-3.1-flash-tts-preview`)
   - Flujo: 1) Resumen corto del informe con `gemini-2.5-flash`; 2) TTS sobre ese resumen; 3) Guardar WAV en `output/reports_audio/`
   - Polling automático cada 4s hasta completar o fallar
   - Botón "Descargar audio" cuando está listo

**Modelos y tablas**:
- `ReportTemplate`: user_id, title, description, points (JSON)
- `CompanyReport`: user_id, asset_id, template_title, content, status, error_msg, gemini_interaction_id, **audio_path**, **audio_status**, **audio_error_msg**, **audio_completed_at**, created_at, completed_at
- `AssetAboutSummary`: user_id, asset_id, summary

**Endpoints**:
- `POST /portfolio/asset/<id>/reports/generate` – Iniciar informe
- `GET /portfolio/asset/<id>/reports` – Listar informes
- `GET /portfolio/asset/<id>/reports/<report_id>` – Detalle de informe
- `GET /portfolio/api/reports/<report_id>/status` – Estado (incluye audio_status)
- `POST /portfolio/asset/<id>/reports/<report_id>/send-email` – Enviar por correo
- `POST /portfolio/asset/<id>/reports/<report_id>/generate-audio` – Iniciar TTS
- `GET /portfolio/asset/<id>/reports/<report_id>/audio` – Descargar WAV

**Configuración (.env)**:
- `GEMINI_API_KEY` – Obligatoria para informes y audio
- `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD` – Para envío por correo
- **Modelos Gemini** (opcionales, ver env.example): `GEMINI_MODEL_FLASH`, `GEMINI_MODEL_TTS`, `GEMINI_AGENT_DEEP_RESEARCH` – Permiten actualizar modelos sin cambiar código cuando Google lance nuevas versiones

**Archivos principales**:
- `app/services/gemini_service.py` – `run_deep_research_report`, `generate_about_summary`, `generate_report_tts_audio`
- `app/utils/email.py` – `send_report_email` (adjunta audio WAV si existe)
- `app/routes/portfolio.py` – Rutas de informes, email, audio; helper `_get_report_audio_path()`
- `app/templates/portfolio/asset_detail.html` – Tab Informes, toast notifications, estilos report-markdown

**Mejoras UX**: Toast en lugar de alert; botón Volver con history.back(); generación paralela de informes/audios

---

## 📊 ESTRUCTURA DE LA TABLA

**Tabla única combinada:**
- **Primero**: Assets en cartera (con peso e indicadores)
- **Después**: Assets en watchlist (sin holdings)
- **Ordenable** por cualquier columna (clic en header para alternar ascendente/descendente)
- **Orden por defecto**: Fecha próximos resultados (descendente - fechas más lejanas primero)
- **Assets seleccionables**: Click en asset muestra información detallada (igual que en portfolio)
- **Header fijo (sticky)**: El encabezado de la tabla permanece visible al hacer scroll

---

## 📋 COLUMNAS DE LA TABLA (Orden Final)

| # | Columna | Tipo | Descripción | Notas |
|---|---------|------|-------------|-------|
| 1 | **Symbol** | - | Símbolo del asset | - |
| 2 | **Nombre** | - | Nombre del asset | - |
| 3 | **Fecha próximos resultados** | Manual | Fecha de próxima presentación de resultados | Con colores (verde/amarillo/rojo) |
| 4 | **Indicador operativa** | Calculado | BUY / SELL / INCREASE / HOLD / REDUCE | Combina señales globales BUY/SELL (reglas configurables) con indicador por Tier (INCREASE/HOLD/REDUCE) |
| 5 | **Tier (1-5)** | Calculado | Tier de inversión según valoración | Basado en Valoración actual 12 meses (%). Con colores para assets en cartera |
| 6 | **Cantidad a aumentar/reducir** | Calculado | Diferencia vs cantidad del Tier (EUR) | En cartera: diferencia vs Tier. En watchlist sin cartera: muestra directamente la cantidad objetivo del Tier (sugerencia de compra inicial) |
| 7 | **Rentabilidad a 5 años (%)** | Calculado | Rentabilidad proyectada a 5 años | Basada en Target Price + Dividend Yield |
| 8 | **Rentabilidad Anual (%)** | Calculado | Rentabilidad anual proyectada | Basada en Target Price + Dividend Yield |
| 9 | **Valoración actual 12 meses (%)** | Calculado | Indicador barata/cara (punto de entrada) | Con colores (verde/amarillo/rojo) |
| 10 | **Target Price (5 yr)** | Calculado | Precio objetivo calculado a 5 años | Fórmula: (EPS * (1 + CAGR)^5) * PER |
| 11 | **Precio actual** | Actualizable | Precio de mercado actual | Actualizable con botón |
| 12 | **Peso en cartera (%)** | Calculado | Porcentaje del portfolio | Solo para assets en cartera, vacío para watchlist. Con colores según umbrales |
| 13 | **PER o NTM P/E** | Manual | Price-to-Earnings ratio | - |
| 14 | **NTM Dividend Yield (%)** | Manual | Dividend Yield próximos 12 meses | - |
| 15 | **EPS** | Manual | Earnings Per Share | - |
| 16 | **CAGR Revenue YoY (%)** | Manual | Crecimiento anual compuesto de ingresos | - |
| 17 | **Acciones** | - | Editar, Eliminar, etc. | - |

**Nota**: Todas las columnas aplican tanto a assets en cartera como en watchlist (excepto "Peso en cartera" y "Cantidad a aumentar/reducir" que son vacías para watchlist sin holdings).

---

## 🎨 SISTEMAS DE COLORES

### 1. Peso en cartera (%)

**Umbral máximo configurable** (ej: 10%) + **2 valores configurables** (Verde y Amarillo):
- 🟢 **Verde**: peso < (umbral + valor_verde)
- 🟡 **Amarillo**: (umbral + valor_verde) <= peso < (umbral + valor_amarillo)
- 🔴 **Rojo**: peso >= (umbral + valor_amarillo)

**Valores por defecto**: Verde = 1.0%, Amarillo = 2.5%

**Ejemplo con umbral = 10% y valores por defecto**:
- Verde: peso < 11%
- Amarillo: 11% <= peso < 12.5%
- Rojo: peso >= 12.5%

### 2. Fecha próximos resultados

- 🟢 **Verde**: Fecha no ha pasado aún
- 🟡 **Amarillo**: Fecha pasada pero <= 15 días
- 🔴 **Rojo**: Fecha pasada > 15 días

### 3. Valoración actual 12 meses (%)

- 🟢 **Verde**: >= 10% (alcista/barata)
- 🟡 **Amarillo**: 0% a < 10%
- 🔴 **Rojo**: < 0% (bajista/cara)

### 4. Indicador operativa

Combina dos niveles:

- **Indicador global BUY/SELL** (señales fuertes):
  - **BUY** (verde): Solo para assets en seguimiento sin posición (watchlist). Basado en reglas configurables sobre Valoración 12m y Rentabilidad Anual.
  - **SELL** (rojo): Solo para assets en cartera (con posición). Basado en reglas configurables sobre Valoración 12m y Rentabilidad Anual.
  - BUY/SELL globales **prevalecen** sobre el indicador por Tier.

- **Indicador por Tier** (solo para assets en cartera):
  - 🟢 **INCREASE** → Verde: muy por debajo del Tier objetivo (hay que aumentar posición).
  - ⚪ **HOLD** → Gris: dentro del margen aceptable alrededor del Tier (±25%).
  - 🟡 **REDUCE** → Amarillo: por encima del Tier objetivo (hay que reducir, pero sin ser señal fuerte de venta).

### 5. Tier (solo para assets en cartera)

**Comparación**: Cantidad invertida actual vs Cantidad del Tier configurada

- 🟢 **Verde**: Cantidad invertida dentro del rango del Tier (±25%)
  - Ejemplo: Tier = 2500€, invertido = 2600€ → dentro de 1875€-3125€ (verde)
- 🟡 **Amarillo**: Cantidad fuera del rango por más del 25% pero menos del 50%
  - Ejemplo: Tier = 2500€, invertido = 3500€ → fuera por 40% (amarillo)
- 🔴 **Rojo**: Cantidad fuera del rango por más del 50%
  - Ejemplo: Tier = 2500€, invertido = 4000€ → fuera por 60% (rojo)

**Fórmula para rangos**:
- Rango inferior: Tier_amount * 0.75
- Rango superior: Tier_amount * 1.25
- Desviación > 50%: fuera de Tier_amount * 0.5 o Tier_amount * 1.5

### 6. Precio actual

- Colores según cercanía al Target Price (3 niveles: verde/amarillo/rojo)

---

## 📐 FÓRMULAS DE CÁLCULO

### 1. Target Price (5 yr)
```
Target Price = EPS * (1 + CAGR Revenue YoY%)^5 * PER
```

**Ejemplo con VICI**:
- EPS = 2.77
- CAGR = 3.1% (0.031 en decimal)
- PER = 12.0
- Factor de crecimiento = (1 + 0.031)^5 = 1.164913
- Target Price = 2.77 * 1.164913 * 12.0 = 38.72

### 2. Valoración actual 12 meses (%)
```
PEGY = PER / (CAGR% + Dividend Yield%)
Desviación = (PEGY - 1) * 100
Valoración final = -Desviación
```

**Interpretación** (después de invertir el signo):
- **Verde (>= 10%)**: La acción está BARATA/INFRAVALORADA (PEGY < 1) → Buen punto de entrada
- **Amarillo (0% a < 10%)**: La acción está en rango NEUTRO
- **Rojo (< 0%)**: La acción está CARA/SOBREVALORADA (PEGY > 1) → Mal punto de entrada

**Ejemplo con VICI**:
- PER = 12.0
- Dividend Yield = 6.4%
- CAGR = 3.1%
- Denominador = 3.1% + 6.4% = 9.5%
- PEGY = 12.0 / 9.5 = 1.263158
- Desviación = (1.263158 - 1) * 100 = 26.32%
- **Valoración final = -26.32%** (ROJO: acción cara/sobrevalorada)

**Ejemplos adicionales**:
- PER=10, Dividend Yield=2%, CAGR=20% → PEGY = 10/(20+2) = 0.455 → Desviación = -54.5% → Valoración = +54.5% (VERDE: barata)
- PER=10, Dividend Yield=2%, CAGR=10% → PEGY = 10/(10+2) = 0.833 → Desviación = -16.7% → Valoración = +16.7% (VERDE: barata)

### 3. Rentabilidad a 5 años (%)
```
Ganancia de capital = (Target Price - Precio actual) / Precio actual * 100
Dividendos acumulados = Dividend Yield% * 5
Rentabilidad 5yr = Ganancia de capital + Dividendos acumulados
```

**Ejemplo con VICI**:
- Precio actual = 28.51
- Target Price 5yr = 38.72
- Dividend Yield = 6.4%
- Ganancia de capital = (38.72 - 28.51) / 28.51 * 100 = 35.82%
- Dividendos acumulados = 6.4% * 5 = 32.00%
- **Rentabilidad 5yr = 35.82% + 32.00% = 67.82%**

### 4. Rentabilidad Anual (%)
```
Si ganancia de capital > 0:
  Ganancia capital anualizada = ((Target Price / Precio actual)^(1/5) - 1) * 100
Si ganancia de capital <= 0:
  Pérdida capital anualizada = (Ganancia de capital / Precio actual) / 5 * 100

Rentabilidad anual = Ganancia capital anualizada + Dividend Yield%
```

**Ejemplo con VICI**:
- Precio actual = 28.51
- Target Price 5yr = 38.72
- Dividend Yield = 6.4%
- Ganancia capital anualizada = ((38.72 / 28.51)^(1/5) - 1) * 100 = 6.31%
- **Rentabilidad anual = 6.31% + 6.4% = 12.71%**

### 4. Tier (1-5)
- **Calculado automáticamente** basado en Valoración actual 12 meses (%)
- El usuario configura los rangos que determinan cada Tier
- Rangos configurables (ej: Tier 5 si >= 50%, Tier 4 si 30-50%, etc.)

**Rangos por defecto**:
- **Tier 5**: Valoración >= 50% (mejor valoración, más barata)
- **Tier 4**: Valoración >= 30% y < 50%
- **Tier 3**: Valoración >= 10% y < 30%
- **Tier 2**: Valoración >= 0% y < 10%
- **Tier 1**: Valoración < 0% (peor valoración, más cara)

**Ejemplo con VICI**:
- Valoración 12M = -26.32% (negativa)
- Como -26.32% < 0% → **Tier 1** (acción cara, no es buen momento de entrada)

### 5. Cantidad a aumentar/reducir (EUR)
```
Cantidad a aumentar/reducir = Cantidad_del_Tier - Cantidad_invertida_actual
```
- **Positivo**: Hay que comprar (INCREASE) - tienes menos que el Tier objetivo
- **Cero o pequeño (±25% del Tier)**: Dentro del margen (HOLD)
- **Negativo**: Hay que reducir (REDUCE) - tienes más que el Tier objetivo

**Ejemplo**:
- Tier 5 = 10000€, invertido = 3970€ → +6030€ (BUY, verde) - necesitas comprar más
- Tier 1 = 2500€, invertido = 2600€ → -100€ (HOLD, gris - dentro del ±25%)
- Tier 1 = 2500€, invertido = 5000€ → -2500€ (SELL, rojo) - tienes que vender

### 6. Indicador operativa (BUY/SELL/INCREASE/HOLD/REDUCE)

#### 6.1 Indicador por Tier (solo cartera)
- **Calculado automáticamente** basado en "Cantidad a aumentar/reducir" vs Tier
- **INCREASE**: Cantidad a aumentar/reducir > Tier_amount * 0.25 (positivo, necesitas comprar más) → Verde
- **HOLD**: `|cantidad_aumentar_reducir| <= Tier_amount * 0.25` (dentro del margen ±25%) → Gris
- **REDUCE**: Cantidad a aumentar/reducir < -(Tier_amount * 0.25) (negativo, necesitas vender/reducir) → Amarillo

**Lógica detallada**:
- Margen = Tier_amount * 0.25 (25% del Tier)
- Si `|cantidad_aumentar_reducir| <= margen` → HOLD
- Si `cantidad_aumentar_reducir > margen` → INCREASE (tienes menos que el Tier, necesitas comprar)
- Si `cantidad_aumentar_reducir < -margen` → REDUCE (tienes más que el Tier, necesitas reducir)

**Ejemplos (cartera)**:
- Tier 1 = 2500€, invertido = 2000€ → cantidad = 2500 - 2000 = +500€
  - Margen = 2500 * 0.25 = 625€
  - Como 500€ <= 625€ → **HOLD** (dentro del margen)
- Tier 5 = 10000€, invertido = 3970€ → cantidad = 10000 - 3970 = +6030€
  - Margen = 10000 * 0.25 = 2500€
  - Como 6030€ > 2500€ → **INCREASE** (verde, necesitas comprar más)
- Tier 1 = 2500€, invertido = 5000€ → cantidad = 2500 - 5000 = -2500€
  - Margen = 2500 * 0.25 = 625€
  - Como -2500€ < -625€ → **REDUCE** (amarillo, necesitas reducir posición)

#### 6.2 Indicador global BUY/SELL (reglas configurables)

Definido en configuración (`operativa_rules`) con esta estructura:
```json
{
  "buy": {
    "valoracion_12m": {"op": ">", "value": -12.5},
    "rentabilidad_anual": {"op": ">=", "value": 60.0},
    "combiner": "AND"
  },
  "sell": {
    "valoracion_12m": {"op": "<", "value": -12.5},
    "rentabilidad_anual": {},
    "combiner": "AND"
  }
}
```

- **BUY**:
  - Solo se aplica a assets **en seguimiento sin posición** (watchlist_only).
  - Se evalúan hasta dos condiciones:
    - Condición 1: Valoración 12m con operador (=, >, >=, <, <=) y valor.
    - Condición 2 (opcional): Rentabilidad Anual con operador y valor.
  - El usuario elige cómo combinarlas: **AND** (ambas) o **OR** (al menos una).
  - **Valores por defecto**:
    - Rentabilidad Anual `>= 60%`
    - Valoración 12m `> -12.5%`
    - Combiner `AND`.

- **SELL**:
  - Solo se aplica a assets **en cartera** (con posición).
  - Misma estructura de reglas (Valoración 12m + Rentabilidad Anual) y combiner AND/OR.
  - Por defecto viene sin condiciones activas (no dispara hasta que el usuario las configure).

**Prioridad**:
- Si se enciende BUY o SELL global, **prevalece** sobre INCREASE/HOLD/REDUCE y es lo que se muestra en la columna de Indicador operativa.

---

## ⚙️ CONFIGURACIÓN

### Umbral máximo peso en cartera
- Configurable por usuario (en pestaña watchlist o ajustes de perfil)
- Valor por defecto: 10%

### Rangos de Tier (según Valoración actual 12 meses %)
- Configurable por usuario
- Define qué rangos de valoración corresponden a Tier 1, 2, 3, 4, 5
- Ejemplo: Tier 5 si >= 50%, Tier 4 si 30-50%, etc.

### Cantidades absolutas por Tier
- Configurable por usuario (cantidades en EUR)
- Ejemplo: Tier 1 = 500€, Tier 2 = 1000€, Tier 3 = 2000€, Tier 4 = 5000€, Tier 5 = 10000€
- Se usan para comparar con cantidad invertida actual y calcular colores del Tier y "Cantidad a aumentar/reducir"

### Márgenes del Tier
- **±25%**: Rango verde (dentro del margen aceptable)
- **25% - 50%**: Rango amarillo (fuera pero moderado)
- **> 50%**: Rojo (fuera significativamente)

---

## 🔧 FUNCIONALIDADES

### 1. Botón "Actualizar Precios"
- Ubicado en la pestaña watchlist
- Actualiza precio actual + datos completos de Yahoo Finance
- Aplica a **todos** los assets en la tabla (cartera + watchlist)
- Obtiene la misma información que al pinchar en un asset en portfolio

### 2. Añadir Assets a Watchlist (Botón "+")

**Opción 1: Enlace Yahoo Finance**
- Usuario introduce URL de Yahoo Finance del asset
- Sistema extrae información del asset automáticamente
- Guarda información en AssetRegistry (`/portfolio/asset-registry`)
- Añade asset a watchlist

**Opción 2: Búsqueda en AssetRegistry**
- Búsqueda por nombre/ticker en AssetRegistry existente
- Autocomplete/filtro en tiempo real mientras escribe
- Seleccionar resultado → añadir a watchlist
- Si no existe → debe usar Opción 1 (enlace Yahoo)

### 3. Assets Seleccionables
- Click en cualquier asset de la tabla
- Muestra información detallada (igual que en pestaña portfolio)
- Modal o navegación a página de detalle
- La página de detalle incluye la **tab Informes** (HITO 2bis) con generación de informes Gemini, envío por correo y audio TTS

### 4. Peso en cartera
- Se calcula igual que en la pestaña portfolio
- Para assets en watchlist sin holdings: campo vacío
- Mismo cálculo para assets en cartera en ambas pestañas

---

## 📋 TAREAS DE IMPLEMENTACIÓN

**Backend:**
- [ ] Modelo Watchlist (relación many-to-many User-Asset)
  - Campos: user_id, asset_id, target_price, next_earnings_date, tier, per_ntm, ntm_dividend_yield, eps, cagr_revenue_yoy, operativa_indicator, rentabilidad_5yr, rentabilidad_anual, valoracion_12m, target_price_5yr, precio_actual
- [ ] Migración de BD
- [ ] Modelo WatchlistConfig (configuración de usuario)
  - Campos: user_id, max_weight_threshold, tier_ranges (JSON), tier_amounts (JSON)
- [ ] Servicio WatchlistService (CRUD)
- [ ] Servicio WatchlistMetricsService (cálculos de métricas)
- [ ] Endpoints API:
  - GET/POST /portfolio/watchlist
  - POST /portfolio/watchlist/add (con URL Yahoo o búsqueda)
  - POST /portfolio/watchlist/<id>/update
  - POST /portfolio/watchlist/<id>/delete
  - POST /portfolio/watchlist/update-prices (botón actualizar)
  - GET/POST /portfolio/watchlist/config (configuración de umbrales y Tier)

**Frontend:**
- [ ] Página `/portfolio/watchlist`
- [ ] Tabla única combinada (cartera + watchlist)
- [ ] 16 columnas con formato y colores
- [ ] Botón "Actualizar Precios"
- [ ] Botón "+" para añadir assets (modal con 2 opciones)
- [ ] Formulario de edición de métricas por asset
- [ ] Panel de configuración (umbrales y Tier)
- [ ] Assets seleccionables (click → detalle)
- [ ] Integración con AssetRegistry
- [ ] Integración con página de detalle de asset

---

### **HITO 3: Alertas de Diversificación** ❌ DESESTIMADO
**Prioridad**: —  
**Estado**: No se implementará (descoped)

Las alertas por asset (concentración individual) ya están en el HITO 2. Las alertas por sector/país no forman parte del alcance del sprint.

---

## 🛠️ TECNOLOGÍAS Y LIBRERÍAS

- **Gráficos**: Chart.js (ya implementado)
- **BD**: SQLite (actual)
- **Modelos**: Nuevo modelo Watchlist, expansión de métricas existentes

---

## 📊 MÉTRICAS DE ÉXITO

- ✅ Métricas de diversificación calculadas correctamente (HITO 1 - COMPLETADO)
- ✅ Visualizaciones claras y útiles para toma de decisiones (HITO 1 - COMPLETADO)
- ✅ Watchlist completo con tabla única combinada (cartera + watchlist)
- ✅ 17 columnas implementadas con métricas avanzadas
- ✅ Sistema de Tier automático funcionando (basado en valoración)
- ✅ Indicadores de operativa (BUY/SELL/HOLD) calculados automáticamente
- ✅ Columna "Cantidad a aumentar/reducir" funcionando
- ✅ Sistema de colores del Tier basado en cantidad invertida vs Tier
- ✅ Sistemas de colores funcionando (peso, valoración, fecha, etc.)
- ✅ Configuración de umbrales y Tier flexible y fácil de usar
- ✅ Integración completa con AssetRegistry
- ✅ Actualización masiva de precios funcionando
- ✅ Ordenación por fecha próximos resultados implementada (orden descendente por defecto)
- ✅ Header fijo (sticky) funcionando correctamente
- ✅ Informes de investigación con Gemini API (HITO 2bis): Deep Research, plantillas, envío por correo, audio TTS

---

## 📝 NOTAS Y CONSIDERACIONES

- **HITO 1 completado**: Las métricas de concentración y gráficos de distribución ya están implementados en el dashboard del portfolio (Sprint 4)
- **Reutilización**: Aprovechar servicios existentes (Yahoo Finance, AssetRegistry, cálculo de peso en cartera)
- **Tabla única**: Combina assets en cartera y watchlist en una sola vista ordenable
- **Peso en cartera**: Se calcula igual que en pestaña portfolio (mismo servicio/método)
- **Sistema de Tier**: Calculado automáticamente pero configurable (rangos y cantidades)
- **Fórmulas de cálculo**: Implementar validación cuando falten datos (mostrar "-" o vacío)
- **Performance**: Considerar cache para cálculos de métricas y actualización de precios
- **UX**: Colores intuitivos y claros, formularios fáciles de usar
- **Escalabilidad**: Watchlist debería soportar muchos assets sin problemas de rendimiento
- **Actualización masiva**: Optimizar llamadas a Yahoo Finance API (batch requests si es posible)
- **Validación de datos**: Manejar casos donde falten datos para cálculos (EPS, PER, CAGR, etc.)
- **HITO 2bis - Informes Gemini**: No estaba en la especificación original; implementado como extensión. Requiere GEMINI_API_KEY y MAIL_* para correo (Gmail: Contraseña de aplicación)
- **Header fijo (sticky)**: La tabla tendrá 17 columnas y muchos registros, por lo que el header debe quedarse fijo al hacer scroll vertical para mantener referencia de las columnas
  - Implementación: Usar `position: sticky; top: 0;` en el `<thead>` con `z-index` apropiado
  - Contenedor de la tabla con altura máxima y `overflow-y-auto` para scroll vertical
  - Mantener `overflow-x-auto` para scroll horizontal si es necesario

---

## 🔗 REFERENCIAS

- Métricas existentes: `app/services/metrics/basic_metrics.py`
- Gráficos de distribución: `app/templates/portfolio/dashboard.html`
- AssetRegistry: `app/models/asset.py`, `app/routes/portfolio.py`
- Sistema de alertas sector/país: Descoped; podría retomarse en sprint futuro si se desea

---

## 📋 CHECKLIST DE IMPLEMENTACIÓN

### HITO 1: Análisis de Concentración ✅ COMPLETADO
- [x] Cálculo de concentración por asset (porcentaje del portfolio)
- [x] Cálculo de concentración por sector/país/industria/broker/tipo
- [x] Visualización en dashboard del portfolio
- [x] Gráficos de distribución implementados (6 gráficos: País, Sector, Asset Top 10, Industria, Broker, Tipo)

### HITO 2: Watchlist con Indicadores de Operativa y Métricas Avanzadas

**Backend - Modelos y Base de Datos:**
- [ ] Modelo Watchlist (relación many-to-many User-Asset)
  - [ ] Campos: user_id, asset_id, next_earnings_date, per_ntm, ntm_dividend_yield, eps, cagr_revenue_yoy
  - [ ] Campos calculados/caché: operativa_indicator, tier, cantidad_aumentar_reducir, rentabilidad_5yr, rentabilidad_anual, valoracion_12m, target_price_5yr, precio_actual
- [ ] Modelo WatchlistConfig (configuración por usuario)
  - [ ] Campos: user_id, max_weight_threshold, tier_ranges (JSON), tier_amounts (JSON)
- [ ] Migración de BD (tablas watchlist y watchlist_config)

**Backend - Servicios:**
- [ ] WatchlistService (CRUD básico)
  - [ ] add_to_watchlist(user_id, asset_id, datos_manuales)
  - [ ] remove_from_watchlist(user_id, asset_id)
  - [ ] get_user_watchlist(user_id)
  - [ ] update_watchlist_asset(watchlist_id, datos)
- [ ] WatchlistMetricsService (cálculos)
  - [ ] calculate_target_price_5yr(eps, cagr, per)
  - [ ] calculate_valoracion_12m(per, dividend_yield, cagr)
  - [ ] calculate_rentabilidad_5yr(target_price, current_price, dividend_yield)
  - [ ] calculate_rentabilidad_anual(target_price, current_price, dividend_yield)
  - [ ] calculate_tier(valoracion_12m, tier_ranges_config)
  - [ ] calculate_cantidad_aumentar_reducir(current_value_eur, tier_amount) - nueva
  - [ ] calculate_operativa_indicator(cantidad_aumentar_reducir, tier_amount) - nueva (BUY/SELL/HOLD)
  - [ ] calculate_tier_color(current_value_eur, tier_amount) - nueva (verde/amarillo/rojo)
  - [ ] update_all_metrics(watchlist_id)
- [ ] WatchlistPriceUpdateService
  - [ ] update_prices_batch(user_id) - actualiza precios + datos Yahoo Finance

**Backend - Rutas API:**
- [ ] GET /portfolio/watchlist (página principal)
- [ ] POST /portfolio/watchlist/add (añadir asset)
  - [ ] Opción 1: Con URL Yahoo Finance (extrae info, guarda en AssetRegistry, añade a watchlist)
  - [ ] Opción 2: Con búsqueda en AssetRegistry (autocomplete)
- [ ] POST /portfolio/watchlist/<id>/update (editar métricas manuales)
- [ ] POST /portfolio/watchlist/<id>/delete (eliminar de watchlist)
- [ ] POST /portfolio/watchlist/update-prices (botón actualizar precios)
- [ ] GET /portfolio/watchlist/api/config (obtener configuración)
- [ ] POST /portfolio/watchlist/api/config (guardar configuración: umbrales y Tier)

**Frontend - Página Principal:**
- [ ] Página `/portfolio/watchlist`
- [ ] Tabla única combinada (cartera primero, luego watchlist)
- [ ] 17 columnas implementadas (ver orden arriba)
- [ ] **Header fijo (sticky header)**: El thead debe quedar fijo al hacer scroll vertical
  - [ ] Implementar `position: sticky; top: 0;` en el thead
  - [ ] Contenedor con altura máxima y `overflow-y-auto` para scroll vertical
  - [ ] Asegurar que el z-index del header sea superior al contenido
- [ ] Sistemas de colores implementados:
  - [ ] Peso en cartera (verde/amarillo/rojo según umbrales)
  - [ ] Fecha próximos resultados (verde/amarillo/rojo)
  - [ ] Valoración actual 12 meses (verde/amarillo/rojo)
  - [ ] Indicador operativa (verde/gris/rojo) - calculado automáticamente
  - [ ] Tier (verde/amarillo/rojo) - solo para assets en cartera
  - [ ] Precio actual (según target_price)
- [ ] Ordenación por columnas
- [ ] Assets seleccionables (click → detalle igual que portfolio)

**Frontend - Funcionalidades:**
- [ ] Botón "Actualizar Precios" (actualiza todos los assets)
- [ ] Botón "+" para añadir assets (modal con 2 opciones)
  - [ ] Opción 1: Input URL Yahoo Finance
  - [ ] Opción 2: Búsqueda autocomplete en AssetRegistry
- [ ] Formulario de edición de métricas manuales por asset
- [ ] Panel de configuración (umbrales y Tier)
  - [ ] Configuración umbral máximo peso en cartera
  - [ ] Configuración rangos de Tier (según Valoración actual 12 meses %)
  - [ ] Configuración cantidades absolutas por Tier

**Frontend - Integraciones:**
- [ ] Integración con AssetRegistry (búsqueda y creación)
- [ ] Integración con página de detalle de asset (misma info que portfolio)
- [ ] Integración con servicio de actualización de precios Yahoo Finance

### HITO 2bis: Informes de Investigación con Gemini API ✅ COMPLETADO
- [x] Generación de informes Deep Research (API Interactions, background)
- [x] Plantillas configurables (ReportTemplate: título, descripción, puntos)
- [x] Resumen "About the Company" (API rápida)
- [x] Envío por correo al email del usuario (Flask-Mail)
- [x] Audio resumen TTS con Gemini 2.5 (background, descarga WAV)
- [x] Tab Informes en Asset Detail con botones y estados

### HITO 3: Alertas de Diversificación ❌ DESESTIMADO
- (No implementado — descoped)

