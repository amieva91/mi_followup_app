#!/bin/bash
# Script de backup de base de datos
# Uso: ./scripts/backup.sh

BACKUP_DIR="$HOME/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/followup_$DATE.db"

mkdir -p $BACKUP_DIR

echo "📦 Creando backup: $BACKUP_FILE"

if [ -f "instance/followup.db" ]; then
    cp instance/followup.db $BACKUP_FILE
    
    # Comprimir
    gzip $BACKUP_FILE
    
    echo "✅ Backup completado: ${BACKUP_FILE}.gz"
    
    # Eliminar backups antiguos (mantener últimos 30 días)
    find $BACKUP_DIR -name "followup_*.db.gz" -mtime +30 -delete
    
    echo "🧹 Backups antiguos eliminados (>30 días)"
else
    echo "❌ Error: No se encontró la base de datos en instance/followup.db"
    exit 1
fi

