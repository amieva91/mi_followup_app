#!/bin/bash
# Script para ejecutar diagnóstico de depósitos en producción
# Captura todos los logs durante la verificación

echo "🔍 Iniciando diagnóstico de depósitos IBKR en producción..."
echo ""

# Crear directorio de logs si no existe
mkdir -p logs

# Ejecutar script de verificación y capturar logs
LOG_FILE="logs/diagnostico_depositos_$(date +%Y%m%d_%H%M%S).log"

echo "📝 Capturando logs en: $LOG_FILE"
echo ""

# Activar venv y ejecutar script, redirigiendo todo a log
source venv/bin/activate
python verificar_depositos_produccion.py 2>&1 | tee "$LOG_FILE"

echo ""
echo "✅ Diagnóstico completado"
echo "📄 Logs guardados en: $LOG_FILE"
echo ""
echo "📊 Resumen del log:"
echo "---"
tail -50 "$LOG_FILE"

