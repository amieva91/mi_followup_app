# FollowUp - Personal Financial Management

Sistema completo de gestión financiera personal.

## ✅ Estado Actual (21 Oct 2025)

**Funcionalidades Implementadas:**
- ✅ **Sprint 0 - Arquitectura Base** - Configuración inicial, estructura modular
- ✅ **Sprint 1 - Autenticación** - Registro, Login, Reset Password
- ✅ **Sprint 2 - Gastos e Ingresos** 
  - Categorías jerárquicas con padre/hijo
  - Gastos y ingresos puntuales y recurrentes
  - Generación automática de instancias históricas
  - Edición y eliminación de series completas
  - Emoji picker interactivo
- ✅ **Sprint 3 - CSV Processor & Portfolio Management** 
  - Base de datos completa (9 modelos: 8 portfolio + AssetRegistry global)
  - CRUD de cuentas de broker con eliminación destructiva
  - Entrada manual de transacciones (BUY/SELL/DIVIDEND/FEE/DEPOSIT/WITHDRAWAL)
  - Parser CSV para IBKR (formato jerárquico + extracción ISIN)
  - Parser CSV para DeGiro Transacciones (lectura por índices, monedas correctas)
  - Parser CSV para DeGiro Estado de Cuenta (dividendos/comisiones/FX)
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
- ✅ **Dashboard** - KPIs en tiempo real (ingresos/gastos/balance mensual)
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

1. **`TU_PLAN_MAESTRO.md`** - Plan general del proyecto y estado actual
2. **`WORKFLOW_DEV_A_PRODUCCION.md`** - Proceso de deploy
3. **`DESIGN_SYSTEM.md`** - Sistema de diseño y componentes UI
4. **`SPRINT3_DISEÑO_BD.md`** - Diseño y progreso del Sprint 3 (Portfolio/CSV)

### 📁 Documentación Organizada (`docs/`)

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

**Fase actual**: Sprint 3 - Finalizado / Sprint 4 - Próximamente  
**Última actualización**: 10 Octubre 2025  
**Versión**: 3.2.0  
**Progreso**: Sprint 0 ✅ | Sprint 1 ✅ | Sprint 2 ✅ | Sprint 3 ✅ (100%)

**Highlights Sprint 3:**
- FIFO robusto con manejo de posiciones cortas temporales
- Parser completo de DeGiro (Transacciones + Estado de Cuenta)
- Corrección de extracción de monedas (csv.reader por índices)
- Consolidación unificada de dividendos con FX conversion
- Normalización de símbolos y extracción de ISINs de IBKR
- Búsqueda y edición de transacciones con recálculo automático
- Vista unificada de holdings por asset (múltiples brokers)
- Import múltiple de archivos CSV con snapshot de duplicados
- Formato europeo en números (1.234,56) y visualización Type • Currency • ISIN
- 19 holdings correctos, 0 posiciones incorrectas, 100% precisión FIFO

**Próximos Pasos (Pendientes para refinamiento):**
- 🔍 Pruebas exhaustivas con CSVs de ambos brokers (IBKR + DeGiro completos)
- 📋 Revisión de información faltante: `exchange` (0%), `sector` (0%)
- 🔌 Integración APIs externas (Yahoo Finance) para exchange/sector/precios
- 📊 Sprint 4: Calculadora de Métricas (IRR, Sharpe, Max Drawdown, etc.)

