#!/usr/bin/env bash
#
# Publica en la VM de producción (GCP) una rama ya existente en origin
# (por defecto ui/dashboard-layout-experiments) para probarla antes de mergear a main.
#
# Requisitos: gcloud instalado, autenticado y acceso SSH a la instancia.
#
# Uso:
#   ./scripts/deploy-experimental-branch.sh
#   ./scripts/deploy-experimental-branch.sh otra/rama
#
#   EXPERIMENTAL_BRANCH=ui/dashboard-layout-experiments ./scripts/deploy-experimental-branch.sh
#
# Volver a la rama de producción habitual (main): ./subidaPRO.sh
#
set -euo pipefail

PROJECT="gen-lang-client-0658912226"
INSTANCE="followup"
ZONE="us-central1-c"
DEFAULT_BRANCH="ui/dashboard-layout-experiments"

BRANCH="${EXPERIMENTAL_BRANCH:-${1:-$DEFAULT_BRANCH}}"

gcloud config set project "$PROJECT" >/dev/null

echo "🚀 Deploy rama experimental → ${INSTANCE} (${ZONE})"
echo "   Rama remota: origin/${BRANCH}"
echo ""

# Un solo heredoc sin comillas: ${BRANCH} se sustituye en tu máquina antes del SSH.
gcloud compute ssh "$INSTANCE" --zone="$ZONE" --command="bash -s" << EOF
set -euo pipefail
sudo bash -s << INNER
set -euo pipefail
cd /var/www/followup

echo "📦 Backup de BD..."
mkdir -p /var/www/followup/backups
if [ -f instance/followup.db ]; then
  cp instance/followup.db /var/www/followup/backups/followup_\$(date +%Y%m%d_%H%M%S).db
  echo "   ✓ Backup creado"
elif [ -f instance/app.db ]; then
  cp instance/app.db /var/www/followup/backups/app_\$(date +%Y%m%d_%H%M%S).db
  echo "   ✓ Backup creado (app.db)"
else
  echo "   ⚠️  No se encontró BD para backup"
fi

echo "📥 Fetch y checkout: ${BRANCH}"
git -c safe.directory=/var/www/followup fetch origin "+refs/heads/${BRANCH}:refs/remotes/origin/${BRANCH}"
git -c safe.directory=/var/www/followup checkout -B "${BRANCH}" "origin/${BRANCH}"
git -c safe.directory=/var/www/followup log -1 --oneline
echo "   ✓ HEAD en ${BRANCH}"

echo "📚 Dependencias..."
source venv/bin/activate
pip install --no-cache-dir -r requirements.txt --quiet
echo "   ✓ pip OK"

echo "🗄️  Migraciones..."
export FLASK_APP=run.py
export FLASK_ENV=production
flask db upgrade
echo "   ✓ Migraciones OK"
INNER

echo "🔄 Reiniciando aplicación..."
sudo systemctl restart followup.service
sleep 2
sudo systemctl is-active followup.service
echo ""
echo "=========================================="
echo "✅ Rama experimental desplegada: ${BRANCH}"
echo "🌐 https://followup.fit/"
echo "=========================================="
EOF
