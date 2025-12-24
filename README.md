# FollowUp - Personal Financial Management

Sistema completo de gestión financiera personal.

## ✅ Estado Actual (24 Dic 2025) - v6.0.0

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
- ✅ **Sprint 4 - Métricas Avanzadas (COMPLETADO - 23 Dic 2025)**
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
  - ✅ **HITO 4: Distribución del Portfolio + Comparación con Benchmarks (COMPLETADO - 23 Dic 2025)**:
    - **Gráficos de Distribución** (6 gráficos en dashboard):
      - Por País, Sector (ya existían)
      - Por Asset (Top 10 + Otros) - NUEVO
      - Por Industria - NUEVO
      - Por Broker (IBKR, DeGiro, Manual) - NUEVO
      - Por Tipo (Stock incluye ADR, ETF, Bond, Crypto) - NUEVO
    - **Comparación con Benchmarks**:
      - Recuadro expandido en dashboard con comparación horizontal
      - Integración con Yahoo Finance para índices (S&P 500, NASDAQ 100, MSCI World, EuroStoxx 50)
      - Gráfico comparativo de rentabilidad normalizado vs benchmarks
      - Tabla comparativa anual (rentabilidades año a año + diferencias)
      - Corrección de discrepancias: dashboard y tabla usan totales acumulados consistentes
    - 🆕 Macro (Planificado): nueva pestaña `/macro/inflation` con tabla y gráfico de inflación por país, agregados **OCDE** y **APEC**, filtros por regiones/indicadores y opción “Solo países en cartera/Watchlist”. Fuentes gratuitas: OECD/World Bank/Eurostat. Cache 24h y normalización (% YoY/MoM).
  - 📝 **HITO 3 - Fase 2 (Planificado)**:
    - Nueva pestaña: `/portfolio/commodities`
    - Gráfico con 3 líneas: Oro (XAUUSD=X), Plata (XAGUSD=X) normalizados a 100 y Correlación rolling 30d (eje secundario -1..1)
    - Filtros de visibilidad por serie (legend/checkboxes)
    - Endpoint JSON: `/portfolio/api/commodities?range=1Y&interval=1d&window=30`
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

**IMPORTANTE**: El directorio raíz debe mantenerse limpio. Solo deben permanecer en la raíz estos 5 archivos:

1. **`README.md`** - Este archivo (estado actual, setup, arquitectura, metodología de trabajo)
2. **`TU_PLAN_MAESTRO.md`** - Plan general del proyecto con todos los sprints y progreso
3. **`WORKFLOW_DEV_A_PRODUCCION.md`** - Proceso completo de deploy, Git workflow y configuración de entornos
4. **`DESIGN_SYSTEM.md`** - Sistema de diseño y componentes UI
5. **`SPRINT[X]_[NOMBRE].md`** - Documento del sprint actual en progreso (ej: `SPRINT4_METRICAS_AVANZADAS.md`)

**Todos los demás archivos `.md` deben moverse a `docs/` al finalizar cada sprint.**

### 📁 Documentación Organizada (`docs/`)

- **`docs/sprints/`** - Sprints completados (archivos movidos desde raíz)
- **`docs/sesiones/`** - Bitácora de sesiones de trabajo
- **`docs/archivo/`** - Análisis inicial y propuestas
- **`docs/migraciones/`** - Documentos de migraciones históricas
- **`docs/indices/`** - Índices de documentación
- **`docs/fixes/`** - Documentación de fixes y correcciones
- **`docs/implementaciones/`** - Documentación de implementaciones específicas
- **`docs/guias/`** - Guías de uso y procedimientos

---

## 🔄 METODOLOGÍA DE TRABAJO

**Esta sección define cómo trabajamos en este proyecto. Es fundamental leerla antes de comenzar cualquier tarea.**

### 📖 Documentos de Referencia

Para entender completamente el flujo de trabajo, consulta estos documentos en orden:

1. **`WORKFLOW_DEV_A_PRODUCCION.md`** - Proceso completo de desarrollo y deploy
2. **`TU_PLAN_MAESTRO.md`** - Plan maestro con todos los sprints e hitos
3. **`DESIGN_SYSTEM.md`** - Guías de diseño y componentes UI
4. **`SPRINT[X]_[NOMBRE].md`** - Documento del sprint actual con hitos y tareas

### 🖥️ Entornos de Trabajo

#### Desarrollo (WSL - Único Entorno de Desarrollo)

**IMPORTANTE**: Todo el desarrollo se realiza **SIEMPRE** en el entorno de desarrollo (WSL). Nunca se codifica directamente en producción.

```bash
Host: ssoo@ES-5CD52753T5
Directorio: /home/ssoo/www
Sistema: WSL Ubuntu
Base de datos: SQLite (local)
Puerto: 5000
URL: http://localhost:5000
Branch Git: develop
```

**Características**:
- ✅ Entorno WSL permite interacción por línea de comandos con la IA
- ✅ Base de datos local para pruebas sin afectar producción
- ✅ Servidor Flask en modo desarrollo (debug activado)
- ✅ Branch `develop` para desarrollo activo

#### Producción (Oracle Cloud)

```bash
Servidor: ubuntu@140.238.120.92
Directorio: /home/ubuntu/www
Dominio: https://followup.fit/
Base de datos: SQLite
Puerto: 5000
Servicio: followup.service (systemd)
Branch Git: main
```

**Características**:
- ❌ **NUNCA** se codifica directamente aquí
- ✅ Solo recibe código desde `main` branch
- ✅ Deploy automático mediante `systemctl`
- ✅ Validación post-deploy obligatoria

### 🔄 Flujo de Trabajo Completo

#### 1. Desarrollo de Features (Siempre en Dev/WSL)

```bash
# 1. Asegurarse de estar en develop
cd /home/ssoo/www
git checkout develop
git pull origin develop

# 2. Activar entorno virtual
source venv/bin/activate

# 3. Desarrollar feature/hito
# ... editar archivos ...
# ... trabajar en el código ...

# 4. Probar localmente
python run.py
# Abrir http://localhost:5000 y probar
```

**Reglas**:
- ✅ Todo el código se escribe en WSL (desarrollo)
- ✅ Branch `develop` es la rama de trabajo activa
- ✅ Probar localmente antes de commitear
- ✅ Commits descriptivos con formato: `feat:`, `fix:`, `refactor:`, etc.

#### 2. Pruebas Después de Cada Hito/Sprint

**IMPORTANTE**: Después de completar un hito o sprint, **SIEMPRE** se realizan pruebas exhaustivas antes de subir a producción.

**Guía de Pruebas** (el usuario debe probar):

1. **Funcionalidad Nueva**:
   - [ ] Probar todas las funcionalidades nuevas implementadas
   - [ ] Verificar que funcionan según los requisitos del hito
   - [ ] Probar casos límite y edge cases
   - [ ] Verificar que no hay errores en consola del navegador

2. **Funcionalidades Existentes** (regresión):
   - [ ] Verificar que las funcionalidades anteriores siguen funcionando
   - [ ] Probar áreas que puedan haber sido afectadas por los cambios
   - [ ] Verificar que no se rompió nada existente

3. **Interfaz de Usuario**:
   - [ ] Verificar que la UI se ve correctamente
   - [ ] Probar en diferentes tamaños de pantalla (responsive)
   - [ ] Verificar que los mensajes de error/éxito funcionan
   - [ ] Comprobar que los formularios validan correctamente

4. **Base de Datos**:
   - [ ] Verificar que las migraciones se aplican correctamente
   - [ ] Comprobar que los datos se guardan/recuperan bien
   - [ ] Verificar integridad de datos existentes

5. **Performance**:
   - [ ] Verificar que no hay degradación de rendimiento
   - [ ] Comprobar tiempos de carga razonables

**Resultado**: Si todas las pruebas pasan, se procede al siguiente paso. Si hay errores, se corrigen antes de continuar.

#### 3. Actualización de Documentación (Antes de Subir a Pro)

**IMPORTANTE**: Antes de subir a producción, **SIEMPRE** se actualizan los documentos principales:

1. **Actualizar `README.md`**:
   - Estado actual del proyecto
   - Versión actualizada
   - Nuevas funcionalidades añadidas

2. **Actualizar `TU_PLAN_MAESTRO.md`**:
   - Marcar hitos/sprints completados
   - Actualizar progreso
   - Añadir notas de lo completado

3. **Actualizar `WORKFLOW_DEV_A_PRODUCCION.md`**:
   - Añadir cambios del último deploy
   - Actualizar versión y fecha
   - Documentar cualquier cambio en el proceso

4. **Actualizar `DESIGN_SYSTEM.md`**:
   - Añadir nuevos componentes UI si los hay
   - Documentar cambios en diseño

5. **Actualizar `SPRINT[X]_[NOMBRE].md`**:
   - Marcar hitos completados
   - Documentar lo implementado
   - Actualizar estado del sprint

#### 4. Limpieza del Directorio Raíz (Antes de Subir a Pro)

**IMPORTANTE**: El directorio raíz debe mantenerse limpio. Solo deben quedar:

- ✅ `README.md`
- ✅ `TU_PLAN_MAESTRO.md`
- ✅ `WORKFLOW_DEV_A_PRODUCCION.md`
- ✅ `DESIGN_SYSTEM.md`
- ✅ `SPRINT[X]_[NOMBRE].md` (solo el sprint actual)

**Proceso de limpieza**:

```bash
# 1. Identificar archivos .md que no son principales
cd /home/ssoo/www
ls *.md

# 2. Mover archivos temporales/documentación a docs/
# Ejemplo:
mv PROGRESO_PLAN_MAESTRO.md docs/sprints/
mv CACHE_IMPLEMENTATION.md docs/implementaciones/
# ... etc

# 3. Verificar que solo quedan los 5 archivos principales
ls *.md
```

**Regla**: Si un archivo `.md` no es uno de los 5 principales, debe moverse a `docs/` en la carpeta correspondiente.

#### 5. Commit y Push a Develop

```bash
# 1. Verificar cambios
git status

# 2. Añadir cambios
git add .

# 3. Commit descriptivo
git commit -m "feat: Sprint X - Hito Y completado

- Detalle 1
- Detalle 2
- Documentación actualizada"

# 4. Push a develop
git push origin develop
```

#### 6. Merge a Main (Solo Después de Revisar y Probar)

**IMPORTANTE**: Solo se hace merge a `main` cuando:
- ✅ El hito/sprint está completamente terminado
- ✅ Todas las pruebas pasaron
- ✅ Documentación actualizada
- ✅ Directorio raíz limpio

```bash
# 1. Cambiar a main
git checkout main

# 2. Mergear develop
git merge develop

# 3. Push a main
git push origin main
```

#### 7. Deploy a Producción

**Ver proceso completo en**: `WORKFLOW_DEV_A_PRODUCCION.md` (FASE 4: Deploy a Producción)

Resumen:
```bash
# En servidor de producción
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92
cd ~/www
git pull origin main
source venv/bin/activate
pip install -r requirements.txt  # Solo si cambió
flask db upgrade  # Solo si hay migraciones
sudo systemctl restart followup.service
sudo systemctl status followup.service
```

#### 8. Validación en Producción

**IMPORTANTE**: Después de cada deploy, se valida en producción:

- [ ] La aplicación arrancó sin errores
- [ ] No hay errores en logs (`journalctl -u followup.service`)
- [ ] URL https://followup.fit/ carga correctamente
- [ ] Nuevo feature funciona en producción
- [ ] Features anteriores siguen funcionando
- [ ] No hay errores en consola del navegador

**Ver checklist completo en**: `WORKFLOW_DEV_A_PRODUCCION.md` (FASE 5: Validación en Producción)

#### 9. Finalización de Sprint (Movimiento de Archivos)

**IMPORTANTE**: Al finalizar un sprint completamente:

1. **Mover archivo del sprint a `docs/sprints/`**:
   ```bash
   mv SPRINT4_METRICAS_AVANZADAS.md docs/sprints/
   ```

2. **Crear nuevo archivo para el siguiente sprint**:
   ```bash
   # Crear SPRINT5_[NOMBRE].md en la raíz
   # Seguir la estructura de sprints anteriores
   ```

3. **Actualizar `TU_PLAN_MAESTRO.md`**:
   - Marcar sprint como completado
   - Actualizar estado del siguiente sprint

### 📋 Checklist Pre-Deploy

Antes de subir a producción, verificar:

- [ ] Código funcional en desarrollo (todas las pruebas pasaron)
- [ ] Documentación actualizada (4 documentos principales + sprint actual)
- [ ] Directorio raíz limpio (solo 5 archivos `.md` principales)
- [ ] Commit con mensaje descriptivo
- [ ] Push a `develop` exitoso
- [ ] Merge a `main` realizado
- [ ] Backup de BD en producción programado (si hay migraciones)

### 📋 Checklist Post-Deploy

Después de subir a producción, verificar:

- [ ] Aplicación arrancó sin errores
- [ ] No hay errores en logs
- [ ] URL carga correctamente
- [ ] Nuevo feature funciona en producción
- [ ] Features anteriores siguen funcionando
- [ ] No hay errores en consola del navegador

### 🎯 Reglas de Oro

1. ❌ **NUNCA** codificar directamente en producción
2. ✅ **SIEMPRE** trabajar en desarrollo (WSL)
3. ✅ **SIEMPRE** probar en desarrollo antes de mergear
4. ✅ **SIEMPRE** actualizar documentación antes de subir a pro
5. ✅ **SIEMPRE** limpiar directorio raíz antes de subir a pro
6. ✅ **SIEMPRE** validar en producción después de deploy
7. ✅ **SIEMPRE** mantener `develop` y `main` sincronizados
8. ✅ **SIEMPRE** hacer pruebas exhaustivas después de cada hito/sprint

### 📞 Referencias Rápidas

- **Proceso de deploy completo**: Ver `WORKFLOW_DEV_A_PRODUCCION.md`
- **Plan maestro y progreso**: Ver `TU_PLAN_MAESTRO.md`
- **Sistema de diseño**: Ver `DESIGN_SYSTEM.md`
- **Sprint actual**: Ver `SPRINT[X]_[NOMBRE].md`

> **Nota**: Para el flujo completo de Git y Deploy, consulta la sección **"🔄 METODOLOGÍA DE TRABAJO"** arriba, o el documento detallado **`WORKFLOW_DEV_A_PRODUCCION.md`**.

## 📊 Estado del Proyecto

**Fase actual**: Sprint 4 - Métricas Avanzadas (En Progreso - 98%)  
**Última actualización**: 22 Diciembre 2025  
**Versión**: 4.3.0  
**Progreso**: Sprint 0 ✅ | Sprint 1 ✅ | Sprint 2 ✅ | Sprint 3 ✅ | Sprint 4 🚧 (HITO 1 ✅ | HITO 2 ✅ | Refinements ✅ | UX Avanzadas ✅ | HITO 3 ✅)

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
- ✅ **Gráficos de Evolución** (`/portfolio/performance`) - **COMPLETADO (HITO 3)**:
  - Gráfico 1: Evolución del Valor Real de la Cuenta (vs Capital Invertido)
  - Gráfico 2: Rentabilidad Acumulada (Modified Dietz %)
  - Gráfico 3: Apalancamiento/Cash Histórico (verde=cash, rojo=leverage) ✅ HITO 3 Fase 2
  - Gráfico 4: Flujos de Caja Acumulados (Capital Invertido Neto) ✅ HITO 3 Fase 2
  - Gráfico 5: P&L Total Acumulado (Realizado + No Realizado + Dividendos - Comisiones) ✅ HITO 3 Fase 2
  - Gráfico 6: Comparación con Benchmarks (normalizado a base 100) ✅ HITO 4
  - Frecuencia mensual optimizada, último punto con precios reales actuales
  - Chart.js 4.0 con tooltips informativos y formateo europeo

**✅ Sprint 4 COMPLETADO (23 Dic 2025):**
- ✅ HITO 4: Gráficos de distribución (6 gráficos) + Comparación con benchmarks completa
- ✅ Corrección de discrepancias en cálculos (dashboard y tabla consistentes)
- ✅ Recuadro de comparación expandido a ancho completo
- ✅ HITO 3 - Fase 2: Gráficos adicionales (Apalancamiento, Flujos de Caja, P&L Acumulado)

**🚧 Sprint 6 EN PLANIFICACIÓN (24 Dic 2025):**
- 🔜 HITO 1: Análisis de Concentración (métricas y alertas)
- 🔜 HITO 2: Watchlist con Comparación vs Portfolio
- 🔜 HITO 3: Alertas de Diversificación configurables

