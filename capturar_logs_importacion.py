#!/usr/bin/env python3
"""
Script para capturar logs durante la importación de CSV
Ejecuta el script de verificación y captura todos los logs a un archivo
"""
import sys
import os
from datetime import datetime

# Redirigir stdout y stderr a un archivo
log_file = f"logs/importacion_depositos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
os.makedirs('logs', exist_ok=True)

print(f"📝 Capturando logs en: {log_file}")
print(f"🔍 Ejecutando verificación de depósitos...\n")

# Redirigir stdout y stderr
original_stdout = sys.stdout
original_stderr = sys.stderr

with open(log_file, 'w', encoding='utf-8') as f:
    sys.stdout = f
    sys.stderr = f
    
    try:
        # Ejecutar el script de verificación
        exec(open('verificar_depositos_produccion.py').read())
    except Exception as e:
        print(f"\n❌ Error ejecutando script: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr

print(f"\n✅ Logs capturados en: {log_file}")
print(f"📄 Revisa el archivo para ver los detalles de la importación")

