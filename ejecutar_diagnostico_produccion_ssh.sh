#!/bin/bash
# Script para ejecutar diagnóstico en producción vía SSH

echo "🔍 Ejecutando diagnóstico de depósitos IBKR en producción..."
echo ""

ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92 << 'ENDSSH'
cd ~/www
source venv/bin/activate

echo "📊 Ejecutando verificación de depósitos..."
python verificar_depositos_produccion.py

echo ""
echo "📊 Ejecutando simulación de importación..."
python simular_importacion_depositos.py

ENDSSH

echo ""
echo "✅ Diagnóstico completado"

