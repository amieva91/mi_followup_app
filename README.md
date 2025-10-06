# FollowUp - Personal Financial Management

Sistema completo de gestión financiera personal.

## ✅ Estado Actual (6 Oct 2025)

**Funcionalidades Implementadas:**
- ✅ **Autenticación completa** - Registro, Login, Reset Password
- ✅ **Gestión de Gastos** - Categorías jerárquicas, gastos puntuales y recurrentes
- ✅ **Gestión de Ingresos** - Categorías, ingresos puntuales y recurrentes  
- ✅ **Dashboard** - KPIs en tiempo real (ingresos/gastos/balance mensual)
- ✅ **Recurrencias inteligentes** - Daily/Weekly/Monthly/Yearly con gestión completa
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

## 📚 Documentación Completa

Ver carpeta `/docs` para:
- Plan maestro: `TU_PLAN_MAESTRO.md`
- Workflow dev→prod: `WORKFLOW_DEV_A_PRODUCCION.md`
- Sistema de diseño: `DESIGN_SYSTEM.md`
- Guía de inicio: `INICIO_RAPIDO.md`

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

**Fase actual**: Sprint 0 - Setup inicial
**Última actualización**: Oct 2025
**Versión**: 2.0.0 (rebuild desde cero)

