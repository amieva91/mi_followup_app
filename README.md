# FollowUp - Personal Financial Management

Sistema completo de gestión financiera personal.

## ✅ Estado Actual (12 Nov 2025) - v4.3.0

**Funcionalidades Implementadas:**
- ✅ **Sprint 0 - Arquitectura Base** - Configuración inicial, estructura modular
- ✅ **Sprint 1 - Autenticación** - Registro, Login, Reset Password
- ✅ **Sprint 2 - Gastos e Ingresos** 
  - Categorías jerárquicas con padre/hijo
  - Gastos y ingresos puntuales y recurrentes
  - Generación automática de instancias históricas
  - Edición y eliminación de series completas
  - Emoji picker interactivo
- ✅ **Sprint 3 - CSV Processor & Portfolio Management** (v3.5.0 - COMPLETADO)
  - Base de datos completa (9 modelos: 8 portfolio + AssetRegistry global)
  - CRUD de cuentas de broker con eliminación destructiva
  - Entrada manual de transacciones (BUY/SELL/DIVIDEND/FEE/DEPOSIT/WITHDRAWAL)
  - Parser CSV para IBKR (formato jerárquico + extracción ISIN)
  - Parser CSV para DeGiro Transacciones (lectura por índices, monedas correctas)
  - Parser CSV para DeGiro Estado de Cuenta (dividendos/comisiones/FX) **[Fixed v3.3.5]**
  - Consolidación unificada de dividendos (3-4 líneas relacionadas)
  - **AssetRegistry - Base de datos global compartida**:
    - Cache de mapeos ISIN → Symbol, Exchange, MIC, Yahoo Suffix
    - Alimentación automática desde CSVs (IBKR aporta symbol/exchange completos)
    - Enriquecimiento automático con OpenFIGI para assets sin symbol
    - Actualización inteligente (reutiliza datos existentes)
    - Contador de uso compartido (usage_count)
  - Importador V2 con progreso en tiempo real
  - Detección inteligente de duplicados (snapshot entre archivos)
  - Filtrado de transacciones FX (Forex)
  - **FIFO robusto con posiciones cortas temporales**
  - Normalización de símbolos (IGC/IGCl → IGC)
  - Cálculo de P&L realizadas y no realizadas
  - Interfaz web para subir múltiples CSV con drag & drop
  - Dashboard de portfolio con holdings y transacciones
  - **Búsqueda y edición de transacciones** con filtros combinables + sorting
  - **Vista unificada de holdings** por asset (múltiples brokers)
  - Import de múltiples archivos simultáneos
  - Recálculo automático de holdings tras edición
  - **Formato europeo** en todos los números (1.234,56)
  - **Visualización mejorada**: Type • Currency • ISIN
  - **Gestión completa de AssetRegistry**:
    - Interfaz dedicada con búsqueda, filtros y ordenación (columnas ordenables)
    - Edición y eliminación de registros
    - Estadísticas de enriquecimiento (total/enriched/pending)
    - Enriquecimiento manual (OpenFIGI o Yahoo URL) desde modal
    - Acceso directo desde transacciones
    - Estado correcto (solo requiere symbol, MIC opcional)
  - **MappingRegistry - Sistema de mapeos editables**:
    - Gestión web de todos los mapeos (MIC→Yahoo, Exchange→Yahoo, DeGiro→IBKR)
    - CRUD completo con búsqueda y filtros
    - Activación/desactivación de mapeos
    - Interfaz accesible desde AssetRegistry
  - **Fixes de estabilidad (v3.3.4)**:
    - Progreso de importación: primer archivo ahora visible en "Completados"
    - Conteo correcto de archivos procesados (5/5 en lugar de 4/5)
    - Botones de enriquecimiento funcionales en edición de transacciones
    - Feedback visual mejorado con banners detallados
  - **Sprint 3 Final - Precios en Tiempo Real (v3.4.0)**:
    - Integración completa con Yahoo Finance (15 métricas avanzadas)
    - Market Cap, P/E Ratios, Beta, Dividend Yield, Analyst Recommendations
    - Actualización manual de precios con progress bar en tiempo real
    - Dashboard con valores actuales y P&L calculado
    - Página detallada por asset con 5 tabs (Métricas, Valoración, Riesgo, Análisis, Transacciones)
    - Cálculo automático de P&L no realizado con precios actuales
  - **Conversión de Divisas (v3.5.0)**:
    - API del BCE con cache de 24 horas (166 monedas)
    - Página dedicada de tasas de conversión (`/portfolio/currencies`)
    - Conversión automática a EUR en dashboard y holdings
    - Display de valor en EUR + moneda local
    - Actualización manual de tasas con botón dedicado
    - **FIX CRÍTICO**: Corrección de cálculo de "Coste Total" (ahora convierte a EUR antes de sumar)
    - Holdings page con ancho ampliado (95%) para más columnas
  - **Sprint 3 - Mejoras Finales (v3.6.0 - 7 Nov 2025)**:
    - ✅ **Optimizaciones de rendimiento**:
      - Limpieza de 15 scripts temporales del repositorio
      - Mensaje informativo cuando import está vacío (duplicados detectados)
      - Timeouts en actualización de precios (10s/request, 180s máximo total)
      - Paginación de 100 transacciones por página con controles completos
    - ✅ **Mejoras de UX**:
      - Búsqueda en tiempo real sin botón submit (AssetRegistry + Transacciones)
      - Indicador de última sincronización en dashboard (fecha/hora última transacción)
      - Guías dinámicas para obtener CSV según broker (DeGiro: 2 archivos | IBKR: Activity Statement)
      - Columna "Peso %" añadida en dashboard (cálculo automático por posición)
      - Columnas ordenables en Dashboard y Holdings (↑↓⇅ sin recarga)
      - **Ancho 92% unificado** en toda la aplicación (16 páginas: Portfolio, Gastos, Ingresos, General)
    - ✅ **Correcciones críticas**:
      - Fix error paginación transacciones (generator → dict)
      - Eliminado doble emoji en botón "Actualizar Precios"
      - Eliminado mensaje innecesario de sincronización en AssetRegistry
      - Navbar alineado al 92% para consistencia visual completa
- ✅ **Sprint 4 - Métricas Avanzadas (EN PROGRESO - 9 Nov 2025)**
  - ✅ **HITO 1: Métricas Básicas (v4.0.0-beta - COMPLETADO 8 Nov)**:
    - **8 Métricas implementadas**:
      - P&L Realizado (posiciones cerradas, cálculo con FIFO robusto)
      - P&L No Realizado (posiciones abiertas)
      - P&L Total (Realizado + No Realizado + Dividendos - Comisiones)
      - ROI (Return on Investment sobre capital depositado)
      - Leverage/Dinero Prestado (con detección de cash disponible)
      - Valor Total Cartera (posiciones actuales a precio de mercado)
      - Valor Total Cuenta de Inversión (incluye cash/apalancamiento)
      - Peso % por Posición (identificación de concentración)
    - **Dashboard reorganizado**: Métricas Globales primero, luego Portfolio
    - **Tooltips explicativos** en todas las métricas
    - **Desgloses detallados** en todos los indicadores (ver cálculo completo)
    - **Página P&L by Asset**: Histórico de ganancias/pérdidas por activo
      - Filtros en tiempo real + ordenación por columnas
      - Indicador de activos en cartera vs cerrados
      - Contador de dividendos por asset
    - **Ordenación numérica universal**: Todas las tablas (Dashboard, Holdings, PL by Asset, Transactions)
    - **Fixes críticos**:
      - P&L Realizado reescrito con FIFOCalculator (antes: 5% arbitrario ❌)
      - Leverage: incluye P&L Realizado + P&L No Realizado en dinero usuario
      - Cash disponible vs Apalancamiento: lógica corregida (solo cash si leverage < 0)
      - Brokers en holdings unificadas: ahora muestra correctamente todos los brokers
      - Holdings: todas las posiciones mostradas (límite de 15 eliminado)
      - P&L pre-calculado en backend (no filtros en template)
  - ✅ **HITO 2: Modified Dietz Method (v4.0.0-beta - COMPLETADO 9 Nov)**:
    - **Portfolio Valuation Service** (`app/services/metrics/portfolio_valuation.py`):
      - `get_value_at_date()`: Valoración del portfolio en cualquier fecha histórica
      - `get_user_money_at_date()`: Dinero real del usuario (sin apalancamiento)
      - Reconstrucción histórica de posiciones con FIFO
      - Soporte para precios actuales vs precios históricos
    - **Modified Dietz Calculator** (`app/services/metrics/modified_dietz.py`):
      - Estándar GIPS (Global Investment Performance Standards)
      - `calculate_return()`: Rentabilidad de un período específico
      - `calculate_annualized_return()`: Rentabilidad anualizada
      - `calculate_ytd_return()`: Rentabilidad año actual (YTD)
      - `get_all_returns()`: Wrapper para dashboard
      - Fórmula: `R = (VF - VI - CF) / (VI + Σ(CF_i × W_i))`
      - Cash flows externos: Solo DEPOSIT/WITHDRAWAL (dividendos son ingresos internos)
    - **Nueva card en Dashboard**: 💎 Rentabilidad (Modified Dietz)
      - Rentabilidad Anualizada (con años de inversión)
      - Rentabilidad Total (%)
      - Rentabilidad YTD (año actual)
      - Ganancia Absoluta (EUR)
      - Días de inversión
    - **Validación matemática exitosa**:
      - Ganancia Modified Dietz: 52.472 EUR
      - P&L Total del sistema: 52.562 EUR
      - **Error: 0,17%** ✅ (dentro del margen aceptable)
    - **Ventajas del Modified Dietz**:
      - NO requiere precios históricos (solo necesita valor inicial y final)
      - Pondera cash flows por tiempo (elimina efecto de timing de deposits/withdrawals)
      - Comparable con benchmarks y otros portfolios
      - Estándar de la industria financiera
  - ✅ **Refinements: Performance & UX (v4.1.0-beta - COMPLETADO 10 Nov)**:
    - **Cache de Métricas** (Mejora de Performance):
      - Nueva tabla `MetricsCache` con TTL de 24 horas
      - Invalidación automática en transacciones/precios/imports
      - Botón manual "♻️ Recalcular" en dashboard
      - Badge visual "⚡ Cache" cuando se usa cache
      - Reducción de tiempo de carga del dashboard: 2-3s → 0.3s
    - **Fixes Críticos**:
      - CSRF token en botón "Actualizar Precios" (corregido error 400)
      - Funcionalidad "🗑️ Eliminar Transacciones" con confirmación
      - UX mejorada: Campo integrado para Yahoo URL (en vez de prompt nativo)
      - Meta tag CSRF en `layout.html` para todos los formularios
      - Recalculo automático de holdings tras eliminar transacción
      - Mensajes de confirmación mejorados
  - ✅ **UX Avanzadas: Transacciones Manuales (v4.2.0-beta - COMPLETADO 10 Nov)**:
    - **Auto-selección en SELL**:
      - Dropdown inteligente para seleccionar activos del portfolio
      - Filtro opcional por cuenta (IBKR, DeGiro, o todas)
      - Auto-completado de Symbol, ISIN, Divisa, Nombre, Tipo
      - Botón "Máximo" para cantidad disponible
      - Actualización automática de la cuenta al seleccionar holding
    - **Autocompletado en BUY**:
      - Búsqueda en tiempo real desde AssetRegistry global
      - Auto-fill de todos los campos (Symbol, ISIN, Currency, etc.)
      - Experiencia sin interrupciones (no bloquea escritura)
    - **Venta por quiebra**:
      - Soporte para precio = 0€ (bankruptcy)
      - Eliminación automática de holdings con cantidad = 0
      - Integración con FIFOCalculator para P&L correcto
    - **Botones de enriquecimiento**:
      - "Enriquecer con OpenFIGI": Habilitado solo en modo EDIT
      - "Desde URL de Yahoo": Habilitado en NEW y EDIT
      - Tooltips explicativos para estado deshabilitado
    - **Redirección mejorada**:
      - BUY/SELL → redirige a `/portfolio/holdings` (antes: transactions)
    - **Fixes críticos**:
      - Corregido `KeyError: 'avg_price'` → `average_buy_price` en FIFO
      - Corregido modal de actualización de precios: `data.updated` → `data.success`
      - Holdings API optimizada con filtro por account_id
  - ✅ **HITO 3: Gráficos de Evolución Histórica (v4.3.0 - COMPLETADO 12 Nov)**:
    - **Nueva página `/portfolio/performance`** con 5 gráficos de evolución mensual
    - **Gráfico 1: Valor Real de la Cuenta** (sin apalancamiento, con precio actual en último punto)
    - **Gráfico 2: Rentabilidad Acumulada (Modified Dietz)** (% acumulado histórico)
    - **Gráfico 3: Apalancamiento/Cash** (verde=cash positivo, rojo=leverage negativo)
    - **Gráfico 4: Capital Invertido Neto** (deposits - withdrawals acumulados)
    - **Gráfico 5: P&L Total Acumulado** (realizado + no realizado + dividendos - comisiones)
    - **Backend**: `PortfolioEvolutionService` con integración FIFO para P&L histórico
    - **Frontend**: Chart.js 4.0 con formateo europeo y tooltips informativos
    - **Correcciones críticas**:
      - Conversión EUR universal en todos los cálculos históricos
      - Fórmula de leverage corregida: `user_money - holdings_value`
      - P&L No Realizado solo en último punto (HOY), histórico solo P&L Realizado
      - Colores corregidos: verde para cash, rojo para apalancamiento
  - 🚧 **HITO 4: Comparación con Benchmarks (PENDIENTE)**:
    - Integración con Yahoo Finance para índices (S&P 500, NASDAQ, etc.)
    - Gráfico comparativo de rentabilidad vs benchmarks
    - Tabla comparativa (Anualizada, YTD, Total)
- ✅ **Dashboard** - KPIs en tiempo real (ingresos/gastos/balance mensual + portfolio completo con 9 métricas + Modified Dietz)
- ✅ **Sistema desplegado** - Funcionando en https://followup.fit/

## 🚀 Entornos

### Desarrollo (WSL)
- **Directorio**: `/home/ssoo/www`
- **Usuario**: `ssoo`
- **Base de datos**: SQLite (local)
- **Puerto**: 5000

### Producción
- **Servidor**: `ubuntu@140.238.120.92` (followup)
- **Directorio**: `/home/ubuntu/www`
- **Dominio**: https://followup.fit/
- **Base de datos**: SQLite
- **Puerto**: 5000
- **Servicio**: `followup.service` (systemd)
- **Usuario**: `ubuntu:www-data`

## 📦 Stack Tecnológico

- **Backend**: Flask + SQLAlchemy
- **Frontend**: Jinja2 + TailwindCSS + Alpine.js + HTMX
- **Base de datos**: SQLite (desarrollo) / PostgreSQL (futuro)
- **Testing**: pytest
- **Deployment**: systemd service

## 🏗️ Arquitectura

```
followup/
├── app/                    # Aplicación principal
│   ├── __init__.py        # Factory pattern
│   ├── models/            # Modelos de base de datos
│   ├── routes/            # Blueprints (auth, portfolio, etc)
│   ├── services/          # Lógica de negocio
│   ├── utils/             # Utilidades y helpers
│   ├── static/            # CSS, JS, imágenes
│   └── templates/         # Templates Jinja2
├── tests/                 # Tests
├── docs/                  # Documentación
├── config.py              # Configuración
├── requirements.txt       # Dependencias
└── run.py                 # Entry point
```

## 🔧 Setup Inicial

### 1. Crear entorno virtual
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/WSL
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Variables de entorno
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

### 4. Inicializar base de datos
```bash
flask db upgrade
```

### 5. Ejecutar (desarrollo)
```bash
python run.py
```

## 📚 Documentación

### 📄 Documentos Principales (Raíz)

1. **`README.md`** - Este archivo (estado actual, setup, arquitectura)
2. **`TU_PLAN_MAESTRO.md`** - Plan general del proyecto con todos los sprints
3. **`WORKFLOW_DEV_A_PRODUCCION.md`** - Proceso de deploy y Git workflow
4. **`DESIGN_SYSTEM.md`** - Sistema de diseño y componentes UI
5. **`SPRINT4_METRICAS_AVANZADAS.md`** - Sprint actual (en progreso)

### 📁 Documentación Organizada (`docs/`)

- **`docs/sprints/`** - Sprints completados (Sprint 3 final)
- **`docs/sesiones/`** - Bitácora de sesiones de trabajo
- **`docs/archivo/`** - Análisis inicial y propuestas
- **`docs/migraciones/`** - Documentos de migraciones históricas
- **`docs/indices/`** - Índices de documentación

## 📝 Git Workflow

```bash
# Desarrollo
git checkout develop
git add .
git commit -m "feat: descripción"
git push origin develop

# Producción (solo después de aprobar)
git checkout main
git merge develop
git push origin main
```

## 🚢 Deploy a Producción

```bash
# En servidor de producción
cd ~/www
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
flask db upgrade
sudo systemctl restart followup.service
sudo systemctl status followup.service
```

## 📊 Estado del Proyecto

**Fase actual**: Sprint 4 - Métricas Avanzadas (En Progreso - 95%)  
**Última actualización**: 11 Noviembre 2025  
**Versión**: 4.3.0  
**Progreso**: Sprint 0 ✅ | Sprint 1 ✅ | Sprint 2 ✅ | Sprint 3 ✅ | Sprint 4 🚧 (HITO 1 ✅ | HITO 2 ✅ | Refinements ✅ | UX Avanzadas ✅ | HITO 3 Fase 1 ✅)

**Highlights Sprint 3 Final:**
- ✅ Precios en tiempo real desde Yahoo Finance (15 métricas)
- ✅ Conversión automática de divisas (166 monedas, cache 24h)
- ✅ Fix crítico: Cálculo correcto de "Coste Total" en EUR
- ✅ Dashboard con P&L en tiempo real
- ✅ Holdings page ampliada (95% ancho)
- ✅ Página dedicada de tasas de conversión
- ✅ FIFO robusto con posiciones cortas temporales
- ✅ Parser completo DeGiro + IBKR
- ✅ AssetRegistry global + MappingRegistry editable
- ✅ 100% precisión en holdings y P&L

**Highlights Sprint 4 - Métricas Avanzadas (HITO 1 + 2 + Refinements + UX Avanzadas + HITO 3 Fase 1 ✅):**
- ✅ 8 Métricas implementadas (P&L Realizado, P&L No Realizado, ROI, Leverage, etc.)
- ✅ Modified Dietz Method (estándar GIPS, sin necesidad de precios históricos)
- ✅ Dashboard reorganizado (Métricas Globales + Portfolio separados)
- ✅ Página P&L by Asset con histórico completo
- ✅ Cache de métricas (2-3s → 0.3s de carga)
- ✅ Eliminar transacciones con confirmación
- ✅ Fixes críticos CSRF + UX mejoradas
- ✅ Transacciones manuales avanzadas (auto-selección SELL, autocompletado BUY, venta por quiebra)
- ✅ Botones de enriquecimiento inteligentes (OpenFIGI + Yahoo URL)
- ✅ Redirección optimizada a holdings tras transacciones
- ✅ **Gráficos de Evolución** (`/portfolio/performance`):
  - Evolución del Valor Real de la Cuenta (mensual, optimizado)
  - Rentabilidad Acumulada (Modified Dietz)
  - Último punto con precios reales actuales
  - Chart.js 4.0 con tooltips y formateo europeo

**Próximo: Sprint 4 - HITO 3 Fase 2 (Gráficos Adicionales):**
- 📈 3 gráficos restantes (Apalancamiento, Flujos de caja, P&L Acumulado)
- 🆚 Fase 3: Comparación con benchmarks (S&P 500, NASDAQ, etc.)

