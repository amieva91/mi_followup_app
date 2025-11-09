# 📊 SPRINT 4 - MÉTRICAS AVANZADAS Y ANÁLISIS
## 🚧 EN PROGRESO

**Versión**: v4.0.0-beta (HITO 1 completado)  
**Inicio**: 6 Noviembre 2025  
**Duración estimada**: 3 semanas  
**Estado**: ✅ HITO 1 COMPLETADO (8 Nov) | 🚧 HITO 2 SIGUIENTE

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

### **HITO 2: Métricas Avanzadas** (5-6 días)
**Prioridad**: 🟡 MEDIA

**Métricas a Implementar**:

1. **TWR (Time-Weighted Return)**
   - Mide performance de la estrategia de inversión
   - Elimina el efecto de deposits/withdrawals
   - Comparable con benchmarks
   ```
   TWR = [(1 + R1) × (1 + R2) × ... × (1 + Rn)] - 1
   donde Ri = (Valor Final - Valor Inicial - Cash Flow) / (Valor Inicial + Cash Flow ponderado)
   ```

2. **IRR (Internal Rate of Return / Money-Weighted Return)**
   - Mide performance considerando timing de cash flows
   - Más realista para el inversor individual
   - Usa librería `numpy-financial` para cálculo

3. **Sharpe Ratio**
   ```
   Sharpe = (Return Promedio - Risk-Free Rate) / Volatilidad
   ```
   - Risk-Free Rate: 3% anual (ajustable)
   - Volatilidad: Desviación estándar de returns diarios
   - Interpretación: >1 bueno, >2 muy bueno, >3 excelente

4. **Max Drawdown**
   ```
   Drawdown = (Valor Pico - Valor Actual) / Valor Pico × 100
   Max Drawdown = max(Drawdown) en período
   ```
   - Peor caída desde un pico
   - Identifica riesgo de pérdida

5. **Volatilidad (Desviación Estándar)**
   ```
   Volatilidad Anualizada = σ_diaria × √252
   ```
   - σ_diaria: Desviación estándar de returns diarios
   - 252: Días de trading en un año
   - Interpretación: Mayor volatilidad = mayor riesgo

**Archivos**: 
- `app/services/metrics/advanced_metrics.py`
- `app/services/metrics/time_series.py` (cálculos temporales)

**Dependencias nuevas**:
```txt
numpy-financial==1.0.0  # IRR calculation
numpy==1.26.0           # Array operations
pandas==2.1.0           # Time series (opcional)
```

**UI**:
- Sección "Análisis de Riesgo" en dashboard
- Cards con gráficos mini (sparklines)
- Comparación con benchmarks (S&P 500, MSCI World)

---

### **HITO 3: Gráficos de Evolución** (4-5 días)
**Prioridad**: 🟡 MEDIA

**Gráficos a Implementar**:

1. **Evolución del Portfolio (Línea)**
   - Eje X: Tiempo (diario/semanal/mensual)
   - Eje Y: Valor en EUR
   - Series: Valor Actual, Capital Invertido, P&L Acumulado
   - Marcadores de cash flows (deposits/withdrawals)

2. **P&L Acumulado (Área)**
   - P&L Realizado (verde sólido)
   - P&L No Realizado (verde transparente)
   - Línea de suma total

3. **Top Ganadores/Perdedores (Barra Horizontal)**
   - Top 5 assets con mayor P&L %
   - Top 5 assets con menor P&L %
   - Colores: verde (ganadores), rojo (perdedores)

4. **Comparación con Benchmarks (Líneas Múltiples)**
   - Tu portfolio (línea azul gruesa)
   - S&P 500 (línea gris)
   - MSCI World (línea naranja)
   - Normalizado a 100 desde fecha inicial

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

### **HITO 4: Distribución del Portfolio** (3-4 días)
**Prioridad**: 🟢 BAJA (nice-to-have)

**Gráficos de Distribución (Pie/Donut Charts)**:

1. **Por Asset**
   - Top 10 assets + "Otros"
   - Porcentaje y valor absoluto

2. **Por Sector**
   - Technology, Healthcare, Finance, etc.
   - Obtenido de Yahoo Finance (ya disponible)

3. **Por Industria**
   - Más granular que sector
   - Software, Biotech, Banks, etc.

4. **Por Broker**
   - IBKR vs DeGiro
   - Útil para identificar concentración

5. **Por Tipo de Asset**
   - Stocks vs ETFs
   - Obtenido de parsers (ya disponible)

6. **Por Moneda**
   - USD, EUR, GBP, HKD, etc.
   - Exposición a divisas

7. **Por País**
   - US, EU, UK, China, etc.
   - Diversificación geográfica

**Archivos**:
- `app/services/metrics/distribution.py` - Cálculos de distribución
- `app/templates/portfolio/distribution.html` - Página de distribución

**UI**:
- Grid responsive 2x2 o 3x2
- Cada pie chart con leyenda
- Click en slice muestra detalles

---

### **HITO 5: Página de Métricas Completa** (2-3 días)
**Prioridad**: 🟡 MEDIA

**Estructura de la Página** (`/portfolio/metrics`):

```
┌────────────────────────────────────────────────────┐
│ 📊 RESUMEN DE PERFORMANCE                          │
│                                                    │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐│
│ │ROI: 20% │ │TWR: 18% │ │IRR: 19% │ │Sharp:2.1││
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘│
└────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────┐
│ 📈 EVOLUCIÓN DEL PORTFOLIO                         │
│                                                    │
│ [Gráfico de líneas con selector de rango]         │
└────────────────────────────────────────────────────┘

┌─────────────────────┐ ┌─────────────────────────┐
│ 🎯 DISTRIBUCIÓN     │ │ 🏆 TOP PERFORMERS       │
│                     │ │                         │
│ [Pie charts grid]   │ │ [Barra horizontal]      │
└─────────────────────┘ └─────────────────────────┘

┌────────────────────────────────────────────────────┐
│ ⚠️ ANÁLISIS DE RIESGO                              │
│                                                    │
│ Max Drawdown: -12.5% | Volatilidad: 15.2%        │
│ [Gráfico de drawdown histórico]                   │
└────────────────────────────────────────────────────┘
```

**Selector de Período**:
- 1 mes, 3 meses, 6 meses, 1 año, Todo el historial
- Recalcula todas las métricas para el período seleccionado

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
- [ ] HITO 4: Gráficos de Distribución (Pie charts)
- [ ] HITO 5: Página de Métricas Completa
- [ ] Testing E2E, deployment a producción

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

