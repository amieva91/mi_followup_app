#!/bin/bash
# Script de deploy automático a producción
# Uso: ./scripts/deploy.sh

set -e  # Exit on error

echo "🚀 Iniciando deploy a producción..."
echo ""

# Colores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Información del servidor
SERVER_USER="ubuntu"
SERVER_IP="140.238.120.92"
SERVER_PATH="/home/ubuntu/www"
SSH_KEY="~/.ssh/ssh-key-2025-08-21.key"

echo -e "${BLUE}📦 Paso 1: Backup de BD en producción...${NC}"
ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP << 'ENDSSH'
    cd ~/www
    mkdir -p ~/backups
    BACKUP_FILE=~/backups/followup_$(date +%Y%m%d_%H%M%S).db
    if [ -f instance/followup.db ]; then
        cp instance/followup.db $BACKUP_FILE
        echo "✅ Backup creado: $BACKUP_FILE"
    else
        echo "⚠️  No se encontró BD para backup"
    fi
ENDSSH

echo ""
echo -e "${BLUE}📥 Paso 2: Descargando código nuevo desde main...${NC}"
ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP << 'ENDSSH'
    cd ~/www
    git pull origin main
    echo "✅ Código actualizado"
ENDSSH

echo ""
echo -e "${BLUE}📚 Paso 3: Instalando dependencias...${NC}"
ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP << 'ENDSSH'
    cd ~/www
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    echo "✅ Dependencias actualizadas"
ENDSSH

echo ""
echo -e "${BLUE}🗄️  Paso 4: Ejecutando migraciones de BD...${NC}"
ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP << 'ENDSSH'
    cd ~/www
    source venv/bin/activate
    flask db upgrade
    echo "✅ Migraciones aplicadas"
ENDSSH

echo ""
echo -e "${BLUE}🔄 Paso 5: Reiniciando aplicación...${NC}"
ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP << 'ENDSSH'
    sudo systemctl restart followup.service
    echo "✅ Servicio reiniciado"
ENDSSH

echo ""
echo -e "${BLUE}✅ Paso 6: Verificando estado...${NC}"
ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP << 'ENDSSH'
    sudo systemctl status followup.service --no-pager -l
ENDSSH

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Deploy completado exitosamente${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "🌐 Aplicación disponible en: ${BLUE}https://followup.fit/${NC}"
echo -e "📊 Ver logs: ${YELLOW}ssh -i $SSH_KEY $SERVER_USER@$SERVER_IP 'sudo journalctl -u followup.service -f'${NC}"
echo ""

