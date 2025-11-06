# FollowUp - Personal Financial Management

Sistema completo de gestión financiera personal.

## ✅ Estado Actual (6 Nov 2025)

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
- ✅ **Dashboard** - KPIs en tiempo real (ingresos/gastos/balance mensual + portfolio)
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

**Fase actual**: Sprint 3 - ✅ COMPLETADO / Sprint 4 - Iniciando  
**Última actualización**: 6 Noviembre 2025  
**Versión**: 3.5.0  
**Progreso**: Sprint 0 ✅ | Sprint 1 ✅ | Sprint 2 ✅ | Sprint 3 ✅ (100%)

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

**Sprint 4 - Métricas Avanzadas (Próximo):**
- 📊 Leverage (apalancamiento basado en deposits/withdrawals)
- 📊 Peso % por posición en portfolio
- 📊 P&L Realizado vs No Realizado
- 📊 TWR, IRR, Sharpe Ratio, Max Drawdown, Volatilidad
- 📈 Gráficos de evolución y distribución

