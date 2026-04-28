#!/bin/bash
# Script de deploy a producción (unificado y optimizado)
# Uso: ./subidaPRO.sh
#
# Usa gcloud compute ssh (sin timeouts de firewall)
# Producción: GCP VM followup (gen-lang-client-0658912226)

set -e  # Exit on error

# Configuración GCP (misma que scripts/connect-gcp.sh)
PROJECT="gen-lang-client-0658912226"
INSTANCE="followup"
ZONE="us-central1-c"

gcloud config set project "$PROJECT" 2>/dev/null

echo "🚀 Iniciando deploy a producción (GCP: $INSTANCE)..."
echo ""

gcloud compute ssh "$INSTANCE" --zone="$ZONE" --command="bash -s" << 'REMOTE_SCRIPT'
APP_DIR="/var/www/followup"
# Ejecutar deploy con sudo (acceso completo a /var/www/followup)
sudo bash -s << 'DEPLOY_STEPS'
APP_DIR="/var/www/followup"
cd "$APP_DIR"

# Backup de BD (en directorio de la app, con permisos www-data)
echo "📦 Haciendo backup de BD..."
mkdir -p "$APP_DIR/backups"
if [ -f instance/followup.db ]; then
    cp instance/followup.db "$APP_DIR/backups/followup_$(date +%Y%m%d_%H%M%S).db"
    echo "   ✓ Backup creado"
elif [ -f instance/app.db ]; then
    cp instance/app.db "$APP_DIR/backups/app_$(date +%Y%m%d_%H%M%S).db"
    echo "   ✓ Backup creado (app.db)"
else
    echo "   ⚠️  No se encontró BD para backup"
fi

# Código en main (checkout explícito: si el servidor estaba en otra rama, p. ej. experimental)
echo "📥 Descargando cambios desde main..."
git -c safe.directory=/var/www/followup fetch origin
git -c safe.directory=/var/www/followup checkout main
git -c safe.directory=/var/www/followup pull origin main
echo "   ✓ Código actualizado (rama main)"

# Activar venv
source venv/bin/activate

# Instalar/comprobar dependencias
echo "📚 Comprobando dependencias..."
pip install --no-cache-dir -r requirements.txt --quiet
echo "   ✓ Dependencias OK"

echo "🎭 Playwright (Chromium para PDF del informe)..."
export PLAYWRIGHT_BROWSERS_PATH=0
python -m playwright install-deps chromium 2>/dev/null || true
python -m playwright install chromium
echo "   ✓ Chromium OK"

# Migraciones (para reset completo de BD en producción: ./scripts/reset_db_production.sh)
echo "🗄️  Aplicando migraciones..."
export FLASK_APP=run.py
export FLASK_ENV=production
flask db upgrade
echo "   ✓ Migraciones aplicadas"
DEPLOY_STEPS

# Reiniciar servicio (fuera del bloque www-data)
echo "🔄 Reiniciando aplicación..."
sudo systemctl restart followup.service
echo "   ✓ Servicio reiniciado"

# Estado final
echo ""
echo "=========================================="
echo "✅ Deploy completado exitosamente"
echo "=========================================="
echo ""
sudo systemctl status followup.service --no-pager -l

REMOTE_SCRIPT

echo ""
echo "🌐 Aplicación disponible en: https://followup.fit/"
echo "📊 Ver logs: ./scripts/connect-gcp.sh 'sudo journalctl -u followup.service -f'"
