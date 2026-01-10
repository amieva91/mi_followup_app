# 🎯 SPRINT 6 - DIVERSIFICACIÓN Y WATCHLIST
## 🚧 EN PROGRESO

**Versión**: v6.0.0  
**Inicio**: 24 Diciembre 2025  
**Duración estimada**: 2 semanas  
**Estado**: 🚧 IMPLEMENTACIÓN EN PROGRESO

**Última actualización**: 10 Enero 2026  
**Progreso**: ~70% completado

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
- 🚧 Pruebas de colores en progreso (Valoración 12M ✅, Indicador operativa ✅)

---

## 📊 ESTRUCTURA DE LA TABLA

**Tabla única combinada:**
- **Primero**: Assets en cartera (con peso e indicadores)
- **Después**: Assets en watchlist (sin holdings)
- **Ordenable** por cualquier columna
- **Assets seleccionables**: Click en asset muestra información detallada (igual que en portfolio)

---

## 📋 COLUMNAS DE LA TABLA (Orden Final)

| # | Columna | Tipo | Descripción | Notas |
|---|---------|------|-------------|-------|
| 1 | **Symbol** | - | Símbolo del asset | - |
| 2 | **Nombre** | - | Nombre del asset | - |
| 3 | **Fecha próximos resultados** | Manual | Fecha de próxima presentación de resultados | Con colores (verde/amarillo/rojo) |
| 4 | **Indicador operativa** | Calculado | BUY / SELL / HOLD | Automático basado en cantidad a aumentar/reducir vs Tier |
| 5 | **Tier (1-5)** | Calculado | Tier de inversión según valoración | Basado en Valoración actual 12 meses (%). Con colores para assets en cartera |
| 6 | **Cantidad a aumentar/reducir** | Calculado | Diferencia vs cantidad del Tier (EUR) | Negativo = vender, Positivo = comprar. Solo para assets en cartera |
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

**Umbral máximo configurable** (ej: 10%):
- 🟢 **Verde**: peso < (umbral + 10%) = < 11%
- 🟡 **Amarillo**: peso >= (umbral + 10%) y < (umbral + 25%) = >= 11% y < 12.5%
- 🔴 **Rojo**: peso >= (umbral + 25%) = >= 12.5%

**Ejemplo con umbral = 10%**:
- Verde: 0% - 10.99%
- Amarillo: 11% - 12.49%
- Rojo: >= 12.5%

### 2. Fecha próximos resultados

- 🟢 **Verde**: Fecha no ha pasado aún
- 🟡 **Amarillo**: Fecha pasada pero <= 15 días
- 🔴 **Rojo**: Fecha pasada > 15 días

### 3. Valoración actual 12 meses (%)

- 🟢 **Verde**: >= 10% (alcista/barata)
- 🟡 **Amarillo**: 0% a < 10%
- 🔴 **Rojo**: < 0% (bajista/cara)

### 4. Indicador operativa

- 🟢 **BUY** → Verde (cantidad a aumentar positiva)
- ⚪ **HOLD** → Gris (dentro del margen del Tier)
- 🔴 **SELL** → Rojo (cantidad a reducir negativa)

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
Target Price = (EPS * (1 + CAGR Revenue YoY%)^5) * PER
```

### 2. Valoración actual 12 meses (%)
```
Valoración actual = ((PER + NTM Dividend Yield%) / CAGR Revenue YoY%) * 100
```
- Si resultado >= 10%: Alcista/barata (verde)
- Si resultado 0-10%: Neutro (amarillo)
- Si resultado < 0%: Bajista/cara (rojo)

**Ejemplos**:
- PER=10, Dividend Yield=2%, CAGR=20% → (10+2)/20 * 100 = 60% (verde)
- PER=10, Dividend Yield=2%, CAGR=10% → (10+2)/10 * 100 = 120% (rojo)

### 3. Rentabilidad a 5 años / Anual
- Basada en Target Price (5 yr) calculado
- Incluye NTM Dividend Yield (dividendo constante anual durante 5 años)

### 4. Tier (1-5)
- **Calculado automáticamente** basado en Valoración actual 12 meses (%)
- El usuario configura los rangos que determinan cada Tier
- Rangos configurables (ej: Tier 5 si >= 50%, Tier 4 si 30-50%, etc.)

### 5. Cantidad a aumentar/reducir (EUR)
```
Cantidad a aumentar/reducir = Cantidad_invertida_actual - Cantidad_del_Tier
```
- **Negativo**: Hay que vender (SELL) - por encima del Tier
- **Cero o pequeño (±25% del Tier)**: Dentro del margen (HOLD)
- **Positivo**: Hay que comprar (BUY) - por debajo del Tier

**Ejemplo**:
- Tier 1 = 2500€, invertido = 5000€ → -2500€ (SELL, rojo)
- Tier 1 = 2500€, invertido = 2600€ → -100€ (HOLD, gris - dentro del ±25%)
- Tier 1 = 2500€, invertido = 2000€ → +500€ (BUY, verde)

### 6. Indicador operativa (BUY/SELL/HOLD)
- **Calculado automáticamente** basado en "Cantidad a aumentar/reducir" vs Tier
- **BUY**: Cantidad a aumentar/reducir > 0 (positivo) → Verde
- **HOLD**: Cantidad dentro del margen (±25% del Tier) → Gris
- **SELL**: Cantidad a aumentar/reducir < 0 (negativo, por encima del Tier) → Rojo

**Lógica**:
- Si `|cantidad_aumentar_reducir| <= Tier_amount * 0.25` → HOLD
- Si `cantidad_aumentar_reducir > Tier_amount * 0.25` → BUY
- Si `cantidad_aumentar_reducir < -(Tier_amount * 0.25)` → SELL

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

### **HITO 3: Alertas de Diversificación**
**Prioridad**: 🟡 MEDIA  
**Duración estimada**: 2-3 días

**Estado**: ⚠️ REVISAR (funcionalidad parcialmente movida al HITO 2)

**Objetivos**:
- Sistema de alertas configurables para diversificación por sector/país
- Alertas cuando el portfolio está demasiado concentrado en sectores/países
- Recomendaciones de diversificación
- Configuración de umbrales personalizados

**Tareas**:
- [ ] Sistema de configuración de alertas por usuario (para sector/país)
- [ ] Alertas de concentración por sector (ej: > 30% en un sector)
- [ ] Alertas de concentración por país (ej: > 40% en un país)
- [ ] Panel de configuración de alertas (sector/país)
- [ ] Notificaciones en dashboard cuando se activan alertas

**Nota**: Las alertas por asset (concentración individual) se implementan en el HITO 2 como parte de los indicadores de operativa.

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
- **Header fijo (sticky)**: La tabla tendrá 17 columnas y muchos registros, por lo que el header debe quedarse fijo al hacer scroll vertical para mantener referencia de las columnas
  - Implementación: Usar `position: sticky; top: 0;` en el `<thead>` con `z-index` apropiado
  - Contenedor de la tabla con altura máxima y `overflow-y-auto` para scroll vertical
  - Mantener `overflow-x-auto` para scroll horizontal si es necesario

---

## 🔗 REFERENCIAS

- Métricas existentes: `app/services/metrics/basic_metrics.py`
- Gráficos de distribución: `app/templates/portfolio/dashboard.html`
- AssetRegistry: `app/models/asset.py`, `app/routes/portfolio.py`
- Sistema de alertas: Considerar integración futura con notificaciones (Sprint 7)

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

### HITO 3: Alertas de Diversificación (Sector/País)
- [ ] Modelo de configuración de alertas por sector/país
- [ ] Sistema de evaluación de alertas (sector/país)
- [ ] Alertas de concentración por sector (ej: > 30%)
- [ ] Alertas de concentración por país (ej: > 40%)
- [ ] Visualización de alertas activas en dashboard
- [ ] Panel de configuración de umbrales (sector/país)
- [ ] Logging de alertas activadas

