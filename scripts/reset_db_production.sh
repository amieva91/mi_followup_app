#!/bin/bash
# Resetea la BD en producción: backup, borra la BD actual y crea una nueva con
# flask db upgrade (esquema actual). Solo usuarios de prueba; los datos se pierden.
#
# Uso (desde tu máquina):
#   ./scripts/reset_db_production.sh
#
# Requiere: connect-gcp.sh (gcloud configurado)

set -e
cd "$(dirname "$0")/.."
PROJECT="gen-lang-client-0658912226"
INSTANCE="followup"
ZONE="us-central1-c"

echo "⚠️  Esto borrará la BD de producción y creará una nueva vacía."
echo "   Se hará backup antes en backups/"
read -p "¿Continuar? (escribe sí): " confirm
if [ "$confirm" != "sí" ]; then
  echo "Cancelado."
  exit 0
fi

gcloud config set project "$PROJECT" 2>/dev/null
gcloud compute ssh "$INSTANCE" --zone="$ZONE" --command="bash -s" << 'REMOTE'
set -e
APP_DIR="/var/www/followup"
cd "$APP_DIR"

echo "📦 Backup de la BD..."
sudo mkdir -p "$APP_DIR/backups"
if [ -f instance/followup.db ]; then
  sudo cp instance/followup.db "$APP_DIR/backups/followup_$(date +%Y%m%d_%H%M%S).db"
  echo "   ✓ Backup creado"
fi

echo "🗑️  Eliminando BD actual..."
sudo rm -f instance/followup.db instance/app.db
echo "   ✓ BD eliminada"

echo "🗄️  Creando BD nueva (flask db upgrade)..."
sudo -u followup bash -c "cd $APP_DIR && source venv/bin/activate && export FLASK_APP=run.py && export FLASK_ENV=production && flask db upgrade"
echo "   ✓ Esquema creado"

echo "🔄 Reiniciando servicio..."
sudo systemctl restart followup.service
echo "   ✓ Listo"

echo ""
echo "✅ BD de producción reseteada. Puedes registrar usuarios de prueba de nuevo."
REMOTE
