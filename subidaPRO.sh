#!/bin/bash
# Script de deploy a producción (unificado y optimizado)
# Uso: ./subidaPRO.sh
#
# Requiere: SSH key en ~/.ssh/ssh-key-2025-08-21.key
# Producción: Oracle Cloud 140.238.120.92 (ubuntu@) o configurar GCP

set -e  # Exit on error

# Configuración
SSH_KEY="${SSH_KEY:-$HOME/.ssh/ssh-key-2025-08-21.key}"
SSH_HOST="${SSH_HOST:-ubuntu@140.238.120.92}"

echo "🚀 Iniciando deploy a producción ($SSH_HOST)..."
echo ""

ssh -T -o BatchMode=yes -o ConnectTimeout=15 \
    -i "$SSH_KEY" "$SSH_HOST" 'bash -s' << 'REMOTE_SCRIPT'
cd ~/www

# Backup de BD
echo "📦 Haciendo backup de BD..."
mkdir -p ~/backups
if [ -f instance/followup.db ]; then
    cp instance/followup.db ~/backups/followup_$(date +%Y%m%d_%H%M%S).db
    echo "   ✓ Backup creado"
elif [ -f instance/app.db ]; then
    cp instance/app.db ~/backups/app_$(date +%Y%m%d_%H%M%S).db
    echo "   ✓ Backup creado (app.db)"
else
    echo "   ⚠️  No se encontró BD para backup"
fi

# Pull código
echo "📥 Descargando cambios desde main..."
git fetch origin
git pull origin main
echo "   ✓ Código actualizado"

# Activar venv
source venv/bin/activate

# Instalar/comprobar dependencias
echo "📚 Comprobando dependencias..."
pip install -r requirements.txt --quiet
echo "   ✓ Dependencias OK"

# Migraciones
echo "🗄️  Aplicando migraciones..."
export FLASK_APP=run.py
flask db upgrade
echo "   ✓ Migraciones aplicadas"

# Reiniciar servicio
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
echo "📊 Ver logs: ssh -i $SSH_KEY $SSH_HOST 'sudo journalctl -u followup.service -f'"
