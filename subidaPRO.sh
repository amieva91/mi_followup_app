#!/bin/bash
# Script de deploy a producción (unificado y optimizado)
# Uso: ./subidaPRO.sh

set -e  # Exit on error

echo "🚀 Iniciando deploy a producción..."
echo ""

ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92 << 'EOF'
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

# Instalar dependencias (solo si cambió requirements.txt)
if git diff HEAD@{1} HEAD --name-only | grep -q "requirements.txt"; then
    echo "📚 Instalando dependencias nuevas..."
    pip install -r requirements.txt --quiet
    echo "   ✓ Dependencias actualizadas"
else
    echo "📚 Sin cambios en dependencias"
fi

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

EOF

echo ""
echo "🌐 Aplicación disponible en: https://followup.fit/"
echo "📊 Ver logs: ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92 'sudo journalctl -u followup.service -f'"
