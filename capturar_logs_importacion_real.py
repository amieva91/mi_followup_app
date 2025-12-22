#!/usr/bin/env python3
"""
Script para capturar logs durante una importación REAL de CSV
Captura todos los prints y logs del proceso de importación
"""
import sys
import os
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr

# Crear directorio de logs
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f"importacion_depositos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

print(f"📝 Iniciando captura de logs en: {log_file}")
print(f"⚠️  IMPORTANTE: Este script capturará TODOS los logs durante la importación")
print(f"   Para usar: ejecuta una importación desde la web y los logs se guardarán aquí")
print(f"")
print(f"📋 Para capturar logs durante importación:")
print(f"   1. Abre otra terminal y ejecuta: tail -f {log_file}")
print(f"   2. O ejecuta este script antes de hacer la importación")
print(f"")

# Redirigir stdout y stderr a archivo
class TeeOutput:
    """Clase para escribir tanto a archivo como a consola"""
    def __init__(self, file, console):
        self.file = file
        self.console = console
    
    def write(self, text):
        self.file.write(text)
        self.file.flush()
        self.console.write(text)
        self.console.flush()
    
    def flush(self):
        self.file.flush()
        self.console.flush()

# Guardar referencias originales
original_stdout = sys.stdout
original_stderr = sys.stderr

# Abrir archivo de log
log_f = open(log_file, 'w', encoding='utf-8')

# Crear Tee que escribe a ambos
tee_stdout = TeeOutput(log_f, original_stdout)
tee_stderr = TeeOutput(log_f, original_stderr)

# Redirigir
sys.stdout = tee_stdout
sys.stderr = tee_stderr

print(f"="*80)
print(f"LOGS DE IMPORTACIÓN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"="*80)
print(f"")

try:
    # Importar y ejecutar el script de verificación
    print("🔍 Ejecutando verificación de depósitos...")
    print("")
    
    # Ejecutar el script de verificación
    with open('verificar_depositos_produccion.py', 'r', encoding='utf-8') as f:
        code = compile(f.read(), 'verificar_depositos_produccion.py', 'exec')
        exec(code, {'__name__': '__main__'})
    
    print("")
    print("="*80)
    print("✅ Verificación completada")
    print("="*80)
    
except Exception as e:
    print(f"")
    print("="*80)
    print(f"❌ ERROR durante la verificación: {e}")
    print("="*80)
    import traceback
    traceback.print_exc()
finally:
    # Restaurar stdout/stderr
    sys.stdout = original_stdout
    sys.stderr = original_stderr
    log_f.close()
    
    print(f"")
    print(f"✅ Logs guardados en: {log_file}")
    print(f"📊 Tamaño del archivo: {os.path.getsize(log_file)} bytes")

