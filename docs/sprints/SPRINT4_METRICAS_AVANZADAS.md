# 📊 SPRINT 4 - MÉTRICAS AVANZADAS Y ANÁLISIS
## 🚧 EN PROGRESO

**Versión**: v4.3.0 (HITO 1, HITO 2, Refinements, UX Avanzadas y HITO 3 completados)  
**Inicio**: 6 Noviembre 2025  
**Duración estimada**: 3 semanas  
**Estado**: ✅ HITO 1 COMPLETADO (8 Nov) | ✅ HITO 2 COMPLETADO (9 Nov) | ✅ Refinements COMPLETADO (10 Nov) | ✅ UX Avanzadas COMPLETADO (10 Nov) | ✅ HITO 3 COMPLETADO (12 Nov) | ✅ HITO 4 COMPLETADO (23 Dic) - Distribución del Portfolio + Comparación con Benchmarks

---

## 🎯 OBJETIVOS DEL SPRINT

Construir un sistema completo de métricas y análisis financiero sobre el foundation sólido del Sprint 3:

1. ✅ **Foundation**: Portfolio completo con precios en tiempo real
2. 🎯 **Objetivo Sprint 4**: Métricas, gráficos, análisis, insights automáticos
3. 🔮 **Resultado esperado**: Dashboard profesional con análisis de performance completo

---

## 📋 HITOS PLANIFICADOS

### ✅ **HITO 1: Métricas Básicas** (COMPLETADO - 8 Nov 2025)
**Prioridad**: 🔴 ALTA  
**Duración real**: 2 días (6-8 Nov)

**Métricas Implementadas**:

1. **P&L Realizado vs No Realizado**
   - P&L Realizado: Ganancias/pérdidas de posiciones cerradas
   - P&L No Realizado: Ganancias/pérdidas de posiciones abiertas (ya implementado)
   - Total P&L: Suma de ambos

2. **ROI (Return on Investment)**
   ```
   ROI = (Valor Actual + Retiradas - Depósitos) / Depósitos × 100
   ```
   - Ejemplo: Depósitos 100K EUR, Valor Actual 115K, Retiradas 5K
   - ROI = (115K + 5K - 100K) / 100K × 100 = 20%

3. **Leverage (Apalancamiento)**
   ```
   Capital Neto Invertido = Depósitos - Retiradas
   Leverage % = (Valor Portfolio - Capital Neto) / Capital Neto × 100
   ```
   - Ejemplo: Depósitos 100K, Retiradas 10K, Valor 102.86K
   - Capital Neto: 90K
   - Leverage: (102.86K - 90K) / 90K × 100 = 14.3%
   - Interpretación: Estás usando 12.86K de ganancias

4. **Peso % por Posición**
   ```
   Peso % = (Valor Posición / Valor Total Portfolio) × 100
   ```
   - Identifica concentración de riesgo
   - Alerta si >10% en un solo asset

**Archivo**: `app/services/metrics/basic_metrics.py`

**UI**:
- Cards en dashboard con iconos y colores
- Tooltip con explicación de cada métrica
- Cambio % respecto a período anterior

**✅ RESULTADOS COMPLETADOS**:

1. **8 Métricas funcionando perfectamente**:
   - ✅ P&L Realizado (reescrito con FIFO - antes 5% arbitrario)
   - ✅ P&L No Realizado
   - ✅ P&L Total (con desglose completo)
   - ✅ ROI (con desglose de cálculo)
   - ✅ Leverage/Dinero Prestado (incluye P&L Realizado + No Realizado)
   - ✅ Valor Total Cartera (con desglose)
   - ✅ Valor Total Cuenta de Inversión (incluye todos los componentes)
   - ✅ Peso % por Posición

2. **Dashboard reorganizado**:
   - ✅ Métricas Globales primero (P&L Total, ROI, Valor Cuenta)
   - ✅ Métricas de Portfolio después (Valor Cartera, Coste, P&L No Realizado, etc)

3. **UX mejorada**:
   - ✅ Tooltips explicativos en TODAS las métricas
   - ✅ Desgloses detallados en todos los indicadores
   - ✅ Página P&L by Asset con búsqueda + ordenación + contador dividendos

4. **Ordenación numérica universal**:
   - ✅ Dashboard holdings (JavaScript, formato europeo)
   - ✅ Holdings page (JavaScript, formato europeo)
   - ✅ PL by Asset (JavaScript, formato europeo)
   - ✅ Transactions (JavaScript con fecha, texto, números)

5. **Fixes críticos**:
   - ✅ P&L Realizado con FIFOCalculator
   - ✅ P&L Total con fórmula correcta
   - ✅ Leverage con lógica de cash corregida
   - ✅ Brokers en holdings unificadas
   - ✅ Holdings sin límite (antes 15, ahora todas)
   - ✅ P&L pre-calculado en backend

**Archivos modificados**:
- `app/services/metrics/basic_metrics.py` - 5 métodos corregidos/ampliados
- `app/routes/portfolio.py` - cost_eur y pl_eur precalculados
- `app/templates/portfolio/dashboard.html` - reorganización + desgloses
- `app/templates/portfolio/pl_by_asset.html` - reordenación columnas
- `app/templates/portfolio/holdings.html` - fix sorting numérico
- `app/templates/portfolio/transactions.html` - sorting JavaScript completo
- `app/services/currency_service.py` - logs debug eliminados

---

### ✅ **HITO 2: Modified Dietz Method** (COMPLETADO - 9 Nov 2025)
**Prioridad**: 🔴 ALTA  
**Duración real**: 1 día (9 Nov)

**Objetivo**: Implementar el método Modified Dietz para calcular la rentabilidad del portfolio considerando el tiempo de permanencia de los cash flows.

**¿Por qué Modified Dietz?**
- ✅ **Estándar GIPS** (Global Investment Performance Standards)
- ✅ **NO requiere precios históricos** (solo valor inicial y final)
- ✅ **Pondera cash flows por tiempo** (elimina efecto de timing de deposits/withdrawals)
- ✅ **Comparable con benchmarks** y otros portfolios
- ✅ **Estándar de la industria** financiera

**Fórmula Modified Dietz**:
```
R = (VF - VI - CF) / (VI + Σ(CF_i × W_i))

Donde:
  R  = Rentabilidad del período
  VF = Valor Final del portfolio
  VI = Valor Inicial del portfolio
  CF = Suma de cash flows externos (deposits/withdrawals)
  W_i = Peso temporal del cash flow i = (D - d_i) / D
  D  = Días totales del período
  d_i = Días desde el cash flow i hasta el final
```

**Cash Flows Externos**:
- ✅ DEPOSIT (depósitos del usuario)
- ✅ WITHDRAWAL (retiradas del usuario)
- ❌ DIVIDEND (son ingresos internos del portfolio)
- ❌ FEE (son gastos internos del portfolio)

**Implementación Completada**:

1. **Portfolio Valuation Service** (`app/services/metrics/portfolio_valuation.py`):
   - `get_value_at_date()`: Valoración del portfolio en cualquier fecha histórica
     - Reconstruye posiciones usando transacciones
     - Calcula valor con precios actuales o históricos
     - Soporte para múltiples assets y currencies
   - `get_user_money_at_date()`: Dinero real del usuario (sin apalancamiento)
     - Considera deposits, withdrawals, P&L, dividends, fees
     - Usa `FIFOCalculator` para calcular cost basis histórico
   - `get_cash_flows()`: Lista de cash flows externos (DEPOSIT/WITHDRAWAL) ordenados

2. **Modified Dietz Calculator** (`app/services/metrics/modified_dietz.py`):
   - `calculate_return()`: Rentabilidad de un período específico
     - Aplica fórmula Modified Dietz
     - Calcula peso temporal de cada cash flow
     - Retorna rentabilidad % y ganancia absoluta
   - `calculate_annualized_return()`: Rentabilidad anualizada
     - Fórmula: `((1 + R_total)^(365/días)) - 1`
     - Permite comparar períodos de diferentes duraciones
   - `calculate_ytd_return()`: Rentabilidad año actual (YTD)
     - Período: 1 enero del año actual hasta hoy
     - Métrica clave para evaluar performance del año
   - `get_all_returns()`: Wrapper para dashboard
     - Retorna las 3 métricas en un solo diccionario
     - Incluye: Total, Anualizada, YTD

3. **Nueva Card en Dashboard**: 💎 Rentabilidad (Modified Dietz)
   - **Rentabilidad Anualizada**: Métrica principal (mostrada grande y destacada)
     - Años de inversión (calculados automáticamente)
   - **Rentabilidad Total**: Rentabilidad acumulada desde el inicio
   - **Rentabilidad YTD**: Rentabilidad en el año actual
   - **Ganancia Absoluta**: Ganancia total en EUR
   - **Días de inversión**: Número de días desde la primera transacción
   - **Tooltip explicativo**: Descripción del método y ventajas

**Integración**:
- ✅ Actualizado `app/services/metrics/basic_metrics.py`:
  - Import de `ModifiedDietzCalculator`
  - Llamada a `ModifiedDietzCalculator.get_all_returns(user_id)` en `get_all_metrics()`
  - Retorna resultados en key `modified_dietz`
- ✅ Actualizado `app/templates/portfolio/dashboard.html`:
  - Nueva card morada en sección "Métricas Globales e Históricas"
  - Color dinámico (morado/rojo) según rentabilidad positiva/negativa
  - Desglose detallado de todas las métricas
  - Tooltip con explicación del método

**Validación Matemática**:
```
Portfolio de prueba:
  - Ganancia Modified Dietz: 52.472,87 EUR
  - P&L Total del sistema:   52.562,87 EUR
  - Error absoluto:             90,00 EUR
  - Error relativo:              0,17%  ✅ VALIDADO
```

**Métricas del Usuario**:
```
💎 Rentabilidad (Modified Dietz):
  - Anualizada:        +16,28%  (7.85 años)
  - Total:            +226,94%
  - YTD 2025:          +17,86%
  - Ganancia:       +52.472,87 EUR
  - Días inversión:      2.867 días
```

**Comparación ROI vs Modified Dietz**:
```
ROI Simple:          +141%  (no considera timing de cash flows)
Modified Dietz:      +227%  (pondera cash flows por tiempo)
Diferencia:           +86%  (refleja mejor timing de inversión)
```

**Ventajas sobre ROI Simple**:
- ✅ Elimina sesgo de timing (deposits tardíos no penalizan rentabilidad)
- ✅ Comparable con benchmarks (S&P 500, NASDAQ, etc.)
- ✅ Estándar de la industria (usado por gestoras profesionales)
- ✅ Más preciso para evaluación de estrategia de inversión

**Archivos Modificados**:
- ✅ `app/services/metrics/portfolio_valuation.py` (NUEVO)
- ✅ `app/services/metrics/modified_dietz.py` (NUEVO)
- ✅ `app/services/metrics/basic_metrics.py` (ACTUALIZADO)
- ✅ `app/templates/portfolio/dashboard.html` (ACTUALIZADO)

**Fixes Aplicados**:
- ✅ Import corregido: `fifo_calculator` (no `fifo`)
- ✅ Parámetros `add_buy`: `total_cost` (no `cost` + `currency`)
- ✅ Método FIFO: `get_current_position()` (no `get_current_quantity`)
- ✅ Cash flows: Excluidos `DIVIDEND` (son ingresos internos)

**Deploy**:
- ✅ Committed: `feat(sprint4-hito2): Modified Dietz Method completado v4.0.0-beta`
- ✅ Pushed to GitHub: `main` branch
- ✅ Deployed to Production: https://followup.fit/
- ✅ Validado en producción: Métricas funcionando correctamente

---

### ✅ **Refinements: Performance & UX** (COMPLETADO - 10 Nov 2025)
**Prioridad**: 🟡 MEDIA  
**Duración real**: 1 día (10 Nov)

**Objetivo**: Mejorar performance del dashboard y corregir issues críticos de UX.

**1. Cache de Métricas** (Mejora de Performance):
- **Nueva tabla**: `MetricsCache` con TTL de 24 horas
  ```python
  class MetricsCache(db.Model):
      id = db.Column(db.Integer, primary_key=True)
      user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
      cached_data = db.Column(db.JSON)
      created_at = db.Column(db.DateTime, default=datetime.utcnow)
      expires_at = db.Column(db.DateTime)  # TTL: 24 horas
  ```

- **Nuevo servicio**: `MetricsCacheService` (`app/services/metrics/cache.py`)
  - `get(user_id)`: Obtiene métricas del cache si no expiró
  - `set(user_id, metrics_data)`: Guarda métricas en cache
  - `invalidate(user_id)`: Borra cache manualmente

- **Invalidación automática**:
  - Al crear/editar/eliminar transacción
  - Al actualizar precios
  - Al importar CSV
  - Al hacer click en botón "♻️ Recalcular"

- **Badge visual**: "⚡ Cache" en dashboard cuando se usa cache

- **Mejora de rendimiento**: Dashboard 2-3s → 0.3s (reducción de 85%)

**2. Fixes Críticos**:
- ✅ **CSRF Token en "Actualizar Precios"**:
  - Error 400 corregido
  - Añadido `<meta name="csrf-token" content="{{ csrf_token() }}">` en `layout.html`
  - Fetch modificado para enviar CSRF token en FormData
  
- ✅ **Funcionalidad "Eliminar Transacciones"**:
  - Botón "🗑️ Eliminar" añadido en tabla de transacciones
  - Modal de confirmación JavaScript
  - Recalculo automático de holdings tras eliminar
  - Invalidación automática de cache tras eliminar
  - Mensaje de confirmación: "✅ Transacción de [ASSET] eliminada correctamente"

**3. UX Mejorada**:
- ✅ **Campo integrado para Yahoo URL** (reemplaza prompt nativo):
  - Input HTML con placeholder
  - Botón "Enriquecer" al lado del campo
  - Validación: error si campo vacío
  - Limpieza automática tras éxito
  - Diseño consistente con el sistema

**Archivos Modificados**:
- ✅ `app/models/metrics_cache.py` (NUEVO)
- ✅ `app/services/metrics/cache.py` (NUEVO)
- ✅ `app/models/__init__.py` (import MetricsCache)
- ✅ `app/routes/portfolio.py`:
  - `dashboard()`: integración con cache
  - `transaction_new()`, `transaction_edit()`: invalidación de cache
  - `import_csv_process()`: invalidación de cache
  - `update_prices()`: invalidación de cache
  - `transaction_delete()`: nueva ruta para eliminar (NUEVO)
  - `invalidate_cache()`: nueva ruta manual (NUEVO)
- ✅ `app/templates/base/layout.html` (meta CSRF token)
- ✅ `app/templates/portfolio/dashboard.html`:
  - Botón "♻️ Recalcular"
  - Badge "⚡ Cache"
  - CSRF token en fetch de precios
- ✅ `app/templates/portfolio/transaction_form.html`:
  - Campo input para Yahoo URL
  - JavaScript actualizado
- ✅ `app/templates/portfolio/transactions.html`:
  - Botón "🗑️ Eliminar"
  - Función JavaScript `confirmDelete()`

**Migración**:
```bash
flask db migrate -m "Add MetricsCache table for performance optimization"
flask db upgrade
```

**Deploy**:
- ✅ Committed: `Sprint 4 - Refinements: Cache de métricas + Fixes críticos`
- ✅ Pushed to GitHub: `main` branch
- ✅ Deployed to Production: https://followup.fit/
- ✅ Validado en producción: Cache y fixes funcionando correctamente

---

### ✅ **UX Avanzadas: Transacciones Manuales** (COMPLETADO - 10 Nov 2025)
**Prioridad**: 🟡 MEDIA  
**Duración real**: 1 día (10 Nov)

**Objetivo**: Implementar funcionalidades UX avanzadas para facilitar el registro manual de transacciones BUY/SELL.

**Funcionalidades Implementadas**:

**1. Auto-selección en SELL**:
- ✅ Dropdown inteligente para seleccionar activos del portfolio
- ✅ Opción "-- Todas las cuentas --" por defecto (muestra todos los assets)
- ✅ Filtro opcional por cuenta específica (IBKR, DeGiro, Manual)
- ✅ Display: `[Broker] Symbol - Name (Quantity)`
- ✅ Auto-completado completo al seleccionar: Symbol, ISIN, Currency, Name, Asset Type, Exchange, MIC, Yahoo Suffix
- ✅ **Botón "Máximo"**: Auto-completa cantidad disponible para vender
- ✅ Actualización automática del campo "Cuenta" al broker del asset seleccionado

**2. Autocompletado en BUY**:
- ✅ Búsqueda en tiempo real desde `AssetRegistry` global
- ✅ Sugerencias al escribir en Symbol o ISIN
- ✅ Auto-fill completo de todos los campos
- ✅ Experiencia sin interrupciones (no bloquea escritura)
- ✅ Alimentado desde base de datos global compartida

**3. Venta por Quiebra (Bankruptcy)**:
- ✅ Soporte completo para precio = 0€
- ✅ Validación: `InputRequired()` + `NumberRange(min=0)`
- ✅ Eliminación automática de holdings con quantity = 0
- ✅ Integración correcta con `FIFOCalculator`
- ✅ Cálculo correcto de P&L: `realized_pl = total_sale - cost_basis`

**4. Botones de Enriquecimiento Inteligentes**:
- ✅ **"Enriquecer con OpenFIGI"**: Deshabilitado en NEW (tooltip), habilitado en EDIT
- ✅ **"Desde URL de Yahoo"**: Habilitado en NEW y EDIT
- ✅ Extrae symbol + yahoo_suffix desde URL
- ✅ Actualiza `AssetRegistry` y sincroniza con `Asset`

**5. Redirección Mejorada**:
- ✅ BUY/SELL → redirige a `/portfolio/holdings` (antes: `/portfolio/transactions`)
- ✅ Feedback visual instantáneo del cambio en el portfolio

**6. Fixes Críticos**:
- ✅ `KeyError: 'avg_price'` → `'average_buy_price'` en FIFO
- ✅ Modal de precios: `data.updated` → `data.success`
- ✅ Holdings API: Query optimizada con `account_id.in_()`
- ✅ `AttributeError: 'avg_buy_price'` → `average_buy_price` correcto

**Archivos Modificados**:
- ✅ `app/routes/portfolio.py`: Lógica de transacciones y API endpoints
- ✅ `app/forms/portfolio_forms.py`: Validadores (`InputRequired`, `NumberRange(min=0)`)
- ✅ `app/templates/portfolio/transaction_form.html`: UI del formulario con dropdowns
- ✅ `app/templates/portfolio/dashboard.html`: Modal de actualización de precios

**Deploy**:
- ✅ Committed: `Fix: Corregir transacciones manuales y modal de actualización de precios`
- ✅ Pushed to GitHub: `main` branch
- ✅ Deployed to Production: https://followup.fit/
- ✅ Validado en producción: Todas las funcionalidades funcionando correctamente

---

### ✅ **HITO 3: Gráficos de Evolución** (COMPLETADO - 12 Nov 2025)
**Prioridad**: 🟡 MEDIA  
**Duración real**: 3 días (10-12 Nov)

**✅ FASE 1: Gráficos Básicos de Evolución**:

1. **Evolución del Valor Real de la Cuenta**
   - Valor de las posiciones vs Capital Invertido Neto
   - Último punto con precios reales actuales

2. **Rentabilidad Acumulada (Modified Dietz)**
   - Rentabilidad % calculada según método Modified Dietz (estándar GIPS)
   - Evolución histórica mensual

**✅ FASE 2: Gráficos Adicionales (COMPLETADO)**:

3. **Apalancamiento/Cash Histórico**
   - Dinero prestado por el broker (positivo) o cash disponible sin invertir (negativo)
   - Verde para cash positivo, rojo para apalancamiento negativo
   - Función: `createLeverageChart()` en `charts.js`

4. **Flujos de Caja Acumulados**
   - Suma neta de depósitos y retiradas a lo largo del tiempo
   - Capital Invertido Neto acumulado
   - Función: `createCashFlowsChart()` en `charts.js`

5. **P&L Total Acumulado**
   - Ganancias/Pérdidas totales históricas (Realizado + No Realizado + Dividendos - Comisiones)
   - Verde para ganancias, rojo para pérdidas
   - Función: `createPLChart()` en `charts.js`

**Nota**: La comparación con Benchmarks se implementó como parte del HITO 4.

**Librería**: Chart.js 4.0 (ligero, responsive, sin dependencias)

**Archivos**:
- `app/static/js/charts.js` - Configuración de Chart.js
- `app/templates/portfolio/charts.html` - Página de gráficos
- `app/routes/portfolio.py` - Endpoint `/portfolio/charts` con data JSON

**Interactividad**:
- Hover muestra valores exactos
- Click en leyenda oculta/muestra serie
- Selector de rango temporal (1M, 3M, 6M, 1Y, Todo)

---

### ✅ **HITO 4: Distribución del Portfolio + Comparación con Benchmarks** (COMPLETADO - 23 Dic 2025)
**Prioridad**: 🟡 MEDIA  
**Duración real**: 2 días

**✅ PARTE 1: Gráficos de Distribución (Pie Charts) - COMPLETADO**:

Los gráficos se muestran en el dashboard principal, en la sección "📊 Distribución del Portfolio":

1. ✅ **Por País** (ya existía, se mantiene)
   - Distribución geográfica del portfolio
   - Obtenido del campo `country` de los assets

2. ✅ **Por Sector** (ya existía, se mantiene)
   - Technology, Healthcare, Finance, etc.
   - Obtenido de Yahoo Finance

3. ✅ **Por Asset (Top 10 + Otros)** (NUEVO)
   - Top 10 assets por valor
   - Resto agrupado como "Otros"
   - Porcentaje y valor absoluto en tooltips

4. ✅ **Por Industria** (NUEVO)
   - Más granular que sector
   - Software, Biotech, Banks, etc.
   - Obtenido del campo `industry` de los assets

5. ✅ **Por Broker** (NUEVO)
   - IBKR, DeGiro, Manual, etc.
   - Útil para identificar concentración por broker
   - Calculado desde holdings → accounts → broker

6. ✅ **Por Tipo de Asset** (NUEVO)
   - Stock (incluye ADR agrupado), ETF, Bond, Crypto
   - ADR se agrupa automáticamente como Stock
   - Obtenido del campo `asset_type` de los assets

**❌ NO IMPLEMENTADO**: Por Moneda (excluido por decisión del usuario)

**✅ PARTE 2: Comparación con Benchmarks - COMPLETADO**:

1. ✅ **Comparación en Dashboard**:
   - Recuadro expandido a ancho completo (fuera del grid de 4 columnas)
   - Muestra rentabilidad anualizada del portfolio
   - Comparación horizontal con 4 índices:
     - S&P 500
     - NASDAQ 100 (corregido de ^IXIC a ^NDX)
     - MSCI World
     - EuroStoxx 50
   - Cada índice muestra su rentabilidad total acumulada y diferencia vs portfolio
   - Colores: verde (mejor que portfolio), rojo (peor que portfolio)
   - Link a gráfico completo en `/portfolio/performance`

2. ✅ **Gráfico Comparativo en Performance Page**:
   - Gráfico normalizado a 100 desde fecha inicial
   - Líneas para portfolio y todos los benchmarks
   - Datos mensuales desde primera inversión

3. ✅ **Tabla Comparativa Anual**:
   - Rentabilidades año a año del portfolio vs benchmarks
   - Diferencia porcentual en cada celda
   - Fila "Total" con rentabilidades totales acumuladas
   - Diferencias calculadas usando totales acumulados (consistente con dashboard)

4. ✅ **Corrección de Discrepancias**:
   - Dashboard y tabla "Total" ahora usan la misma base de cálculo (totales acumulados)
   - Rentabilidad anualizada solo se muestra como título principal del portfolio

**Archivos Modificados**:
- ✅ `app/routes/portfolio.py`: Cálculos de distribución (asset, industry, broker, tipo)
- ✅ `app/templates/portfolio/dashboard.html`: HTML de gráficos + JavaScript Chart.js
- ✅ `app/services/metrics/benchmark_comparison.py`: Corrección para usar totales acumulados en diferencias
- ✅ `app/static/js/charts.js`: Renderizado de gráfico y tabla de benchmarks
- ✅ `app/templates/portfolio/performance.html`: Tabla comparativa anual

**UI**:
- ✅ Grid responsive 2 columnas (1 en móvil, 2 en desktop)
- ✅ 6 gráficos en total (País, Sector, Asset, Industria, Broker, Tipo)
- ✅ Cada pie chart con leyenda y tooltips informativos
- ✅ Chart.js 4.0 con colores consistentes
- ✅ Recuadro de benchmarks expandido horizontalmente ocupando todo el ancho

---

## 🗄️ ESTRUCTURA DE BASE DE DATOS

### **Nuevas Tablas (si necesarias)**:

**`portfolio_snapshots`** (para cálculos históricos):
```python
class PortfolioSnapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    snapshot_date = db.Column(db.Date, nullable=False)
    total_value = db.Column(db.Numeric(15, 2))
    total_cost = db.Column(db.Numeric(15, 2))
    cash_balance = db.Column(db.Numeric(15, 2))
    num_positions = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**`benchmark_prices`** (para comparaciones):
```python
class BenchmarkPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10))  # ^GSPC (S&P500), ^DJI, etc.
    date = db.Column(db.Date, nullable=False)
    close_price = db.Column(db.Numeric(10, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### **Extensión de Tablas Existentes**:

**`portfolio_metrics`** (añadir columnas):
```python
# Columnas nuevas:
twr = db.Column(db.Float)           # Time-Weighted Return
irr = db.Column(db.Float)           # Internal Rate of Return
sharpe_ratio = db.Column(db.Float)
max_drawdown = db.Column(db.Float)
volatility = db.Column(db.Float)
leverage_pct = db.Column(db.Float)
```

---

## 🎨 DISEÑO UI/UX

### **Paleta de Colores para Métricas**:
```
Positivo (ganancias):  bg-green-100, text-green-800, border-green-300
Negativo (pérdidas):   bg-red-100, text-red-800, border-red-300
Neutral (info):        bg-blue-100, text-blue-800, border-blue-300
Alerta (riesgo):       bg-orange-100, text-orange-800, border-orange-300
```

### **Iconos por Métrica**:
```
ROI:          📈 (trending up)
TWR/IRR:      🎯 (target)
Sharpe:       ⚖️ (balance)
Drawdown:     📉 (trending down)
Volatilidad:  🌊 (wave)
Leverage:     🔧 (leverage tool)
Peso %:       🥧 (pie)
```

### **Responsive Design**:
- Desktop: Grid 4 columnas para cards
- Tablet: Grid 2 columnas
- Mobile: Stack vertical, gráficos scrollables horizontalmente

---

## 📊 FUENTES DE DATOS

### **Datos Internos** (ya disponibles):
✅ Transactions (BUY/SELL/DIVIDEND/FEE)
✅ CashFlows (DEPOSIT/WITHDRAWAL)
✅ PortfolioHoldings (posiciones actuales)
✅ PriceHistory (histórico de precios)
✅ Assets (sector, industry, currency)

### **Datos Externos** (a obtener):
🔲 Benchmarks históricos (Yahoo Finance: ^GSPC, ^DJI, ^ACWI)
🔲 Risk-Free Rate (US Treasury 10Y, API alternativa o hardcoded)

---

## 🧪 CASOS DE PRUEBA

### **Escenarios de Testing**:

1. **Portfolio Simple**
   - 1 asset, 1 compra, sin ventas
   - ROI = P&L No Realizado / Depósito

2. **Portfolio con Ventas**
   - 2 assets, compras + ventas
   - P&L Realizado calculado correctamente

3. **Portfolio con Cash Flows**
   - Deposits escalonados en el tiempo
   - TWR ≠ IRR (TWR ignora timing)

4. **Portfolio con Pérdidas**
   - Asset con P&L negativo
   - Max Drawdown detectado

5. **Portfolio Multi-Divisa**
   - Holdings en USD, GBP, HKD
   - Conversión a EUR correcta

---

## 🚀 PLAN DE IMPLEMENTACIÓN

### **Semana 1** (6-10 Nov):
- [x] Planificación y diseño (este documento)
- [ ] HITO 1: Métricas Básicas (ROI, Leverage, Peso %)
- [ ] UI: Cards en dashboard
- [ ] Testing con datos reales

### **Semana 2** (11-17 Nov):
- [ ] HITO 2: Métricas Avanzadas (TWR, IRR, Sharpe, Drawdown, Volatilidad)
- [ ] HITO 3: Gráficos de Evolución (Chart.js)
- [ ] Testing de cálculos matemáticos

### **Semana 3** (18-24 Nov):
- [x] HITO 4: Gráficos de Distribución (Pie charts) ✅ COMPLETADO (23 Dic)
- [x] HITO 4: Comparación con Benchmarks ✅ COMPLETADO (23 Dic)
- [x] Testing E2E, deployment a producción ✅ COMPLETADO

---

## 📚 REFERENCIAS Y RECURSOS

### **Fórmulas Financieras**:
- [Investopedia - Time-Weighted Return](https://www.investopedia.com/terms/t/time-weightedreturnofthecapital.asp)
- [Investopedia - IRR](https://www.investopedia.com/terms/i/irr.asp)
- [Investopedia - Sharpe Ratio](https://www.investopedia.com/terms/s/sharperatio.asp)
- [Investopedia - Max Drawdown](https://www.investopedia.com/terms/m/maximum-drawdown-mdd.asp)

### **Librerías**:
- [Chart.js Documentation](https://www.chartjs.org/docs/latest/)
- [numpy-financial](https://numpy.org/numpy-financial/latest/)
- [pandas Time Series](https://pandas.pydata.org/docs/user_guide/timeseries.html)

### **Benchmarks**:
- S&P 500: `^GSPC`
- Dow Jones: `^DJI`
- NASDAQ: `^IXIC`
- MSCI World: `^ACWI`
- FTSE 100: `^FTSE`

---

### **HITO 6: Mejoras UX - Modales y Navegación** (2-3 días)
**Prioridad**: 🟢 BAJA (mejora cosmética, no bloquea funcionalidad)

**Objetivo**: Mejorar la experiencia de navegación convirtiendo páginas completas en modales inline.

**Tareas**:

1. **Modal de Detalle de Asset (#4)**
   - Convertir `/portfolio/asset/<id>` en modal
   - Aparece en Dashboard y Holdings al hacer clic en un activo
   - Contenido: nombre, precio, métricas, historial de transacciones
   - Botón "Ver Completo" para ir a la página si se necesita más detalle
   - Cierre con ESC o clic fuera

2. **Modal de Nueva Transacción (#5)**
   - Convertir formulario de "Nueva Transacción" a modal
   - Reemplazar botón "Nueva Transacción" por icono "+" en la tabla
   - Ubicación: Dashboard y Holdings
   - Validación Ajax sin recarga de página
   - Feedback inline de errores
   - Auto-actualización de la tabla al guardar

**Beneficios**:
- Navegación más fluida (sin cambios de página)
- Menos clics para acciones frecuentes
- Experiencia más moderna y responsive
- Reduce la necesidad de volver atrás

**Stack**:
- Modal: Tailwind CSS utilities
- Ajax: Fetch API
- Validación: WTForms server-side + JavaScript client-side

**Consideraciones**:
- Mantener las páginas completas para SEO y accesibilidad
- Los modales son atajos, no reemplazos totales
- Formularios deben funcionar con y sin JavaScript

---

## ⚠️ CONSIDERACIONES

### **Performance**:
- Cálculos pesados → cachear resultados en `portfolio_metrics`
- Recalcular solo cuando hay nuevas transacciones o precios
- Gráficos → cargar data via AJAX (JSON) para evitar bloqueo

### **Precisión**:
- TWR/IRR requieren snapshots diarios → crear job nocturno
- Volatilidad necesita ≥30 días de datos
- Sharpe Ratio requiere risk-free rate actualizado

### **UX**:
- Explicar métricas con tooltips (no todos conocen TWR/Sharpe)
- Mostrar "Data insuficiente" si <30 días de historial
- Permitir comparación con períodos anteriores

---

## 📝 SIGUIENTE SPRINT (Sprint 5)

Después de completar Sprint 4, los siguientes pasos serían:

- **Sprint 5**: Actualización Automática de Precios (scheduler diario)
- **Sprint 6**: Diversificación y Watchlist
- **Sprint 7**: Alertas y Notificaciones
- **Sprint 8**: Testing Exhaustivo y Optimización

---

**Documento creado por**: AI Assistant  
**Fecha**: 6 Noviembre 2025  
**Versión**: 1.0 - Planificación Inicial  
**Estado**: 📋 Pendiente de aprobación

