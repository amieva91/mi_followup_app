# Instrucciones: Capturar Logs de Importación en Producción

## 📋 Configuración Realizada

1. ✅ **Logging a archivo configurado** en `app/__init__.py`
   - Los logs se guardan en `logs/followup.log` en producción
   - Rotación automática (10MB por archivo, 10 backups)

2. ✅ **Logger específico para importaciones** en `app/services/importer_v2.py`
   - Captura mensajes específicos de depósitos

3. ✅ **Scripts de diagnóstico creados**:
   - `verificar_depositos_produccion.py` - Verifica depósitos en DB vs CSV
   - `ejecutar_diagnostico_produccion.sh` - Ejecuta diagnóstico y captura logs
   - `capturar_logs_importacion_real.py` - Captura logs durante importación

## 🚀 Cómo Ejecutar en Producción

### Opción 1: Ejecutar Diagnóstico (Recomendado)

```bash
# En producción, ejecutar:
cd /home/ubuntu/www  # o la ruta donde esté el proyecto
chmod +x ejecutar_diagnostico_produccion.sh
./ejecutar_diagnostico_produccion.sh
```

Este script:
- Ejecuta la verificación de depósitos
- Captura todos los logs en `logs/diagnostico_depositos_YYYYMMDD_HHMMSS.log`
- Muestra un resumen al final

### Opción 2: Capturar Logs Durante Importación Real

1. **Antes de hacer la importación desde la web**, ejecuta en una terminal:

```bash
cd /home/ubuntu/www
source venv/bin/activate
python capturar_logs_importacion_real.py
```

2. **En otra terminal**, monitorea el log en tiempo real:

```bash
tail -f logs/importacion_depositos_*.log
```

3. **Haz la importación desde la web** (sube el CSV de IBKR)

4. **Los logs se capturarán automáticamente** en el archivo

### Opción 3: Ver Logs del Sistema (Gunicorn/Systemd)

Si la aplicación corre con systemd, los logs también están en:

```bash
# Ver logs del servicio
sudo journalctl -u followup.service -f

# Ver últimas 100 líneas
sudo journalctl -u followup.service -n 100
```

## 📊 Qué Buscar en los Logs

### Mensajes Importantes:

1. **Depósitos parseados del CSV**:
   ```
   💰 Depósitos parseados del CSV: X
   ```

2. **Depósitos duplicados saltados**:
   ```
   ⏭️  Depósito duplicado saltado: YYYY-MM-DD | AMOUNT EUR | DESCRIPTION
   ```

3. **Resumen de depósitos**:
   ```
   📥 Depósitos en CSV: X, Importados: Y, Saltados (duplicados): Z
   ```

4. **Advertencias**:
   ```
   ⚠️  ADVERTENCIA: Depósito sin fecha - Saltado
   ```

### Si los depósitos NO se están importando:

Buscar en los logs:
- ¿Se parsean los depósitos del CSV? (debe mostrar "Depósitos parseados del CSV: 6")
- ¿Se saltan como duplicados? (debe mostrar "Depósito duplicado saltado")
- ¿Hay errores? (buscar "ERROR", "Exception", "Traceback")
- ¿Hay advertencias de fecha? (buscar "ADVERTENCIA: Depósito sin fecha")

## 📁 Ubicación de Archivos de Log

- **Logs de aplicación**: `logs/followup.log`
- **Logs de diagnóstico**: `logs/diagnostico_depositos_*.log`
- **Logs de importación**: `logs/importacion_depositos_*.log`

## 🔍 Análisis de Logs

Después de ejecutar el diagnóstico, revisar:

1. **¿Cuántos depósitos hay en el CSV?**
   - Debe ser 6 para el CSV completo

2. **¿Cuántos depósitos hay en la DB?**
   - Si es 0, deberían importarse
   - Si es 6, se saltarán como duplicados (correcto)

3. **¿Hay coincidencias exactas?**
   - Si todos coinciden → Funciona correctamente (duplicados)
   - Si no coinciden → Hay un problema

## 📤 Enviar Logs para Análisis

Para que pueda revisar los logs:

1. Ejecutar el diagnóstico
2. Copiar el archivo de log generado
3. Enviarlo para análisis

```bash
# El archivo estará en:
logs/diagnostico_depositos_YYYYMMDD_HHMMSS.log
```

