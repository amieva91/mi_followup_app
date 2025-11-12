# 🎯 TU PLAN MAESTRO - Sistema Financiero Personal

**Fecha de inicio**: 5 Octubre 2025  
**Timeline**: 6 meses (26 semanas)  
**Última actualización**: 12 Noviembre 2025  
**Estado actual**: ✅ Sprint 3 COMPLETADO (v3.6.0) | 🚧 Sprint 4 EN PROGRESO (v4.3.0 - HITO 1 ✅ | HITO 2 ✅ | Refinements ✅ | UX Avanzadas ✅ | HITO 3 ✅)

## 🎉 PROGRESO RECIENTE

**✅ SPRINT 0 - Infraestructura (COMPLETADO - 5 Oct)**
- Entornos limpiados (desarrollo + producción)
- Estructura modular creada (Factory Pattern)
- Git configurado (branches: develop, main)
- Primera página funcionando en https://followup.fit/

**✅ SPRINT 1 - Autenticación (COMPLETADO - 5 Oct)**
- Modelo User con password hashing
- Registro, Login, Logout, Reset Password
- Dashboard protegido
- Templates elegantes con Tailwind CSS
- ¡Sistema 100% funcional en producción!

**✅ SPRINT 2 - Gastos e Ingresos (COMPLETADO - 6 Oct)**
- Categorías de gastos con jerarquía padre-hijo
- Categorías de ingresos
- Gastos y ingresos puntuales y recurrentes (daily/weekly/monthly/yearly)
- Generación automática de instancias recurrentes históricas
- Edición de series recurrentes completas
- Eliminación inteligente (entrada individual vs serie completa)
- Vista de tabla jerárquica para categorías
- Emoji picker con sugerencias clickeables
- Dashboard con KPIs en tiempo real (ingresos/gastos/balance del mes)

**✅ SPRINT 3 - CSV Processor & Portfolio Management (COMPLETADO - 7 Nov)**  
**Versión Final**: v3.6.0 | **Duración**: 4 semanas + 1 día (mejoras finales)
- ✅ HITO 1: Base de Datos y Arquitectura
  - 9 modelos: Broker, BrokerAccount, Asset, PriceHistory, PortfolioHolding, Transaction, CashFlow, PortfolioMetrics + **AssetRegistry**
  - Migraciones aplicadas en dev y prod
  - Seeders de brokers (IBKR, DeGiro, Manual)
- ✅ HITO 2: Entrada Manual de Posiciones
  - CRUD de cuentas de broker
  - Entrada manual de transacciones (BUY/SELL/DIVIDEND/FEE/DEPOSIT/WITHDRAWAL)
  - Actualización automática de holdings con FIFO
  - Cálculo de P&L realizadas y no realizadas
  - Eliminación destructiva de cuentas
- ✅ HITO 3: Parser CSV IBKR
  - Formato jerárquico con secciones (Account Info, Trades, Holdings, Dividends)
  - Extracción de ISINs de "Financial Instrument Information"
  - Normalización de símbolos (IGCl → IGC)
  - Soporte para múltiples divisas (USD, EUR, HKD, SGD, NOK, GBP)
- ✅ HITO 4: Parser CSV DeGiro
  - **Transacciones CSV**: Lectura por índices (csv.reader), columna 8 = moneda
  - **Estado de Cuenta CSV**: Consolidación unificada de dividendos con FX
  - Detección de tipos de transacción por descripción
  - Cálculo automático de holdings con FIFO
  - Extracción de ISIN de descripciones
- ✅ HITO 5: Importador a Base de Datos
  - Detección automática de duplicados (100% efectiva)
  - Filtrado de transacciones FX (Forex)
  - Assets como catálogo global compartido
  - Recálculo automático de holdings desde transacciones
  - Corrección de signos (precios siempre positivos)
- ✅ HITO 6: Interfaz Web
  - Formulario de subida de CSV con drag & drop
  - Detección automática de formato (IBKR/DeGiro)
  - Feedback con estadísticas de importación
  - Integración completa con dashboard de portfolio
- ✅ HITO 7: Búsqueda y Edición de Transacciones
  - Filtros combinables (símbolo, tipo, cuenta, fechas)
  - Edición individual con recálculo automático
  - Vista unificada de holdings por asset (múltiples brokers)
- ✅ HITO 8: **AssetRegistry - Sistema Global de Enriquecimiento** (NUEVO - 19 Oct)
  - **Tabla global compartida**: Cache de mapeos ISIN → Symbol, Exchange, MIC, Yahoo Suffix
  - **Alimentación automática desde CSVs**:
    - IBKR aporta symbol + exchange completos
    - DeGiro aporta ISIN + MIC (se mapea localmente)
  - **Actualización inteligente**: Si un registro existe, actualiza campos vacíos
  - **Enriquecimiento con OpenFIGI**: Automático durante importación para assets sin symbol
  - **CSVImporterV2**: Nuevo importer con progreso en tiempo real
  - **Interfaz de gestión completa** (`/portfolio/asset-registry`):
    - Búsqueda por ISIN, Symbol, Nombre
    - Filtros (solo sin enriquecer)
    - Ordenación por cualquier columna
    - Edición en modal
    - Eliminación con confirmación
    - Estadísticas de enriquecimiento (total/enriched/pending)
  - **Enriquecimiento manual**: 
    - Botones en edición de transacciones (OpenFIGI o Yahoo URL)
    - Enriquecimiento directo desde modal de AssetRegistry
    - Feedback visual detallado con banners
  - **Contador de uso**: `usage_count` para estadísticas de popularidad (columna ordenable)
  - **Acceso directo**: Banner en transacciones para acceder al registro global
  - **Estado inteligente**: Solo requiere `symbol` (MIC opcional, mejora precisión)
- ✅ HITO 9: **MappingRegistry - Sistema de Mapeos Editables** (NUEVO - 21 Oct)
  - **Tabla global de mapeos**: MIC→Yahoo, Exchange→Yahoo, DeGiro→IBKR
  - **CRUD completo** (`/portfolio/mappings`):
    - Búsqueda por tipo o clave
    - Filtros por tipo de mapeo
    - Ordenación por cualquier columna
    - Crear, editar, eliminar mapeos
    - Activar/desactivar mapeos sin borrarlos
  - **Mappers dinámicos**: Leen de la BD en lugar de diccionarios hardcodeados
  - **Acceso directo**: Link desde AssetRegistry
  - **Expansión colaborativa**: Usuarios pueden añadir nuevos mapeos
- ✅ HITO 10: **Fixes de Estabilidad** (v3.3.4 - 21 Oct)
  - **Progreso de importación**: Primer archivo ahora visible en "Completados"
  - **Conteo correcto**: 5/5 archivos en lugar de 4/5
  - **Botones funcionales**: OpenFIGI/Yahoo en edición de transacciones ahora funcionan
  - **Validación de campos**: JavaScript verifica existencia antes de actualizar
  - **Feedback mejorado**: Banners detallados con información completa del enriquecimiento
- ✅ HITO 11: **Fix Crítico - DeGiro Dividendos/Fees sin Fecha** (v3.3.5 - 2 Nov)
  - **Problema**: Transacciones del CSV "Estado de Cuenta" rechazadas (407 total)
  - **Causa**: `parse_datetime()` no manejaba objetos `datetime.date`
  - **Solución**: Soporte completo para `datetime.date` → conversión a `datetime`
  - **Resultado**: ✅ 407 transacciones importadas correctamente
  - **Fixes adicionales**: Tooltip AssetRegistry, filtro "Solo sin enriquecer"
- ✅ HITO 12: **Precios en Tiempo Real - Yahoo Finance** (v3.4.0 - 5 Nov)
  - **Integración completa Yahoo Finance**:
    - Autenticación: cookie + crumb para API avanzadas
    - Chart API: precio, cambio %, 52w high/low, volume
    - quoteSummary API: 15 métricas avanzadas por asset
  - **Métricas obtenidas**: Market Cap, P/E (trailing/forward), PEG, Beta, Dividend Yield, Ex-Dividend Date, Analyst Recommendations
  - **Progress bar en tiempo real**: Modal no-bloqueante con estado (updating/success/error)
  - **Dashboard mejorado**: Valores actuales, P&L no realizado calculado, última actualización
  - **Manejo robusto**: Assets suspendidos/delisted detectados correctamente
- ✅ HITO 13: **Conversión de Divisas - API del BCE** (v3.5.0 - 6 Nov)
  - **Servicio de divisas**: `app/services/currency_service.py`
    - API: `exchangerate-api.com` (gratis, 166 monedas)
    - Cache thread-safe de 24 horas
    - Fallback rates integrados
    - Manejo especial GBX (British Pence = GBP/100)
  - **Página dedicada** `/portfolio/currencies`:
    - Tabla de tasas para monedas del portfolio
    - Información de cache (última actualización, edad)
    - Botón "🔄 Actualizar Tasas" manual
  - **Display dual currency**: Valor en EUR (principal) + moneda local (gris, si ≠ EUR)
  - **Holdings ampliada**: Ancho 95% (preparado para más columnas)
  - **🔴 FIX CRÍTICO - Coste Total**: 
    - BUG: Sumaba costes SIN conversión a EUR (error 10x: 957K en lugar de 96K)
    - FIX: Convierte cada holding a EUR ANTES de sumar
    - Impacto: Dashboard ahora muestra valores correctos
- ✅ MEJORAS FINALES:
  - **FIFO robusto** con posiciones cortas temporales
  - Parser completo DeGiro (Transacciones + Estado de Cuenta)
  - **Corrección extracción monedas**: csv.reader por índices (columna 8)
  - **Consolidación unificada de dividendos** (3-4 líneas relacionadas + FX)
  - Normalización de símbolos IBKR + extracción ISINs
  - Import múltiple de archivos simultáneos
  - Detección inteligente de duplicados (snapshot, no batch)
  - Eliminación destructiva de cuentas broker
  - **Formato europeo**: 1.234,56 en todos los números
  - **Visualización mejorada**: Type • Currency • ISIN (en lugar de nombre)
  - Búsqueda con sorting + filtros real-time
- ✅ HITO 14: **Mejoras Finales - Optimización y UX** (v3.6.0 - 7 Nov)
  - **Optimizaciones de rendimiento**:
    - Limpieza de 15 scripts temporales del repositorio
    - Mensaje informativo cuando import está vacío (duplicados)
    - Timeouts en actualización de precios (10s/request, 180s máximo total)
    - Paginación de 100 transacciones por página con controles completos
  - **Mejoras de experiencia de usuario**:
    - Búsqueda en tiempo real sin botón submit (AssetRegistry + Transacciones)
    - Indicador de última sincronización en dashboard
    - Guías dinámicas para obtener CSV según broker (DeGiro/IBKR)
    - Columna "Peso %" en dashboard (cálculo automático)
    - Columnas ordenables en Dashboard y Holdings (↑↓⇅)
    - **Ancho 92% unificado** en toda la aplicación (16 páginas + navbar)
  - **Correcciones críticas**:
    - Fix error paginación transacciones (generator → dict)
    - Eliminado doble emoji en botón "Actualizar Precios"
    - Eliminado mensaje innecesario de sincronización
    - Navbar alineado al 92% para consistencia visual completa

- **Métricas finales Sprint 3**: 
  - ✅ 209 assets en AssetRegistry (90%+ enriquecidos)
  - ✅ 29 holdings correctos (10 IBKR + 19 DeGiro)
  - ✅ 100% precisión FIFO (0 errores)
  - ✅ 15 métricas Yahoo Finance por asset
  - ✅ 166 monedas soportadas con conversión automática
  - ✅ Dashboard con precios en tiempo real
  - ✅ Sistema listo para producción
  - ✅ MappingRegistry con 3 tipos de mapeos editables
  - ✅ 8 mejoras de optimización y UX implementadas
  - ✅ Experiencia visual consistente (92% en toda la app)

**🚧 SPRINT 4 - Métricas Avanzadas (EN PROGRESO - 12 Nov)**  
**Versión Actual**: v4.3.0 | **Duración estimada**: 3 semanas  
**Documento detallado**: `SPRINT4_METRICAS_AVANZADAS.md`  
**Progreso**: HITO 1 ✅ | HITO 2 ✅ | HITO 3 ✅ | **Pendiente**: HITO 4 (Comparación con Benchmarks)

**Objetivo**: Construir sistema completo de métricas y análisis financiero

**✅ HITO 1: Métricas Básicas (COMPLETADO - 8 Nov)**
- ✅ **8 Métricas implementadas**:
  - P&L Realizado con FIFO robusto (reescrito desde cero)
  - P&L No Realizado (posiciones abiertas)
  - P&L Total (con desglose: Realizado + No Realizado + Dividendos - Comisiones)
  - ROI (Return on Investment, con desglose completo de cálculo)
  - Leverage/Dinero Prestado (con lógica de cash disponible)
  - Valor Total Cartera (posiciones a precio actual)
  - Valor Total Cuenta de Inversión (incluye todos los componentes: deposits, P&L, dividends, fees, cash/leverage)
  - Peso % por Posición (concentración de riesgo)
- ✅ **Dashboard reorganizado**:
  - Métricas Globales e Históricas primero (P&L Total, ROI, Valor Cuenta)
  - Métricas del Portfolio Actual después (Valor Cartera, Coste, P&L No Realizado, etc)
- ✅ **UI/UX mejorada**:
  - Tooltips explicativos en todas las métricas
  - Desgloses detallados en todos los indicadores
  - Página P&L by Asset con búsqueda en tiempo real + ordenación
  - Contador de dividendos por asset
  - Indicador de assets en cartera vs cerrados
- ✅ **Ordenación numérica universal**:
  - Dashboard holdings (JavaScript, formato europeo)
  - Holdings page (JavaScript, formato europeo)
  - PL by Asset (JavaScript, formato europeo)
  - Transactions (JavaScript con fecha, texto, números)
- ✅ **Fixes críticos**:
  - P&L Realizado: reescrito con FIFOCalculator (antes usaba 5% arbitrario)
  - P&L Total: fórmula corregida (incluye dividendos y comisiones)
  - Leverage: incluye P&L Realizado + P&L No Realizado en dinero usuario
  - Cash disponible: solo se muestra si leverage < 0
  - Brokers en holdings: ahora muestra correctamente múltiples brokers
  - Holdings: límite de 15 eliminado, muestra todas las posiciones
  - P&L: calculado en backend (cost_eur y pl_eur pre-calculados)
  - Logs simplificados: cache hits de currency_service eliminados

**✅ HITO 2: Modified Dietz Method (COMPLETADO - 9 Nov)**
- ✅ **Portfolio Valuation Service** (`app/services/metrics/portfolio_valuation.py`):
  - `get_value_at_date()`: Valoración del portfolio en cualquier fecha histórica
  - `get_user_money_at_date()`: Dinero real del usuario (sin apalancamiento)
  - Reconstrucción histórica de posiciones con FIFO
  - Soporte para precios actuales vs precios históricos
- ✅ **Modified Dietz Calculator** (`app/services/metrics/modified_dietz.py`):
  - Estándar GIPS (Global Investment Performance Standards)
  - `calculate_return()`: Rentabilidad de un período específico
  - `calculate_annualized_return()`: Rentabilidad anualizada
  - `calculate_ytd_return()`: Rentabilidad año actual (YTD)
  - `get_all_returns()`: Wrapper para dashboard
  - Fórmula: `R = (VF - VI - CF) / (VI + Σ(CF_i × W_i))`
  - Cash flows externos: Solo DEPOSIT/WITHDRAWAL (dividendos son ingresos internos)
- ✅ **Nueva card en Dashboard**: 💎 Rentabilidad (Modified Dietz)
  - Rentabilidad Anualizada (con años de inversión)
  - Rentabilidad Total (%)
  - Rentabilidad YTD (año actual)
  - Ganancia Absoluta (EUR)
  - Días de inversión
- ✅ **Validación matemática exitosa**:
  - Ganancia Modified Dietz: 52.472 EUR
  - P&L Total del sistema: 52.562 EUR
  - **Error: 0,17%** ✅ (dentro del margen aceptable)
- ✅ **Ventajas del Modified Dietz**:
  - NO requiere precios históricos (solo necesita valor inicial y final)
  - Pondera cash flows por tiempo (elimina efecto de timing de deposits/withdrawals)
  - Comparable con benchmarks y otros portfolios
  - Estándar de la industria financiera

**✅ Refinements: Performance & UX (COMPLETADO - 10 Nov)**
- ✅ **Cache de Métricas** (Mejora de Performance):
  - Nueva tabla `MetricsCache` con TTL de 24 horas
  - Service `MetricsCacheService` con `get()`, `set()`, `invalidate()`
  - Invalidación automática en transacciones/precios/imports
  - Botón manual "♻️ Recalcular" en dashboard
  - Badge visual "⚡ Cache" cuando se usa cache
  - **Mejora de rendimiento**: Dashboard 2-3s → 0.3s
- ✅ **Fixes Críticos**:
  - CSRF token en botón "Actualizar Precios" (error 400 corregido)
  - Meta tag `<meta name="csrf-token">` en `layout.html`
  - Funcionalidad "🗑️ Eliminar Transacciones" con confirmación
  - Recalculo automático de holdings tras eliminar
  - Invalidación automática de cache tras eliminar
- ✅ **UX Mejorada**:
  - Campo integrado para Yahoo URL (en vez de prompt nativo)
  - Input con placeholder + botón "Enriquecer"
  - Validación: error si campo vacío
  - Limpieza automática tras éxito
  - Mensajes de confirmación mejorados

**✅ UX Avanzadas: Transacciones Manuales (COMPLETADO - 10 Nov)**
- ✅ **Auto-selección en SELL** (`/portfolio/transactions/new`):
  - Dropdown inteligente para seleccionar activos del portfolio
  - Opción "-- Todas las cuentas --" por defecto (muestra todos los assets)
  - Filtro opcional por cuenta específica (IBKR, DeGiro, Manual)
  - Auto-completado completo al seleccionar:
    - Symbol, ISIN, Divisa, Nombre del activo, Tipo de activo, Market Identifiers
    - Actualización automática del campo "Cuenta" al broker del asset
  - **Botón "Máximo"**: Auto-completa cantidad disponible para vender
  - **Display mejorado**: `[Broker] Symbol - Name (Quantity)` en dropdown
- ✅ **Autocompletado en BUY**:
  - Búsqueda en tiempo real desde `AssetRegistry` global
  - Sugerencias al escribir en Symbol o ISIN
  - Auto-fill completo de todos los campos al seleccionar:
    - Symbol, ISIN, Currency, Name, Asset Type, Exchange, MIC, Yahoo Suffix
  - Experiencia sin interrupciones (no bloquea escritura del usuario)
  - Alimentado desde base de datos global (compartida entre usuarios)
- ✅ **Venta por quiebra (Bankruptcy)**:
  - Validación actualizada: `price >= 0` (antes: `price > 0`)
  - Soporte completo para precio = 0€
  - Eliminación automática de holdings con `quantity = 0`

**✅ HITO 3: Gráficos de Evolución Histórica (COMPLETADO - 12 Nov)**
- ✅ **Nueva página `/portfolio/performance`**:
  - **Gráfico 1: Valor Real de la Cuenta** (sin apalancamiento, con precio actual en último punto)
  - **Gráfico 2: Rentabilidad Acumulada (Modified Dietz)** (% acumulado histórico)
  - **Gráfico 3: Apalancamiento/Cash** (verde=cash positivo, rojo=leverage negativo)
  - **Gráfico 4: Capital Invertido Neto** (deposits - withdrawals acumulados)
  - **Gráfico 5: P&L Total Acumulado** (realizado + no realizado + dividendos - comisiones)
  - Frecuencia: **mensual** (rendimiento optimizado)
  - Último punto con **precios reales actuales** (`use_current_prices=True`)
- ✅ **Backend Services**:
  - `PortfolioEvolutionService` (`app/services/metrics/portfolio_evolution.py`)
  - `PortfolioValuation.get_detailed_value_at_date()`: Retorna holdings_value, cash, cost, P&L No Realizado
  - Integración con `FIFOCalculator` para P&L Realizado histórico
  - Cálculo correcto de apalancamiento: `user_money - holdings_value`
  - P&L No Realizado solo para último punto (HOY), histórico solo P&L Realizado
  - API endpoint `/portfolio/api/evolution?frequency=monthly`
- ✅ **Frontend**:
  - Chart.js 4.0 con adaptador de fechas (`chartjs-adapter-date-fns`)
  - `app/static/js/charts.js` con formateo europeo
  - 5 gráficos de línea con colores dinámicos (verde/rojo según valor)
  - Loading spinner y manejo de errores
  - Gráficos responsivos con tooltips informativos
- ✅ **Correcciones críticas**:
  - **Conversión EUR universal**: Todos los cálculos históricos convierten `value_local` y `cost_local` a EUR
  - **Fórmula de Leverage corregida**: `broker_money = user_money - holdings_value` (antes: `value - user_money`)
  - **P&L histórico vs actual**: P&L No Realizado solo en último punto (HOY), histórico solo usa P&L Realizado
  - **Colores invertidos corregidos**: Verde para cash positivo, rojo para apalancamiento negativo
  - **Tipo de dato corregido**: `float()` para evitar `TypeError` con `Decimal`
- ✅ **Nomenclatura corregida**:
  - Dashboard: "🏦 Valor Real Cuenta" (antes "Valor Total Cuenta")
  - Performance: "Evolución del Valor Real de la Cuenta" (clarifica: sin apalancamiento)
  - Mantiene: "💰 Valor Total Cartera" en métricas de portfolio actual

- ✅ **Botones de enriquecimiento inteligentes**:
  - **"Enriquecer con OpenFIGI"**:
    - Deshabilitado en modo NEW (tooltip: "Solo disponible al editar transacciones existentes")
    - Habilitado en modo EDIT
  - **"Desde URL de Yahoo"**:
    - Habilitado en modo NEW y EDIT
    - Input field con validación
    - Extrae symbol + yahoo_suffix desde URL
    - Actualiza `AssetRegistry` y sincroniza con `Asset`
- ✅ **Redirección mejorada**:
  - BUY → redirige a `/portfolio/holdings` (antes: `/portfolio/transactions`)
  - SELL → redirige a `/portfolio/holdings` (antes: `/portfolio/transactions`)
  - Mejor flujo UX: Ver holdings inmediatamente tras transacción
- ✅ **Fixes críticos**:
  - `KeyError: 'avg_price'` → Corregido a `'average_buy_price'` en FIFO
  - Modal de precios: `data.updated` → `data.success` (corrección de clave JSON)
  - Holdings API: Filtro por `account_id` optimizado (query más eficiente)
  - `AttributeError: 'avg_buy_price'` → Atributo correcto `average_buy_price`

**Hitos Planificados**:
- [x] **HITO 1**: Métricas Básicas ✅ COMPLETADO (8 Nov 2025)
- [x] **HITO 2**: Modified Dietz Method ✅ COMPLETADO (9 Nov 2025)
- [x] **Refinements**: Performance & UX ✅ COMPLETADO (10 Nov 2025)
- [x] **UX Avanzadas**: Transacciones Manuales ✅ COMPLETADO (10 Nov 2025)
- [x] **HITO 3 - Fase 1**: Gráficos de Evolución ✅ COMPLETADO (11 Nov 2025)
- [ ] **HITO 3 - Fase 2**: Gráficos Adicionales 🚧 SIGUIENTE
  - Gráfico de Apalancamiento/Cash histórico
  - Gráfico de Flujos de caja (Deposits/Withdrawals)
  - Gráfico de P&L Acumulado
- [ ] **HITO 3 - Fase 3**: Comparación con Benchmarks
  - Modified Dietz vs S&P 500 vs NASDAQ vs Benchmarks (comparación visual)
  - Tabla comparativa por año (Tu rentabilidad vs índices)
  - Integración de Yahoo Finance API para datos históricos de índices
- [ ] **HITO 4**: Distribución del Portfolio (Pie charts: asset/sector/industria/broker/moneda/país)
- [ ] **HITO 5**: Mejoras UX - Modales y Navegación
  - Convertir detalle de asset (`/portfolio/asset/<id>`) a modal en Dashboard y Holdings
  - Convertir "Nueva Transacción" a modal con botón "+" en tabla (Dashboard y Holdings)
  - Formularios con validación Ajax sin recarga
  - Manejo de errores inline
  - Mejora experiencia de navegación

**Sprints Futuros** (después de Sprint 4):
- **Sprint 5**: Actualización Automática de Precios (2 semanas)
  - Scheduler diario, histórico de precios, gráficos de evolución
- **Sprint 6**: Diversificación y Watchlist (2 semanas)
  - Análisis de concentración, alertas de diversificación, watchlist con comparación
- **Sprint 7**: Alertas y Notificaciones (2 semanas)
  - Alertas de precio, calendario dividendos, eventos corporativos
- **Sprint 8**: Testing y Optimización (2 semanas)
  - Tests 80%+, optimización SQL, logging, monitoring, deployment automatizado
- **Sprint 9**: Planificación Financiera y Cash Flow Forecast (3 semanas)
  - Gastos planificados/deseados (viajes, caprichos, compras grandes)
  - Proyección de flujo de caja a 12 meses
  - Análisis de capacidad de endeudamiento
  - Simulador "What-if" para decisiones financieras
  - Dashboard de planificación con alertas y límites

**🔗 URLs Funcionales:**
- **Producción**: https://followup.fit/
- **Desarrollo**: http://localhost:5001

---

## 👤 TU PERFIL Y CONFIGURACIÓN

```yaml
Objetivo: Producto comercial completo
Experiencia: Principiante técnico (desarrollo con IA)
Tiempo disponible: 40+ horas/semana (tiempo completo)
Módulos necesarios: TODOS (13 módulos)
Pain point crítico: Procesamiento de CSVs (IBKR + DeGiro)

Prioridades:
  1. Calidad del código (arquitectura limpia, tests)
  2. Features completas (muchas funcionalidades)
  3. Facilidad de mantenimiento
  4. Performance (rapidez de ejecución)
  5. Velocidad de desarrollo
```

---

## 🖥️ TUS ENTORNOS

### Desarrollo (WSL)
```bash
Host: ssoo@ES-5CD52753T5
Directorio: /home/ssoo/www
OS: WSL Ubuntu
Shell: bash
```

### Producción (Oracle Cloud)
```bash
IP: 140.238.120.92
User: ubuntu
Directorio: /home/ubuntu/www
OS: Ubuntu 24.04.2 LTS
Dominio: https://followup.fit/
SSH Key: ~/.ssh/ssh-key-2025-08-21.key
```

### Comando SSH
```bash
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92
```

---

## 🏗️ ARQUITECTURA DEFINITIVA

### Stack Tecnológico
```yaml
Backend:
  Framework: Flask 3.x
  ORM: SQLAlchemy 2.x
  Auth: Flask-Login
  Testing: pytest + pytest-cov
  Migrations: Alembic

Frontend:
  Templates: Jinja2
  CSS: TailwindCSS 3.x
  JS: Alpine.js 3.x
  Interactividad: HTMX 1.9.x

Base de Datos:
  Desarrollo: PostgreSQL 16
  Producción: PostgreSQL 16

Deployment:
  Servidor Web: Gunicorn
  Proxy: Nginx
  Process Manager: systemd
  SSL: Let's Encrypt (Certbot)
  Domain: followup.fit
```

### Estructura del Proyecto
```
followup/
├── app/
│   ├── __init__.py           # Factory de aplicación
│   ├── config.py             # Configuración por entorno
│   ├── models/               # Modelos SQLAlchemy
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── account.py
│   │   ├── expense.py
│   │   └── ...
│   ├── routes/               # Blueprints por módulo
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── expenses.py
│   │   └── ...
│   ├── services/             # Lógica de negocio
│   │   ├── __init__.py
│   │   ├── kpi_service.py
│   │   ├── portfolio_service.py
│   │   └── ...
│   ├── forms/                # WTForms
│   │   ├── __init__.py
│   │   ├── auth_forms.py
│   │   ├── expense_forms.py
│   │   └── ...
│   ├── csv_processor/        # Módulo crítico separado
│   │   ├── __init__.py
│   │   ├── detectors/
│   │   ├── parsers/
│   │   ├── transformers/
│   │   └── tests/
│   ├── templates/            # Jinja2 templates
│   │   ├── base.html
│   │   ├── auth/
│   │   ├── dashboard/
│   │   └── ...
│   ├── static/               # Assets estáticos
│   │   ├── css/
│   │   │   └── output.css    # TailwindCSS compilado
│   │   ├── js/
│   │   │   └── main.js       # Alpine.js components
│   │   └── img/
│   └── utils/                # Utilidades comunes
│       ├── __init__.py
│       ├── decorators.py
│       └── helpers.py
├── tests/                    # Tests organizados
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── migrations/               # Alembic migrations
├── docs/                     # Documentación
├── scripts/                  # Scripts de deploy
│   ├── deploy.sh
│   └── backup.sh
├── .env.example              # Variables de entorno ejemplo
├── .gitignore
├── requirements.txt          # Dependencias Python
├── tailwind.config.js        # Config TailwindCSS
├── package.json              # Para TailwindCSS
├── pytest.ini                # Config pytest
└── README.md
```

---

## 📊 BASE DE DATOS: 15 TABLAS

### Core (7 tablas)
1. `users` - Usuarios del sistema
2. `bank_accounts` - Cuentas bancarias
3. `expense_categories` - Categorías de gastos
4. `expenses` - Gastos individuales
5. `income_categories` - Categorías de ingresos
6. `incomes` - Ingresos variables
7. `financial_snapshots` - Snapshots mensuales

### Inversiones (3 tablas)
8. `portfolio_holdings` - Holdings actuales
9. `portfolio_transactions` - Transacciones de inversión
10. `crypto_transactions` - Transacciones cripto

### Patrimonio (3 tablas)
11. `debt_plans` - Planes de deuda
12. `real_estate_assets` - Inmuebles
13. `pension_plans` - Planes de pensiones

### Análisis (2 tablas)
14. `metal_transactions` - Transacciones metales preciosos
15. `benchmarks` - Benchmarks y objetivos

---

## 🎨 DESIGN SYSTEM

### Paleta de Colores (Tema Financiero)
```css
/* Colores principales */
--primary: #1e40af;      /* Azul corporativo */
--secondary: #059669;    /* Verde finanzas (positivo) */
--danger: #dc2626;       /* Rojo (negativo/alertas) */
--warning: #f59e0b;      /* Ámbar (advertencias) */

/* Grises elegantes */
--gray-50: #f9fafb;
--gray-100: #f3f4f6;
--gray-800: #1f2937;
--gray-900: #111827;

/* Fondos y superficie */
--bg-primary: #ffffff;
--bg-secondary: #f9fafb;
--surface: #ffffff;
```

### Tipografía
```css
Font Stack: Inter, system-ui, -apple-system, sans-serif
Headings: font-weight: 600-700
Body: font-weight: 400
Numbers: font-feature-settings: "tnum" (tabular nums)
```

### Componentes Base
- Cards con sombras sutiles
- Botones con estados hover/active/disabled
- Formularios con validación inline
- Tablas responsivas con sorting
- Gráficos con Chart.js (consistente con design)
- Iconos: Heroicons (mismo estilo que Tailwind)

---

## 📅 PLAN DE 6 MESES - SPRINT POR SPRINT

### ⚙️ SPRINT 0: Setup Inicial (Semana 0 - 3 días) ✅ COMPLETADO

**Objetivo**: Preparar entornos de desarrollo y producción  
**Estado**: ✅ COMPLETADO (5 Oct 2025)

#### Tareas
- [x] **Día 1: Limpieza y Setup Git**
  ```bash
  # Desarrollo (WSL)
  cd /home/ssoo/www
  # Backup del sistema actual (por si acaso)
  mv * ../www_backup_$(date +%Y%m%d)/
  
  # Inicializar Git
  git init
  git config user.name "Tu Nombre"
  git config user.email "tu@email.com"
  ```

- [ ] **Día 1: Crear estructura base**
  ```bash
  mkdir -p followup/{app,tests,migrations,docs,scripts}
  cd followup
  python3 -m venv venv
  source venv/bin/activate
  ```

- [ ] **Día 2: Setup PostgreSQL**
  ```bash
  # Instalar PostgreSQL en WSL
  sudo apt update
  sudo apt install postgresql postgresql-contrib
  sudo service postgresql start
  
  # Crear base de datos
  sudo -u postgres psql
  CREATE DATABASE followup_dev;
  CREATE USER followup_user WITH PASSWORD 'dev_password';
  GRANT ALL PRIVILEGES ON DATABASE followup_dev TO followup_user;
  ```

- [ ] **Día 2: Instalar dependencias base**
  ```bash
  pip install flask flask-sqlalchemy flask-login flask-wtf
  pip install psycopg2-binary alembic pytest pytest-cov
  pip install python-dotenv gunicorn
  ```

- [ ] **Día 3: Setup TailwindCSS**
  ```bash
  npm init -y
  npm install -D tailwindcss @tailwindcss/forms
  npx tailwindcss init
  ```

- [ ] **Día 3: Configurar entorno de producción**
  ```bash
  # SSH a producción
  ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92
  
  # Limpiar directorio (CUIDADO: borra todo)
  cd /home/ubuntu/www
  sudo rm -rf *
  
  # Instalar dependencias del sistema
  sudo apt update
  sudo apt install python3-pip python3-venv postgresql nginx certbot
  ```

**Entregable**: Proyecto inicializado, Git configurado, ambos entornos listos  
**Checkpoint**: ✅ `git commit -m "Initial project setup"`

---

### 🔐 SPRINT 1: Autenticación + Base (Semana 1-2) ✅ COMPLETADO

**Objetivo**: Sistema de autenticación funcional + estructura base  
**Estado**: ✅ COMPLETADO (5 Oct 2025)

#### Semana 1: Modelos y Lógica

- [x] **Día 1-2: Modelo User y configuración**
  - Crear `app/__init__.py` (factory pattern)
  - Crear `app/config.py` (dev/prod configs)
  - Crear `app/models/user.py`
  - Tests unitarios del modelo User

- [x] **Día 3-4: Rutas de autenticación**
  - Crear `app/routes/auth.py` ✅
  - Crear `app/forms/auth_forms.py` (login, registro) ✅
  - Login, logout, registro ✅
  - Tests de rutas auth

- [x] **Día 5: Base template y diseño**
  - Crear `templates/base.html` (con TailwindCSS) ✅
  - Crear `templates/auth/login.html` ✅
  - Crear `templates/auth/register.html` ✅
  - Navbar básico ✅

#### Semana 2: Deploy y Validación

- [x] **Día 6-7: Completar funcionalidades auth**
  - Reseteo de contraseña ✅
  - Validaciones robustas ✅
  - Mensajes flash con diseño ✅
  - Tests completos (70%+ coverage)

- [x] **Día 8-9: Primer deploy a producción**
  - Setup Nginx en producción (No necesario - Flask directo) ✅
  - Setup Gunicorn + systemd ✅
  - Configurar SSL (Let's Encrypt) (Ya configurado) ✅
  - Deploy y pruebas en https://followup.fit/ ✅

- [x] **Día 10: Buffer y refinamiento**
  - Arreglar bugs encontrados ✅
  - Mejorar UX si necesario ✅
  - Documentación del proceso ✅

**Entregables**:
- ✅ Login/registro funcional - **HECHO**
- ✅ Diseño base elegante - **HECHO**
- ✅ Deploy automático funcionando - **HECHO**
- ✅ Tests pasando (70%+ coverage) - **PENDIENTE para próxima sesión**

**Checkpoint**: 
```bash
git tag v0.1-auth
git push origin main --tags
```

---

### 💰 SPRINT 2: Cuentas Bancarias (Semana 3-4)

**Objetivo**: Gestión de cuentas y efectivo

#### Semana 3: Backend

- [ ] **Día 1-2: Modelos**
  - `app/models/account.py` (BankAccount)
  - Migraciones Alembic
  - Tests de modelos

- [ ] **Día 3-4: CRUD completo**
  - `app/routes/accounts.py`
  - `app/forms/account_forms.py`
  - `app/services/account_service.py` (lógica de negocio)
  - Tests de servicio

- [ ] **Día 5: Dashboard inicial**
  - Vista de cuentas
  - Saldo total
  - Listado de cuentas

#### Semana 4: Frontend y Deploy

- [ ] **Día 6-7: UI elegante**
  - Cards de cuentas con iconos
  - Modal para añadir/editar cuenta
  - Validación client-side (Alpine.js)
  - Animaciones sutiles

- [ ] **Día 8: Tests y refinamiento**
  - Tests de integración
  - Validaciones edge cases
  - Performance checks

- [ ] **Día 9: Deploy a producción**
  - Merge a main
  - Deploy
  - Pruebas en producción
  - Backup de BD

- [ ] **Día 10: Buffer**
  - Documentación
  - Mejoras UX

**Entregables**:
- ✅ CRUD cuentas completo
- ✅ Dashboard mostrando efectivo
- ✅ UI pulida y responsiva

**Checkpoint**: 
```bash
git tag v0.2-accounts
```

---

### 💸 SPRINT 3: Gastos (Semana 5-6)

**Objetivo**: Gestión completa de gastos con categorías y recurrencias

#### Semana 5: Modelos y Lógica

- [ ] **Día 1-2: Categorías**
  - `app/models/expense_category.py`
  - Soporte jerárquico (padre/hijo)
  - Categorías predeterminadas
  - Tests

- [ ] **Día 3-5: Gastos**
  - `app/models/expense.py`
  - Soporte recurrencias (mensual, trimestral, etc.)
  - `app/services/expense_service.py`
  - Lógica de expansión de recurrencias
  - Tests exhaustivos

#### Semana 6: UI y Features Avanzadas

- [ ] **Día 6-7: UI de gastos**
  - Lista de gastos (tabla con sorting/filtros)
  - Formulario añadir gasto (con recurrencias)
  - Gestión de categorías
  - Gráfico de gastos por categoría (pie chart)

- [ ] **Día 8: Filtros y búsqueda**
  - Filtrar por fecha, categoría
  - Búsqueda por descripción
  - Exportar a CSV

- [ ] **Día 9: Deploy**
  - Tests finales
  - Deploy a producción
  - Validación

- [ ] **Día 10: Buffer**

**Entregables**:
- ✅ Categorías jerárquicas
- ✅ Gastos con recurrencias
- ✅ Visualización y filtros
- ✅ Exportación

**Checkpoint**: 
```bash
git tag v0.3-expenses
```

---

### 📊 SPRINT 4: Ingresos (Semana 7-8)

**Objetivo**: Gestión de ingresos variables y salario

#### Semana 7: Backend

- [ ] **Día 1-2: Modelos de ingresos**
  - `app/models/income_category.py`
  - `app/models/income.py`
  - Recurrencias (igual que gastos)
  - Tests

- [ ] **Día 3-4: Salario y servicios**
  - Salario anual en User model
  - `app/services/income_service.py`
  - Cálculos de ingresos por período
  - Tests

- [ ] **Día 5: Integración**
  - Rutas y forms de ingresos
  - Tests de integración

#### Semana 8: UI y Deploy

- [ ] **Día 6-7: UI de ingresos**
  - Lista de ingresos
  - Formularios
  - Gráficos de fuentes de ingreso
  - Configuración de salario

- [ ] **Día 8: Refinamiento**
  - Validaciones
  - Edge cases
  - Tests E2E

- [ ] **Día 9: Deploy**
  - Merge y deploy
  - Validación producción

- [ ] **Día 10: Buffer**

**Entregables**:
- ✅ Ingresos variables completos
- ✅ Configuración de salario
- ✅ Visualizaciones

**Checkpoint**: 
```bash
git tag v0.4-incomes
```

---

### 📈 SPRINT 5-6: Dashboard y KPIs (Semana 9-12)

**Objetivo**: Dashboard completo con métricas financieras

#### Semana 9-10: Cálculos de KPIs

- [ ] **Implementar servicios de cálculo**
  - `app/services/kpi_service.py`
  - Ingresos mensuales promedio
  - Gastos mensuales promedio
  - Ahorro mensual
  - Tasa de ahorro
  - Ratio deuda/ingresos (preparar para futuro)
  - Tests exhaustivos de cálculos

- [ ] **Sistema de snapshots**
  - `app/models/financial_snapshot.py`
  - Job automático para guardar snapshots mensuales
  - Histórico de métricas

#### Semana 11: Dashboard Frontend

- [ ] **Crear dashboard interactivo**
  - Cards de KPIs (diseño elegante)
  - Gráficos de evolución temporal (Chart.js)
  - Filtros por período (mes actual, 3m, 6m, 12m)
  - Comparativas mes a mes
  - Responsivo mobile

#### Semana 12: Refinamiento y Deploy

- [ ] **Optimización y tests**
  - Cache de cálculos
  - Performance optimization
  - Tests E2E del dashboard
  
- [ ] **Deploy y validación**

**Entregables**:
- ✅ Dashboard completo y funcional
- ✅ 6 KPIs principales calculados
- ✅ Gráficos interactivos
- ✅ Sistema de snapshots

**Checkpoint**: 
```bash
git tag v0.5-dashboard
```

**🎉 MILESTONE 1 COMPLETADO**: Sistema Core Funcional (3 meses)

---

### 📂 SPRINT 7-8: CSV Processor (Semana 13-16) ⚡ CRÍTICO

**Objetivo**: Resolver tu pain point principal - procesamiento robusto de CSVs

#### Semana 13-14: Arquitectura del Processor

- [ ] **Día 1-3: Estructura base**
  - `app/csv_processor/__init__.py`
  - `app/csv_processor/detectors/` (detectar formato)
  - `app/csv_processor/parsers/` (parsear datos)
  - `app/csv_processor/transformers/` (normalizar)
  - Tests con CSVs reales de ejemplo

- [ ] **Día 4-5: Parser DeGiro**
  - `degiro_parser.py`
  - Todos los tipos de transacción
  - Validaciones robustas
  - Tests exhaustivos

- [ ] **Día 6-7: Parser IBKR**
  - `ibkr_parser.py`
  - Manejo de formato complejo
  - Conversión a formato unificado
  - Tests exhaustivos

- [ ] **Día 8-10: Normalización y validación**
  - Formato unificado de salida
  - Validación de datos
  - Detección de errores y warnings
  - Reportes de problemas claros

#### Semana 15: Integración con Portfolio

- [ ] **Modelos de portfolio**
  - `app/models/portfolio_holding.py`
  - `app/models/portfolio_transaction.py`
  - Relaciones y validaciones

- [ ] **Integración del processor**
  - Importar transacciones desde CSV
  - Actualizar holdings automáticamente
  - Cálculo de cost basis
  - Tests de integración

#### Semana 16: UI y Deploy

- [ ] **UI de importación**
  - Drag & drop para CSVs
  - Preview de datos antes de importar
  - Reporte de errores/warnings
  - Confirmación de importación

- [ ] **Deploy y validación**
  - Probar con tus CSVs reales
  - Refinamiento basado en casos reales
  - Documentación de formatos soportados

**Entregables**:
- ✅ CSV Processor robusto (DeGiro + IBKR)
- ✅ Tests con >80% coverage
- ✅ UI intuitiva para importar
- ✅ Documentación completa

**Checkpoint**: 
```bash
git tag v0.6-csv-processor
```

---

### 💼 SPRINT 3 FINAL: Precios en Tiempo Real (1-2 semanas)

**Objetivo**: Integrar Yahoo Finance para valoración de mercado en tiempo real

**Duración**: 8 días

#### Fase 1: Base de Datos y Modelos (Día 1)

- [ ] **Migración para Asset model** - 15 nuevos campos:
  - **Precios**: currentPrice, previousClose, currency, regularMarketChangePercent
  - **Valoración**: marketCap, marketCapFormatted (K/M/B), marketCapEUR, trailingPE, forwardPE
  - **Info Corporativa**: sector, industry
  - **Riesgo/Rendimiento**: beta, dividendRate, dividendYield
  - **Análisis**: recommendationKey, numberOfAnalystOpinions, targetMeanPrice
  - **Metadata**: lastPriceUpdate

- [ ] **Actualizar PortfolioHolding model**
  - Properties: current_market_value, unrealized_pl, unrealized_pl_percent, total_return

#### Fase 2: Servicios de Actualización (Días 2-3)

- [ ] **PriceUpdater service**
  - `app/services/market_data/price_updater.py`
  - Integración con yfinance
  - Conversión de divisas (hardcoded inicial: USD, GBP, HKD → EUR)
  - Formateo de marketCap (1.5B, 234M, 45K)
  - Actualizar solo assets con holdings > 0

- [ ] **Ruta /prices/update**
  - POST endpoint para actualización manual
  - Feedback de resultados (updated/failed/total)

#### Fase 3: UI y Visualización (Días 4-5)

- [ ] **Dashboard mejorado**
  - 4 cards de resumen:
    - Valor Total del Portfolio (EUR)
    - P&L No Realizado (monto y %)
    - Costo Total
    - Rendimiento Total %
  - Botón "🔄 Actualizar Precios"
  - Última actualización timestamp

- [ ] **Tabla de holdings mejorada**
  - Precio actual + moneda
  - Cambio del día (% con ↑/↓ y colores)
  - Valor de mercado actual
  - P&L No Realizado (monto y %)
  - Colores: verde (positivo), rojo (negativo)

#### Fase 4: Página de Asset (Día 6)

- [ ] **Vista detallada de asset**
  - Header con precio actual y cambio del día
  - Grid de métricas:
    - Market Cap (formateado + EUR)
    - P/E Ratio (trailing y forward)
    - Beta (riesgo)
    - Dividend Yield (% y monto anual)
  - Recomendación de analistas (badge de color)
  - Precio objetivo promedio
  - Número de analistas

#### Fase 5: Testing y Deploy (Días 7-8)

- [ ] **Testing**
  - Unit tests para PriceUpdater
  - Tests de conversión de divisas
  - Tests de formateo de números
  - Verificar cálculos de P&L

- [ ] **Deploy a producción**
  - Tag: v3.4.0
  - Documentar en SPRINT3_DISEÑO_BD.md
  - Actualizar TU_PLAN_MAESTRO.md

**Entregables**:
- ✅ Precios actuales mostrados en holdings
- ✅ Valor de mercado calculado correctamente
- ✅ P&L No Realizado visible
- ✅ Dashboard con métricas de mercado
- ✅ Botón de actualización funcional

**Checkpoint**: 
```bash
git tag v3.4.0-precios-tiempo-real
```

---

### 📊 SPRINT 4: Calculadora de Métricas Avanzadas (3 semanas)

**Objetivo**: Análisis financiero profundo con métricas de rendimiento y riesgo

**Duración**: 21 días

#### Semana 1: Métricas Básicas (Días 1-7)

- [ ] **P&L (Profit & Loss)**
  - P&L Realizado (de ventas ejecutadas)
  - P&L No Realizado (holdings actuales - ya implementado en Sprint 3F)
  - P&L Total por cuenta
  - P&L Total por asset
  - P&L por período (día, semana, mes, año, total)

- [ ] **ROI (Return on Investment)**
  - ROI simple: `(Valor actual - Inversión) / Inversión * 100`
  - ROI por cuenta
  - ROI por asset
  - ROI anualizado

- [ ] **Cost Basis y Capital**
  - Costo promedio por asset (ya implementado con FIFO)
  - Costo total invertido
  - Capital disponible por cuenta

#### Semana 2: Métricas Avanzadas (Días 8-14)

- [ ] **TWR (Time-Weighted Return)**
  - Rendimiento sin considerar timing de depósitos/retiros
  - Ideal para comparar con benchmarks
  - Cálculo por período

- [ ] **MWR / IRR (Money-Weighted Return / Internal Rate of Return)**
  - Rendimiento considerando timing de cash flows
  - Refleja decisiones reales del inversor
  - Cálculo con scipy/numpy

- [ ] **Sharpe Ratio**
  - `(Rendimiento - Tasa libre riesgo) / Volatilidad`
  - Rendimiento ajustado por riesgo
  - Usar tasa libre de riesgo de bono 10Y

- [ ] **Max Drawdown**
  - Máxima caída desde un pico
  - % de drawdown
  - Duración del drawdown

- [ ] **Volatilidad (Std Dev)**
  - Desviación estándar de rendimientos diarios
  - Anualizada (× √252)
  - Por asset y por portfolio total

#### Semana 3: Gráficos y Dashboard (Días 15-21)

- [ ] **Gráfico: Evolución del Portfolio** (ApexCharts line chart)
  - Eje X: Tiempo (seleccionable: 1M, 3M, 6M, 1Y, Todo)
  - Eje Y: Valor en EUR
  - Línea 1: Valor de mercado
  - Línea 2: Costo acumulado
  - Área sombreada: P&L (verde si +, rojo si -)

- [ ] **Gráfico: P&L Acumulado** (ApexCharts area chart)
  - Área verde fija: P&L Realizado
  - Área azul variable: P&L No Realizado
  - Línea total: Suma de ambos

- [ ] **Gráfico: Top Ganadores/Perdedores** (ApexCharts bar chart horizontal)
  - Top 5 assets con mejor P&L %
  - Top 5 assets con peor P&L %
  - Barras verdes (ganadores) y rojas (perdedores)

- [ ] **Gráfico: Comparación con Benchmarks** (ApexCharts line chart)
  - Tu portfolio vs S&P 500 / NASDAQ / IBEX 35
  - % de outperformance/underperformance
  - Seleccionable por período

- [ ] **Dashboard de Métricas**
  - Vista principal con cards de métricas clave
  - Tabla con métricas por asset (sorteable)
  - Tabla con métricas por cuenta
  - Exportar a CSV/Excel

- [ ] **Deploy**
  - Tag: v3.5.0

**Entregables**:
- ✅ Todas las métricas implementadas y testeadas
- ✅ 4 gráficos interactivos funcionando
- ✅ Dashboard completo de análisis
- ✅ Comparación con benchmarks

**Checkpoint**: 
```bash
git tag v3.5.0-metricas-avanzadas
```

---

### 📈 SPRINT 5: Actualización Automática de Precios (2 semanas)

**Objetivo**: Automatizar actualización de precios y mantener histórico

**Duración**: 14 días

#### Semana 1: Histórico y Automatización (Días 1-7)

- [ ] **Tabla PriceHistory**
  - Modelo con campos: asset_id, date, open, high, low, close, volume
  - Migración y relaciones
  - Índices para consultas rápidas

- [ ] **Cron Job con Flask-APScheduler**
  - Instalación y configuración
  - Job diario a las 18:00 UTC
  - Actualizar precios de todos los assets con holdings
  - Guardar snapshot diario en PriceHistory
  - Log de ejecuciones

- [ ] **Configuración de Auto-Update en UI**
  - Activar/desactivar en perfil de usuario
  - Elegir hora preferida
  - Notificación email al completar (opcional)

#### Semana 2: Histórico Visual y Cache (Días 8-14)

- [ ] **Gráfico de Precio Histórico** (ApexCharts candlestick)
  - OHLC (Open, High, Low, Close)
  - Volumen en barras debajo
  - Rangos: 1M, 3M, 6M, 1Y
  - Zoom y pan interactivo

- [ ] **Cache con Redis** (opcional pero recomendado)
  - Instalación de Redis
  - Flask-Caching setup
  - Cache de precios (TTL: 15 minutos)
  - Cache de tasas forex (TTL: 1 día)
  - Cache de totales dashboard (TTL: 5 minutos)

- [ ] **Optimización de Queries**
  - Índices en columnas frecuentes
  - joinedload() para evitar N+1
  - Paginación en listas largas

- [ ] **Deploy**
  - Tag: v3.6.0

**Entregables**:
- ✅ Actualización automática diaria funcionando
- ✅ Histórico de precios almacenado
- ✅ Gráfico candlestick por asset
- ✅ Cache implementado (si se eligió)

**Checkpoint**: 
```bash
git tag v3.6.0-auto-update
```

---

### 🎯 SPRINT 6: Diversificación y Watchlist (2 semanas)

**Objetivo**: Análisis de distribución de riesgo y seguimiento de assets

**Duración**: 14 días

#### Semana 1: Gráficos de Distribución (Días 1-7)

- [ ] **Gráfico: Distribución por Asset** (ApexCharts pie/donut chart)
  - % del valor total por cada asset
  - Colores diferenciados por asset
  - Click para ver detalles
  - Mostrar top 10 + "Otros"

- [ ] **Gráfico: Distribución por Sector** (ApexCharts pie chart)
  - Technology, Healthcare, Finance, Consumer, Energy, etc.
  - Identificar concentración sectorial
  - Colores temáticos por sector

- [ ] **Gráfico: Distribución por País** (ApexCharts pie chart o mapa)
  - USA, España, Hong Kong, UK, etc.
  - Análisis de geografía de riesgo
  - Opcional: Mapa interactivo con D3.js

- [ ] **Gráfico: Distribución por Tipo** (ApexCharts donut chart)
  - Acciones individuales
  - ETFs
  - REITs
  - Otros

#### Semana 2: Análisis y Watchlist (Días 8-14)

- [ ] **Análisis de Concentración de Riesgo**
  - Indicador visual:
    - Alta: >30% en un asset (rojo)
    - Media: 20-30% en un asset (amarillo)
    - Diversificado: <20% cada asset (verde)
  - Recomendaciones automáticas
  - Alertas de concentración

- [ ] **Watchlist (Lista de Seguimiento)**
  - Tabla `Watchlist` con campos:
    - user_id, asset_id, target_price, notes, created_at
  - CRUD de watchlist
  - Ver precios actuales sin tener holdings
  - Alertas cuando alcance precio objetivo
  - Notas personales por asset

- [ ] **Rebalanceo Sugerido**
  - Algoritmo de sugerencias de rebalanceo
  - Mantener % target por sector/país
  - Mostrar transacciones sugeridas

- [ ] **Deploy**
  - Tag: v3.7.0

**Entregables**:
- ✅ 4 gráficos de distribución funcionando
- ✅ Análisis de concentración automático
- ✅ Watchlist funcional con alertas
- ✅ Sugerencias de rebalanceo

**Checkpoint**: 
```bash
git tag v3.7.0-diversificacion-watchlist
```

---

### 🔔 SPRINT 7: Alertas y Conversión Automática EUR (2 semanas)

**Objetivo**: Sistema de notificaciones y conversión automática de divisas

**Duración**: 14 días

#### Semana 1: Alertas (Días 1-7)

- [ ] **Alertas de Precio**
  - Tabla `PriceAlert`: user_id, asset_id, condition (above/below), price, is_active, notification_method
  - CRUD de alertas
  - Verificación diaria en cron job
  - Email cuando se dispara
  - Notificación en app (badge contador)
  - Historial de alertas disparadas

- [ ] **Calendario de Dividendos**
  - Tabla `DividendCalendar`: asset_id, ex_dividend_date, payment_date, dividend_amount, frequency
  - Integración con Yahoo Finance (calendar data)
  - Vista mensual/anual
  - Destacar próximos 7 días
  - Estimación de ingresos futuros por dividendos

- [ ] **Alertas de Eventos Corporativos**
  - Cambio en recomendación de analistas
  - Dividendo anunciado
  - Cambios significativos en precio (±10% en un día)
  - Email opcional al usuario

#### Semana 2: Conversión Automática EUR (Días 8-14)

- [ ] **API de Forex (ExchangeRate-API)**
  - Integración con https://www.exchangerate-api.com/
  - Gratis: 1,500 requests/mes
  - Función `get_forex_rate(from_currency, to_currency='EUR')`

- [ ] **Tabla ForexRate (cache)**
  - Campos: from_currency, to_currency, rate, date, created_at
  - Actualización diaria con cron job
  - Histórico de tasas de cambio

- [ ] **Conversión Automática en Toda la App**
  - Reemplazar conversiones hardcoded
  - Actualizar PriceUpdater service
  - Mostrar valor en moneda original + EUR
  - Formato: "1,234.56 USD (1,137.50 EUR)"

- [ ] **Deploy**
  - Tag: v3.8.0

**Entregables**:
- ✅ Sistema de alertas de precio funcional
- ✅ Calendario de dividendos completo
- ✅ Conversión automática EUR en toda la app
- ✅ Notificaciones por email funcionando

**Checkpoint**: 
```bash
git tag v3.8.0-alertas-forex
```

---

### 🧪 SPRINT 8: Testing y Optimización (2 semanas)

**Objetivo**: Asegurar calidad, cobertura de tests y performance óptimo

**Duración**: 14 días

#### Semana 1: Testing (Días 1-7)

- [ ] **Tests Unitarios (pytest)**
  - Modelos: Asset, PortfolioHolding, Transaction, etc.
  - Servicios: PriceUpdater, Importer, FIFO, Metrics
  - Utilidades: formatters, converters, date helpers
  - Target: 80%+ coverage

- [ ] **Tests de Integración**
  - Flujo completo: Login → Import CSV → View Holdings → Update Prices
  - Flujo de compra/venta: Buy → Sell → P&L correcto
  - Flujo de dividendos: Recibir dividendo → Actualizar holdings
  - Alertas: Crear alerta → Disparar → Notificación

- [ ] **Tests de Performance**
  - Benchmarking de queries críticas
  - Verificar N+1 queries
  - Load testing de endpoints

#### Semana 2: Optimización (Días 8-14)

- [ ] **Optimización de Base de Datos**
  - Añadir índices a columnas frecuentes:
    - assets.symbol
    - assets.isin
    - transactions.transaction_date
    - price_history.date
  - Analizar query plans (EXPLAIN)
  - Optimizar queries lentas

- [ ] **Logging y Monitoring**
  - Setup logging con Python logging
  - Logs en archivo: logs/app.log
  - Niveles: INFO, WARNING, ERROR
  - Rotación de logs (log rotation)
  - Monitoreo de errores:
    - Error rate > 5%
    - Response time > 2s
    - Uso de disco > 80%

- [ ] **Optimización de Frontend**
  - Minificación CSS/JS en producción
  - Lazy loading de imágenes
  - Comprimir assets estáticos
  - CDN para librerías (ApexCharts, TailwindCSS)

- [ ] **Documentación Técnica**
  - API documentation (docstrings completos)
  - README actualizado
  - Guías de deployment
  - Troubleshooting guide

- [ ] **Deploy Final**
  - Tag: v3.9.0
  - Backup completo de producción
  - Validación exhaustiva

**Entregables**:
- ✅ Cobertura de tests > 80%
- ✅ Performance < 1s response time
- ✅ Logging y monitoring activo
- ✅ Documentación completa
- ✅ Sistema optimizado y estable

**Checkpoint**: 
```bash
git tag v3.9.0-testing-optimization
```

**🎉 MILESTONE 2 COMPLETADO**: Portfolio Management Completo (3.5 meses)

---

### 💰 SPRINT 9: Planificación Financiera y Cash Flow Forecast (3 semanas)

**Objetivo**: Sistema de planificación de gastos futuros, proyección de flujo de caja y análisis de capacidad de endeudamiento

**Duración**: 21 días

**Contexto**: 
Este sprint permite al usuario planificar gastos futuros deseados (viajes, caprichos, compras grandes) y conocer en todo momento:
- El dinero que tendrá disponible en cualquier fecha futura
- Su margen de maniobra para nuevos gastos
- Su capacidad máxima de endeudamiento mensual y a 12 meses
- Si puede permitirse un gasto específico y cómo financiarlo (cash propio vs crédito)

#### Semana 1: Backend - Gastos Planificados (Días 1-7)

- [ ] **Modelo de Gastos Planificados**
  - `app/models/planned_expense.py`
  - Campos:
    - `name` (str): Nombre del gasto (ej: "Viaje a Japón", "MacBook Pro")
    - `amount` (Decimal): Cantidad en EUR
    - `target_date` (date): Fecha objetivo para realizar el gasto
    - `priority` (enum): ALTA, MEDIA, BAJA
    - `category_id` (FK): Vinculación con categorías de gastos existentes
    - `expense_type` (enum): CAPRICHO, VIAJE, COMPRA_GRANDE, INVERSION, OTRO
    - `status` (enum): PLANIFICADO, EN_AHORRO, COMPLETADO, CANCELADO, POSPUESTO
    - `financing_type` (enum): CASH_PROPIO, CREDITO, MIXTO
    - `notes` (text): Descripción adicional
    - `created_at`, `updated_at`
  - Relaciones: Vinculación con `ExpenseCategory` y `User`
  - Métodos:
    - `calculate_monthly_saving_required()`: Cuánto ahorrar por mes
    - `is_affordable()`: ¿Puede permitírselo con flujo de caja actual?
    - `mark_as_completed()`: Marcar como realizado
  - Tests unitarios completos

- [ ] **Servicio de Proyección de Flujo de Caja**
  - `app/services/cash_flow_projection_service.py`
  - Métodos:
    - `project_balance(months=12)`: Proyección de saldo mes a mes
      - Input: mes objetivo
      - Output: array de {fecha, saldo_proyectado, ingresos, gastos_recurrentes, gastos_planificados}
    - `calculate_monthly_income()`: Ingresos recurrentes promedio
    - `calculate_monthly_expenses()`: Gastos recurrentes promedio
    - `calculate_monthly_margin()`: Margen mensual disponible
    - `get_critical_months()`: Meses con saldo negativo proyectado
    - `get_balance_at_date(target_date)`: Saldo proyectado en fecha específica
  - Integración con:
    - ✅ Ingresos recurrentes (Sprint 2)
    - ✅ Gastos recurrentes (Sprint 2)
    - 🆕 Gastos planificados
    - 🆕 Saldo actual en cuentas bancarias (futuro)
  - Tests de integración

- [ ] **Servicio de Capacidad de Endeudamiento**
  - `app/services/debt_capacity_service.py`
  - Métodos:
    - `calculate_debt_capacity()`: Capacidad máxima de endeudamiento seguro
      - Regla: Max 30-40% de ingresos mensuales
      - Output: {max_monthly_payment, max_total_debt, current_utilization}
    - `calculate_available_margin()`: Margen mensual después de gastos
    - `project_debt_capacity_12m()`: Proyección a 12 meses
    - `check_affordability(amount, target_date)`: ¿Puede permitirse este gasto?
    - `suggest_financing(amount, target_date)`: Recomendar fuente de financiación
      - Cash propio disponible
      - Ahorro mensual requerido
      - Crédito necesario (si aplica)
  - Cálculos:
    - **Margen Mensual** = Ingresos - Gastos Recurrentes - Cuotas Deuda Actual
    - **Endeudamiento Max Seguro** = Ingresos × 0.35 (configurable)
    - **Cash Disponible** = Saldo Cuentas Bancarias + Portfolio Líquido (efectivo)
  - Tests exhaustivos

#### Semana 2: Backend - Simulador y API (Días 8-14)

- [ ] **Simulador "What-if"**
  - `app/services/what_if_simulator.py`
  - Método principal: `simulate_expense(amount, target_date, financing_type)`
  - Output:
    - `is_affordable` (bool): ¿Puede permitírselo?
    - `impact_on_margin` (dict): Impacto en margen mensual
    - `financing_recommendation` (dict):
      - `cash_available` (Decimal): Cash propio disponible
      - `savings_needed` (Decimal): Ahorro mensual requerido
      - `months_to_save` (int): Meses necesarios para ahorrar
      - `credit_needed` (Decimal): Crédito necesario (si aplica)
    - `risk_level` (enum): BAJO, MEDIO, ALTO, CRITICO
    - `warnings` (list): Alertas de riesgo
  - Escenarios:
    - Mejor caso: Solo cash propio
    - Caso realista: Ahorro mensual
    - Peor caso: Requiere crédito
  - Tests de casos edge

- [ ] **Rutas y Forms**
  - `app/routes/financial_planning.py`
  - Rutas:
    - `GET /planning/expenses` - Lista de gastos planificados
    - `GET /planning/expenses/new` - Formulario nuevo gasto
    - `POST /planning/expenses` - Crear gasto planificado
    - `GET /planning/expenses/<id>/edit` - Editar
    - `POST /planning/expenses/<id>/update` - Actualizar
    - `POST /planning/expenses/<id>/delete` - Eliminar
    - `POST /planning/expenses/<id>/complete` - Marcar como completado
    - `GET /planning/dashboard` - Dashboard de planificación
    - `POST /planning/simulate` - Simulador what-if (Ajax)
    - `GET /planning/api/projection` - API proyección JSON
  - `app/forms/planned_expense_forms.py`
  - Validaciones:
    - Fecha objetivo no en el pasado
    - Monto > 0
    - Prioridad válida
  - Tests de integración

#### Semana 3: UI y Gráficos (Días 15-21)

- [ ] **Dashboard de Planificación Financiera** (`/planning/dashboard`)
  - Sección 1: **KPIs Principales**
    - 💰 Saldo Actual Total (cuentas bancarias + portfolio líquido)
    - 📊 Margen Mensual Disponible (ingresos - gastos recurrentes)
    - 📈 Capacidad de Endeudamiento (% utilizado / máximo seguro)
    - 🎯 Total Gastos Planificados (suma de todos los pending)
  - Sección 2: **Gráficos** (Chart.js)
    - **Gráfico 1: Proyección de Saldo a 12 Meses**
      - Línea: Saldo proyectado mes a mes
      - Zona verde: Saldo positivo
      - Zona roja: Saldo negativo (alerta)
      - Marcadores: Gastos planificados en timeline
    - **Gráfico 2: Margen Disponible vs Comprometido**
      - Barra apilada por mes
      - Verde: Margen disponible
      - Naranja: Comprometido en gastos planificados
      - Rojo: Sobreendeudamiento
    - **Gráfico 3: Distribución de Gastos Planificados**
      - Pie chart por tipo (Capricho, Viaje, Compra Grande, etc.)
      - Muestra distribución de prioridades
  - Sección 3: **Alertas y Avisos**
    - 🚨 CRÍTICO: Gastos planificados exceden capacidad
    - ⚠️ ADVERTENCIA: Meses con saldo proyectado negativo
    - 💡 INFO: Recomendaciones de ahorro
  - Estilo: Dashboard completo, elegante, con iconos y colores

- [ ] **Página de Gastos Planificados** (`/planning/expenses`)
  - Tabla con todas las columnas:
    - Nombre
    - Monto (EUR)
    - Fecha Objetivo
    - Prioridad (badge de color)
    - Tipo (badge)
    - Estado (badge: Planificado, En ahorro, Completado)
    - Financiación (Cash, Crédito, Mixto)
    - Ahorro mensual requerido (calculado)
    - Acciones (Editar, Eliminar, Completar, Simular)
  - Filtros:
    - Por estado
    - Por prioridad
    - Por tipo
    - Por fecha (próximos 3 meses, 6 meses, año)
  - Ordenación por cualquier columna
  - Búsqueda en tiempo real
  - Botón destacado: "➕ Nuevo Gasto Planificado"

- [ ] **Modal de Simulador "What-if"**
  - Inputs:
    - Monto del gasto (EUR)
    - Fecha objetivo
    - Tipo de financiación deseada
  - Output visual:
    - ✅ / ❌ ¿Puedes permitírtelo?
    - 📊 Gráfico de impacto en saldo proyectado
    - 💰 Financiación recomendada:
      - Cash disponible: XXX€
      - Ahorro mensual necesario: XXX€
      - Meses para ahorrar: X
      - Crédito necesario: XXX€ (si aplica)
    - 🎯 Nivel de riesgo: Badge de color
    - ⚠️ Advertencias específicas
  - Botón: "Guardar como Gasto Planificado"
  - Ajax: Sin recarga de página

- [ ] **Formulario de Nuevo/Editar Gasto Planificado**
  - Campos:
    - Nombre del gasto
    - Monto (EUR)
    - Fecha objetivo (date picker)
    - Prioridad (select: Alta/Media/Baja)
    - Categoría (select de categorías existentes)
    - Tipo (select: Capricho, Viaje, Compra Grande, etc.)
    - Financiación (select: Cash Propio, Crédito, Mixto)
    - Notas (textarea opcional)
  - Validación en tiempo real
  - Preview de "Ahorro mensual requerido" calculado automáticamente
  - Botones: Guardar, Cancelar

- [ ] **Deploy y Validación**
  - Migraciones de BD
  - Tests E2E del flujo completo:
    1. Crear gasto planificado → Ver en dashboard → Simular → Completar
    2. Proyección de saldo → Verificar cálculos correctos
    3. Capacidad de endeudamiento → Alertas funcionando
  - Tag: v4.0.0-financial-planning
  - Deploy a producción
  - Validación exhaustiva

**Entregables**:
- ✅ Gestión completa de gastos planificados/deseados
- ✅ Proyección de flujo de caja a 12 meses (mes a mes)
- ✅ Análisis de capacidad de endeudamiento
- ✅ Simulador "What-if" interactivo
- ✅ Dashboard de planificación con 3 gráficos
- ✅ Sistema de alertas y límites
- ✅ Integración con gastos/ingresos recurrentes (Sprint 2)

**Beneficios para el Usuario**:
- 🎯 Saber exactamente cuánto dinero tendrá en cualquier fecha futura
- 💰 Planificar caprichos y compras grandes sin remordimientos
- 📊 Conocer su margen de maniobra en todo momento
- 🚨 Evitar sobreendeudamiento con alertas tempranas
- 🧠 Tomar decisiones financieras informadas con simulaciones

**Checkpoint**: 
```bash
git tag v4.0.0-financial-planning
```

**Dependencias**:
- ✅ Sprint 2 (Gastos e Ingresos recurrentes) - COMPLETADO
- 🔜 Integración futura con:
  - Saldo de cuentas bancarias (futuro Sprint 10: Cuentas Bancarias)
  - Portfolio líquido (ya disponible en Sprint 3)

---

### 🏦 SPRINT 11-12: Deudas (Semana 21-24)

**Objetivo**: Gestión completa de deudas y tracking de cuotas

#### Semana 21-22: Backend

- [ ] **Modelos de deuda**
  - `app/models/debt_plan.py`
  - Cálculo de cuotas restantes
  - Progreso de pago
  - Soporte hipotecas
  - Tests de cálculos

- [ ] **Servicios**
  - `app/services/debt_service.py`
  - Cálculo de amortización
  - Proyecciones de pago
  - Tests

#### Semana 23-24: UI y Deploy

- [ ] **UI de deudas**
  - Lista de deudas activas
  - Progreso visual (progress bars)
  - Calculadora de deuda
  - Vinculación con categorías de gastos
  - Gráfico de evolución de deuda

- [ ] **Deploy y validación**

**Entregables**:
- ✅ Gestión de deudas completa
- ✅ Tracking de cuotas
- ✅ Visualizaciones claras

**Checkpoint**: 
```bash
git tag v0.8-debts
```

**🎉 MILESTONE 2 COMPLETADO**: Sistema de Inversiones y Deudas (4.5 meses)

---

### 🪙 SPRINT 13-14: Criptomonedas (Semana 25-28)

[Detalles similares a sprints anteriores...]

### 🏠 SPRINT 15-16: Bienes Raíces (Semana 29-32)

[Detalles similares...]

### 🥇 SPRINT 17-18: Metales + Pensiones (Semana 33-36)

[Detalles similares...]

### 📊 SPRINT 19-20: Benchmarks y Reportes (Semana 37-40)

[Detalles similares...]

### 🔔 SPRINT 21: Alertas + Polish Final (Semana 41-44)

[Detalles similares...]

---

## 🔄 WORKFLOW: Desarrollo → Producción

### Proceso Estándar por Feature

```bash
# 1. DESARROLLO LOCAL
cd /home/ssoo/www/followup

# Crear rama para feature
git checkout -b feature/nombre-feature

# Desarrollar y testear
# ... código ...
pytest tests/ -v --cov=app

# Commit
git add .
git commit -m "feat: descripción del feature"

# 2. MERGE A MAIN
git checkout main
git merge feature/nombre-feature
git push origin main

# 3. DEPLOY A PRODUCCIÓN
# Conectar a producción
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92

# En producción
cd /home/ubuntu/www/followup
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head  # Si hay migraciones
sudo systemctl restart followup

# 4. VALIDAR
# Abrir https://followup.fit/
# Probar la nueva funcionalidad
# Verificar logs: sudo journalctl -u followup -f

# 5. TAG SI ES HITO IMPORTANTE
git tag v0.X-nombre
git push origin --tags
```

### Script de Deploy Automatizado

Crear `scripts/deploy.sh`:
```bash
#!/bin/bash
# Ver WORKFLOW_DEV_A_PRODUCCION.md para detalles
```

---

## ✅ CHECKLIST DE PROGRESO

### Semana Actual: **Semana 0 - Setup**

```
SPRINT 0: Setup Inicial
├── [ ] Backup código actual
├── [ ] Configurar Git
├── [ ] Crear estructura de proyecto
├── [ ] Setup PostgreSQL (dev)
├── [ ] Instalar dependencias base
├── [ ] Setup TailwindCSS
├── [ ] Limpiar y configurar producción
└── [ ] Primer commit

SPRINT 1: Autenticación (Próximo)
├── [ ] Modelo User
├── [ ] Rutas auth
├── [ ] Templates con diseño
├── [ ] Tests (70%+)
├── [ ] Deploy producción
└── [ ] Tag v0.1-auth
```

---

## 📝 NOTAS IMPORTANTES

### Antes de Cada Deploy
1. ✅ Tests pasando (70%+ coverage)
2. ✅ Probado localmente
3. ✅ Commit con mensaje descriptivo
4. ✅ Backup de BD en producción (antes de migrations)

### Cada Viernes
- Review de la semana
- Actualizar este documento
- Planificar próxima semana
- Backup completo de BD

### Recursos de Ayuda
- Documentos de referencia: FORMULAS_Y_CALCULOS.md, ANALISIS_COMPLETO_FUNCIONALIDADES.md
- Stack Overflow, Flask docs, TailwindCSS docs
- ChatGPT/Claude para debugging

---

## 🎯 PRÓXIMOS PASOS INMEDIATOS

1. **AHORA**: Leer este documento completo
2. **HOY**: Ejecutar Sprint 0 (3 días)
3. **ESTA SEMANA**: Sprint 1 - Autenticación
4. **PRÓXIMA SEMANA**: Sprint 2 - Cuentas Bancarias

---

**Última actualización**: 5 Octubre 2025  
**Estado**: 📝 Plan inicial creado  
**Progreso**: 0% (0/44 semanas completadas)

---

## 📞 CONTACTO Y SOPORTE

Si algo no funciona o necesitas ayuda:
1. Revisar documentación relevante
2. Google el error específico
3. Preguntar a IA con contexto completo
4. Documentar la solución en este archivo

**¡Vamos a construir algo increíble!** 🚀

