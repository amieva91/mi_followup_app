# FollowUp - Personal Financial Management

Sistema completo de gestión financiera personal.

## ✅ Estado Actual (7 Oct 2025)

**Funcionalidades Implementadas:**
- ✅ **Sprint 1 - Autenticación** - Registro, Login, Reset Password
- ✅ **Sprint 2 - Gastos e Ingresos** 
  - Categorías jerárquicas con padre/hijo
  - Gastos y ingresos puntuales y recurrentes
  - Generación automática de instancias históricas
  - Edición y eliminación de series completas
  - Emoji picker interactivo
- ✅ **Sprint 3 - Portfolio Manager (HITO 1 y 2)**
  - Base de datos completa (8 modelos)
  - CRUD de cuentas de broker
  - Entrada manual de transacciones (BUY/SELL/DIVIDEND/etc)
  - Actualización automática de holdings con FIFO
  - Cálculo de P&L realizadas
  - Dashboard de portfolio
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

**Fase actual**: Sprint 3 - CSV Processor (HITO 2 completado)  
**Última actualización**: 7 Octubre 2025  
**Versión**: 2.0.0  
**Progreso**: Sprint 0 ✅ | Sprint 1 ✅ | Sprint 2 ✅ | Sprint 3 🔄 (33%)

