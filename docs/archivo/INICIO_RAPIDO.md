# 🚀 INICIO RÁPIDO - Primeros Pasos

**Fecha de creación**: 5 Octubre 2025  
**Última actualización**: 6 Octubre 2025  
**Tiempo estimado**: 30 minutos de lectura + 3 días de setup

---

## 📚 PASO 0: Leer Documentación (30 min)

### Lectura Obligatoria (HOY)

```
1. Este archivo (5 min)
2. TU_PLAN_MAESTRO.md - Sección "Tu Perfil" (5 min)
3. TU_PLAN_MAESTRO.md - Sección "Sprint 0" (10 min)
4. WORKFLOW_DEV_A_PRODUCCION.md - Resumen (5 min)
5. DESIGN_SYSTEM.md - Paleta de colores y componentes base (5 min)
```

### Lectura Recomendada (Esta Semana)

```
- TU_PLAN_MAESTRO.md - Completo (1 hora)
- WORKFLOW_DEV_A_PRODUCCION.md - Completo (30 min)
- DESIGN_SYSTEM.md - Completo (30 min)
```

---

## 🎯 PASO 1: Entender Tu Proyecto

### ¿Qué Vas a Construir?

**Followup** - Sistema financiero personal completo con:
- ✅ 13 módulos funcionales (todos los que usas)
- ✅ Dashboard con KPIs en tiempo real
- ✅ Procesador robusto de CSVs (tu pain point crítico)
- ✅ Diseño elegante y profesional
- ✅ Arquitectura limpia y mantenible

### Timeline

```
Total: 6 meses (26 semanas)
│
├─ Mes 1-3: Sistema Core + CSV Processor
│  └─ Auth, Cuentas, Gastos, Ingresos, Dashboard, Portfolio
│
├─ Mes 4-5: Inversiones Alternativas + Patrimonio
│  └─ Crypto, Metales, Bienes Raíces, Deudas, Pensiones
│
└─ Mes 6: Análisis y Refinamiento
   └─ Benchmarks, Reportes, Alertas, Polish
```

### Hito Actual

```
✅ COMPLETADO: Sprint 0 (Infraestructura)
✅ COMPLETADO: Sprint 1 (Autenticación)  
✅ COMPLETADO: Sprint 2 (Gastos e Ingresos)
📍 PRÓXIMO: Sprint 3 (CSV Processor) o refinamiento
```

---

## 💻 PASO 2: Setup de Desarrollo (Día 1)

### 2.1 Backup del Sistema Actual

```bash
# En WSL
cd /home/ssoo/www

# Crear backup
mkdir -p ../www_backup_$(date +%Y%m%d)
mv * ../www_backup_$(date +%Y%m%d)/ 2>/dev/null || true

# Verificar
ls -la ../www_backup_*/
```

### 2.2 Configurar Git (Primera Vez)

```bash
# Configurar identidad (CAMBIAR CON TUS DATOS)
git config --global user.name "Tu Nombre"
git config --global user.email "tu@email.com"

# Verificar configuración
git config --list
```

### 2.3 Crear Estructura del Proyecto

```bash
# Crear directorio y estructura base
cd /home/ssoo/www
mkdir followup
cd followup

# Inicializar Git
git init
git branch -M main

# Crear estructura de carpetas
mkdir -p app/{models,routes,services,forms,templates,static/{css,js,img},csv_processor,utils}
mkdir -p tests/{unit,integration,fixtures}
mkdir -p migrations docs scripts

# Crear archivos base
touch app/__init__.py
touch app/config.py
touch requirements.txt
touch .env.example
touch .gitignore
touch README.md
```

### 2.4 Crear .gitignore

```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Flask
instance/
.env
*.db

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# TailwindCSS
node_modules/
package-lock.json

# Backups
*.bak
*.backup
EOF
```

### 2.5 Crear Entorno Virtual e Instalar Dependencias Base

```bash
# Crear entorno virtual
python3 -m venv venv

# Activar
source venv/bin/activate

# Actualizar pip
pip install --upgrade pip

# Instalar dependencias base
pip install flask==3.0.0
pip install flask-sqlalchemy==3.1.1
pip install flask-login==0.6.3
pip install flask-wtf==1.2.1
pip install psycopg2-binary==2.9.9
pip install alembic==1.13.1
pip install python-dotenv==1.0.0
pip install gunicorn==21.2.0
pip install pytest==7.4.3
pip install pytest-cov==4.1.0

# Generar requirements.txt
pip freeze > requirements.txt
```

### 2.6 Primer Commit

```bash
git add .
git commit -m "Initial project structure

- Basic folder structure
- Virtual environment setup
- Initial dependencies
- Gitignore configuration"
```

---

## 🗄️ PASO 3: Setup de PostgreSQL (Día 2)

### 3.1 Instalar PostgreSQL en WSL

```bash
# Actualizar repositorios
sudo apt update

# Instalar PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Iniciar servicio
sudo service postgresql start

# Verificar que está corriendo
sudo service postgresql status
```

### 3.2 Crear Base de Datos de Desarrollo

```bash
# Cambiar a usuario postgres
sudo -u postgres psql

# Dentro de psql, ejecutar:
CREATE DATABASE followup_dev;
CREATE USER followup_user WITH PASSWORD 'dev_password_123';
GRANT ALL PRIVILEGES ON DATABASE followup_dev TO followup_user;
\q

# Verificar conexión
psql -U followup_user -d followup_dev -h localhost
# Password: dev_password_123
# Si conecta, salir con: \q
```

### 3.3 Crear Archivo .env

```bash
cat > .env << 'EOF'
# Environment
FLASK_ENV=development
FLASK_DEBUG=True

# Database
DATABASE_URL=postgresql://followup_user:dev_password_123@localhost/followup_dev

# Secret Key (generar una real en producción)
SECRET_KEY=dev-secret-key-change-in-production

# App Config
APP_NAME=Followup
EOF
```

---

## 🎨 PASO 4: Setup de TailwindCSS (Día 2)

### 4.1 Instalar Node.js (si no está instalado)

```bash
# Verificar si está instalado
node --version
npm --version

# Si no está instalado:
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 4.2 Configurar TailwindCSS

```bash
# Inicializar npm
npm init -y

# Instalar TailwindCSS
npm install -D tailwindcss @tailwindcss/forms

# Inicializar config
npx tailwindcss init
```

### 4.3 Configurar tailwind.config.js

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
        },
        success: {
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
        },
        danger: {
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}
```

### 4.4 Crear CSS de Entrada

```bash
mkdir -p app/static/css

cat > app/static/css/input.css << 'EOF'
@tailwind base;
@tailwind components;
@tailwind utilities;
EOF
```

### 4.5 Configurar Scripts de Build

Añadir a `package.json`:

```json
{
  "scripts": {
    "build:css": "tailwindcss -i ./app/static/css/input.css -o ./app/static/css/output.css",
    "watch:css": "tailwindcss -i ./app/static/css/input.css -o ./app/static/css/output.css --watch"
  }
}
```

### 4.6 Compilar CSS

```bash
npm run build:css
```

---

## 🚀 PASO 5: Crear App Básica (Día 3)

### 5.1 Crear app/__init__.py (Factory)

```python
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

# Inicializar extensiones
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    
    # Configuración
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Registrar blueprints (cuando los tengas)
    # from app.routes import auth
    # app.register_blueprint(auth.bp)
    
    # Ruta de prueba
    @app.route('/')
    def index():
        return '<h1>Followup - Sistema Financiero</h1><p>¡Funciona!</p>'
    
    return app
```

### 5.2 Crear run.py (Ejecutor)

```python
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
```

### 5.3 Probar la Aplicación

```bash
# Activar entorno virtual (si no está activo)
source venv/bin/activate

# Ejecutar app
python run.py

# Deberías ver:
# * Running on http://127.0.0.1:5000

# Abrir navegador en: http://localhost:5000
# Deberías ver: "Followup - Sistema Financiero ¡Funciona!"

# Ctrl+C para detener
```

### 5.4 Commit de App Base

```bash
git add .
git commit -m "Add basic Flask app with database config

- Flask factory pattern
- PostgreSQL connection
- TailwindCSS setup
- Basic test route"
```

---

## 🌐 PASO 6: Configurar Producción (Día 3)

### 6.1 Conectar al Servidor

```bash
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92
```

### 6.2 Limpiar Directorio Actual

```bash
# ⚠️ CUIDADO: Esto borra todo
cd /home/ubuntu/www
sudo rm -rf *

# Verificar que está vacío
ls -la
```

### 6.3 Instalar Dependencias del Sistema

```bash
# Actualizar
sudo apt update
sudo apt upgrade -y

# Instalar dependencias
sudo apt install -y python3-pip python3-venv postgresql nginx git

# Instalar Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 6.4 Configurar PostgreSQL en Producción

```bash
# Cambiar a usuario postgres
sudo -u postgres psql

# Crear base de datos
CREATE DATABASE followup_prod;
CREATE USER followup_prod_user WITH PASSWORD 'CAMBIAR_PASSWORD_SEGURO';
GRANT ALL PRIVILEGES ON DATABASE followup_prod TO followup_prod_user;
\q
```

### 6.5 Crear GitHub Repository (Opcional pero Recomendado)

```bash
# En GitHub: Crear repo "followup"
# Entonces, en desarrollo (WSL):

cd /home/ssoo/www/followup
git remote add origin https://github.com/TU_USUARIO/followup.git
git push -u origin main
```

### 6.6 Clonar Proyecto en Producción

```bash
# En producción
cd /home/ubuntu/www
git clone https://github.com/TU_USUARIO/followup.git

# O si no usas GitHub, copiar manualmente con SCP desde WSL:
# scp -i ~/.ssh/ssh-key-2025-08-21.key -r /home/ssoo/www/followup/* ubuntu@140.238.120.92:/home/ubuntu/www/followup/
```

### 6.7 Configurar Entorno en Producción

```bash
cd /home/ubuntu/www/followup

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Crear .env de producción
nano .env
```

Contenido de `.env` en producción:

```bash
FLASK_ENV=production
FLASK_DEBUG=False
DATABASE_URL=postgresql://followup_prod_user:TU_PASSWORD_SEGURO@localhost/followup_prod
SECRET_KEY=GENERA_UNA_CLAVE_SECRETA_MUY_LARGA_Y_ALEATORIA
APP_NAME=Followup
```

---

## ✅ VERIFICACIÓN FINAL

Si completaste todos los pasos:

```bash
# En desarrollo (WSL):
[ ] PostgreSQL instalado y corriendo
[ ] Base de datos followup_dev creada
[ ] Entorno virtual creado y activado
[ ] Dependencias instaladas
[ ] TailwindCSS configurado
[ ] App básica funciona en localhost:5000
[ ] Git configurado y commits iniciales hechos

# En producción:
[ ] Servidor limpio
[ ] Dependencias del sistema instaladas
[ ] PostgreSQL configurado
[ ] Base de datos followup_prod creada
[ ] Proyecto clonado/copiado
[ ] Entorno virtual configurado
[ ] Archivo .env de producción creado
```

---

## 🎯 PRÓXIMOS PASOS

### Mañana (Día 4)

```
🚀 Empezar Sprint 1: Autenticación

Ver TU_PLAN_MAESTRO.md → Sprint 1 para detalles completos

Tareas:
1. Crear modelo User
2. Implementar rutas de auth
3. Crear templates de login/registro
4. Tests básicos
```

### Esta Semana

```
Semana 1: Autenticación (backend)
Semana 2: Autenticación (frontend) + Deploy
```

### Este Mes

```
Sprint 1: Autenticación (2 semanas)
Sprint 2: Cuentas Bancarias (2 semanas)
```

---

## 📞 ¿PROBLEMAS?

### Error: PostgreSQL no arranca en WSL

```bash
sudo service postgresql start
# Si falla:
sudo pg_ctlcluster 16 main start
```

### Error: No se puede conectar a PostgreSQL

```bash
# Verificar que está corriendo
sudo service postgresql status

# Ver logs
sudo tail -f /var/log/postgresql/postgresql-16-main.log
```

### Error: pip install falla

```bash
# Actualizar pip
pip install --upgrade pip

# Instalar dependencias del sistema si falta algo
sudo apt install python3-dev libpq-dev
```

### Error: Permission denied en producción

```bash
# Cambiar permisos
sudo chown -R ubuntu:ubuntu /home/ubuntu/www/followup
```

---

## 📚 DOCUMENTOS DE REFERENCIA

Durante el desarrollo, consultar:

1. **TU_PLAN_MAESTRO.md** → Plan completo de 6 meses
2. **WORKFLOW_DEV_A_PRODUCCION.md** → Proceso de deploy
3. **DESIGN_SYSTEM.md** → Componentes y estilos
4. **FORMULAS_Y_CALCULOS.md** → Fórmulas financieras
5. **ANALISIS_COMPLETO_FUNCIONALIDADES.md** → Detalles de módulos

---

## 🎉 ¡LISTO PARA EMPEZAR!

```
✅ Setup completo
✅ Documentación leída
✅ Entornos configurados
✅ Git funcionando

🚀 Próximo paso: Sprint 1 - Autenticación
```

**¡Vamos a construir algo increíble!** 💪

---

**Creado**: 5 Octubre 2025  
**Estado**: Setup inicial  
**Progreso**: 0/26 semanas (0%)

