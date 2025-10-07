# 🔄 WORKFLOW: Desarrollo → Producción

**Actualizado**: 7 Octubre 2025 - 23:00 UTC  
**Estado**: ✅ WORKFLOW VALIDADO Y FUNCIONANDO

**Último deploy exitoso**: 7 Octubre 2025 - Sprint 3 COMPLETO (CSV Processor)

---

## 🎯 FILOSOFÍA

```
Desarrollo Local (WSL) → Git (develop) → Git (main) → Producción → Validación
```

**Reglas de Oro**:
1. ❌ Nunca codificar directamente en producción
2. ✅ Siempre testear en desarrollo antes de mergear
3. ✅ Siempre probar en producción después de deploy
4. ✅ Mantener develop y main sincronizados

---

## 🖥️ CONFIGURACIÓN DE ENTORNOS

### Desarrollo (WSL)

```bash
# Tu entorno de desarrollo
Host: ssoo@ES-5CD52753T5
Path: /home/ssoo/www
DB: SQLite - /home/ssoo/www/instance/followup.db
Puerto: 5000 (Flask development server con debug)
URL local: http://localhost:5000 o http://172.23.77.32:5000
Branch: develop
```

### Producción (Oracle Cloud)

```bash
# Tu servidor de producción
IP: 140.238.120.92
User: ubuntu
Path: /home/ubuntu/www
DB: SQLite - /home/ubuntu/www/instance/followup.db
Dominio: https://followup.fit/
Puerto: 5000 (Flask directo, sin Nginx/Gunicorn por ahora)
Branch: main
Servicio: followup.service (systemd)
```

---

## 🚀 PROCESO COMPLETO (EL QUE USAMOS HOY)

### FASE 1: Desarrollo Local

```bash
# 1. Entrar a tu directorio de trabajo
cd /home/ssoo/www

# 2. Activar entorno virtual
source venv/bin/activate

# 3. Asegurarte de estar en develop
git checkout develop
git status

# 4. Desarrollar el feature
# ... editar archivos ...
# ... escribir tests (cuando corresponda) ...
```

```bash
# 5. Probar en desarrollo
python run.py

# Abrir http://localhost:5000
# Probar todas las funcionalidades nuevas
# Probar edge cases
# Presionar Ctrl+C para detener
```

```bash
# 6. Commit en develop
git add .
git status  # Verificar qué archivos se añaden

git commit -m "feat: descripción del feature

- Detalle 1
- Detalle 2
- Tests añadidos (si corresponde)"

# Ejemplo real de hoy:
# git commit -m "feat: Sprint 1 - Complete authentication system
# 
# - Created User model with password hashing
# - Implemented auth forms and routes
# - Built elegant templates with Tailwind CSS"
```

# Convención de mensajes:
# feat: nueva funcionalidad
# fix: arreglo de bug
# refactor: mejora de código sin cambiar funcionalidad
# test: añadir/mejorar tests
# docs: documentación
# style: formato de código
```

### FASE 2: Subir a GitHub

```bash
# 7. Subir develop a GitHub
git push origin develop

# Te pedirá usuario y token/password
# Username: tu-email@gmail.com
# Password: tu-personal-access-token (o contraseña)
```

### FASE 3: Merge a Main

```bash
# 8. Cambiar a main
git checkout main

# 9. Mergear develop en main
git merge develop

# 10. Push main a GitHub
git push origin main
```

### FASE 4: Deploy a Producción

```bash
# 11. Conectar a servidor de producción
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92
```

```bash
# === AHORA ESTÁS EN EL SERVIDOR DE PRODUCCIÓN ===

# 12. Ir al directorio del proyecto
cd ~/www

# 13. Pull del código nuevo desde main
git pull origin main

# 14. Activar entorno virtual
source venv/bin/activate

# 15. Instalar/actualizar dependencias (si cambió requirements.txt)
pip install -r requirements.txt

# 16. Ejecutar migraciones de BD (si hay nuevas tablas/campos)
flask db upgrade

# 17. Reiniciar la aplicación
sudo systemctl restart followup.service

# 18. Verificar que arrancó bien
sudo systemctl status followup.service
# Debe decir "active (running)"

# 19. Ver logs en tiempo real (para detectar errores)
sudo journalctl -u followup.service -f
# Ctrl+C para salir
```

### FASE 5: Validación en Producción

```bash
# 20. Abrir navegador y probar
# URL: https://followup.fit/

# Checklist de validación:
# [ ] La página carga sin errores
# [ ] El nuevo feature funciona correctamente
# [ ] Las funcionalidades anteriores siguen funcionando
# [ ] No hay errores en la consola del navegador
# [ ] No hay errores en los logs del servidor

# 21. Si algo falla:
# - Revisar logs: sudo journalctl -u followup.service -n 100
# - Rollback si es crítico (ver sección ROLLBACK abajo)
```

### FASE 6: Tag de Versión (Opcional - si es hito importante)

```bash
# En desarrollo (WSL)
cd /home/ssoo/www

# Crear tag
git tag v0.X-nombre-descriptivo
# Ejemplos:
# v0.1-auth
# v0.2-expenses
# v0.5-dashboard

# Push del tag
git push origin --tags
```

---

## 🔧 SCRIPTS ÚTILES

### Script de Deploy (`scripts/deploy.sh`)

```bash
#!/bin/bash
# Script de deploy automático

set -e  # Exit on error

echo "🚀 Iniciando deploy a producción..."

# Backup
echo "📦 Haciendo backup de BD..."
pg_dump followup_prod > ~/backups/followup_$(date +%Y%m%d_%H%M%S).sql

# Pull
echo "📥 Descargando código nuevo..."
git pull origin main

# Dependencies
echo "📚 Instalando dependencias..."
source venv/bin/activate
pip install -r requirements.txt

# Migrations
echo "🗄️ Ejecutando migraciones..."
alembic upgrade head

# CSS
echo "🎨 Compilando CSS..."
npm run build:css

# Restart
echo "🔄 Reiniciando aplicación..."
sudo systemctl restart followup

# Status
echo "✅ Deploy completado. Verificando estado..."
sudo systemctl status followup

echo ""
echo "🌐 Aplicación disponible en: https://followup.fit/"
echo "📊 Ver logs: sudo journalctl -u followup -f"
```

Hacer ejecutable:
```bash
chmod +x scripts/deploy.sh
```

Usar:
```bash
cd /home/ubuntu/www/followup
./scripts/deploy.sh
```

### Script de Backup (`scripts/backup.sh`)

```bash
#!/bin/bash
# Backup de base de datos

BACKUP_DIR="/home/ubuntu/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/followup_$DATE.sql"

mkdir -p $BACKUP_DIR

echo "📦 Creando backup: $BACKUP_FILE"
pg_dump followup_prod > $BACKUP_FILE

# Comprimir
gzip $BACKUP_FILE

echo "✅ Backup completado: ${BACKUP_FILE}.gz"

# Eliminar backups antiguos (mantener últimos 30)
find $BACKUP_DIR -name "followup_*.sql.gz" -mtime +30 -delete

echo "🧹 Backups antiguos eliminados (>30 días)"
```

---

## ⚠️ ROLLBACK (Reversión de Deploy)

Si algo sale mal en producción:

```bash
# EN PRODUCCIÓN

# 1. Ver commits recientes
git log --oneline -5

# 2. Volver al commit anterior
git reset --hard <hash-del-commit-anterior>

# Ejemplo:
# git reset --hard abc1234

# 3. Restaurar BD si hiciste migrations
# Encontrar el backup más reciente
ls -lh ~/backups/

# Restaurar
gunzip ~/backups/followup_20251005_143000.sql.gz
psql followup_prod < ~/backups/followup_20251005_143000.sql

# 4. Reiniciar aplicación
sudo systemctl restart followup

# 5. Validar que funciona con la versión anterior
```

---

## 🗄️ GESTIÓN DE BASE DE DATOS

### Migraciones con Alembic

```bash
# EN DESARROLLO: Crear migración después de cambiar modelos
alembic revision --autogenerate -m "descripción del cambio"
# Ejemplo: alembic revision --autogenerate -m "add expense table"

# Revisar el archivo generado en migrations/versions/
# Editar si es necesario

# Aplicar migración localmente
alembic upgrade head

# Probar que funciona

# Commit de la migración
git add migrations/
git commit -m "db: add expense table migration"

# EN PRODUCCIÓN: Aplicar migración
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92
cd /home/ubuntu/www/followup
source venv/bin/activate

# IMPORTANTE: Backup antes de migrar
./scripts/backup.sh

# Aplicar migración
alembic upgrade head

# Verificar que se aplicó
alembic current
```

### Comandos Útiles de Alembic

```bash
# Ver historial de migraciones
alembic history

# Ver estado actual
alembic current

# Ver SQL que ejecutará sin ejecutarlo (dry-run)
alembic upgrade head --sql

# Downgrade (volver atrás)
alembic downgrade -1  # Una migración atrás
alembic downgrade <revision>  # A una revisión específica
```

---

## 🔍 DEBUGGING EN PRODUCCIÓN

### Ver Logs

```bash
# Logs en tiempo real
sudo journalctl -u followup -f

# Últimas 100 líneas
sudo journalctl -u followup -n 100

# Logs con errores solo
sudo journalctl -u followup -p err

# Logs de un período específico
sudo journalctl -u followup --since "1 hour ago"
```

### Acceder a la Base de Datos

```bash
# Conectar a PostgreSQL
psql followup_prod

# Comandos útiles dentro de psql:
\dt              # Listar tablas
\d+ users        # Describir tabla users
SELECT * FROM users LIMIT 10;
\q               # Salir
```

### Verificar Estado de Servicios

```bash
# Estado de la aplicación
sudo systemctl status followup

# Estado de Nginx
sudo systemctl status nginx

# Estado de PostgreSQL
sudo systemctl status postgresql
```

---

## 🛡️ CONFIGURACIÓN INICIAL DE PRODUCCIÓN

### 1. Setup de Nginx

Crear `/etc/nginx/sites-available/followup`:

```nginx
server {
    listen 80;
    server_name followup.fit www.followup.fit;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /home/ubuntu/www/followup/app/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
# Activar configuración
sudo ln -s /etc/nginx/sites-available/followup /etc/nginx/sites-enabled/
sudo nginx -t  # Verificar configuración
sudo systemctl restart nginx
```

### 2. Setup de SSL (Let's Encrypt)

```bash
# Instalar Certbot
sudo apt install certbot python3-certbot-nginx

# Obtener certificado
sudo certbot --nginx -d followup.fit -d www.followup.fit

# Renovación automática (ya configurada por defecto)
sudo certbot renew --dry-run
```

### 3. Setup de Gunicorn como Servicio

Crear `/etc/systemd/system/followup.service`:

```ini
[Unit]
Description=Followup Financial App
After=network.target postgresql.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/www/followup
Environment="PATH=/home/ubuntu/www/followup/venv/bin"
ExecStart=/home/ubuntu/www/followup/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 'app:create_app()'
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Activar servicio
sudo systemctl daemon-reload
sudo systemctl enable followup
sudo systemctl start followup
sudo systemctl status followup
```

---

## 📊 MONITOREO

### Logs Importantes

```bash
# Logs de aplicación
sudo journalctl -u followup

# Logs de Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Logs de PostgreSQL
sudo tail -f /var/log/postgresql/postgresql-16-main.log
```

### Métricas de Sistema

```bash
# Uso de CPU/memoria
top
htop  # Si está instalado

# Espacio en disco
df -h

# Conexiones PostgreSQL activas
psql -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## ✅ CHECKLIST PRE-DEPLOY

Antes de cada deploy, verificar:

- [ ] Tests pasando localmente (`pytest`)
- [ ] Código funcional en desarrollo
- [ ] Commit con mensaje descriptivo
- [ ] Push a main exitoso
- [ ] Backup de BD en producción programado
- [ ] Migraciones probadas localmente (si aplica)

---

## ✅ CHECKLIST POST-DEPLOY

Después de cada deploy, verificar:

- [ ] Aplicación arrancó sin errores
- [ ] No hay errores en logs (`journalctl`)
- [ ] URL https://followup.fit/ carga correctamente
- [ ] Nuevo feature funciona en producción
- [ ] Features anteriores siguen funcionando
- [ ] No hay errores en consola del navegador

---

## 📞 TROUBLESHOOTING

### Problema: Aplicación no arranca

```bash
# Ver logs
sudo journalctl -u followup -n 50

# Verificar que el puerto está libre
sudo netstat -tulpn | grep 5000

# Verificar permisos
ls -la /home/ubuntu/www/followup

# Reintentar
sudo systemctl restart followup
```

### Problema: Error de base de datos

```bash
# Verificar que PostgreSQL está corriendo
sudo systemctl status postgresql

# Conectar a BD
psql followup_prod

# Verificar usuarios
\du

# Verificar permisos
\l
```

### Problema: Nginx devuelve 502

```bash
# Verificar que la app está corriendo
sudo systemctl status followup

# Verificar configuración de Nginx
sudo nginx -t

# Ver logs de Nginx
sudo tail -f /var/log/nginx/error.log
```

---

**Última actualización**: 5 Octubre 2025  
**Próxima revisión**: Después del primer deploy exitoso

