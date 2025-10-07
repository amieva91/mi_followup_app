# 🚨 Reparación de Base de Datos SQLite Corrupta en Producción

## Problema
Error: `sqlite3.DatabaseError: database disk image is malformed`

## Soluciones Disponibles

### 1. 🔧 Script Automático de Reparación

```bash
# Ejecutar el script de reparación automática
python3 fix_database.py
```

### 2. 🚨 Script de Emergencia (Más rápido)

```bash
# Ejecutar reparación básica
./emergency_db_fix.sh
```

### 3. 🔍 Diagnóstico Manual

```bash
# Verificar integridad
sqlite3 site.db "PRAGMA integrity_check;"

# Si está corrupta, intentar reparar
sqlite3 site.db "VACUUM;"

# Verificar nuevamente
sqlite3 site.db "PRAGMA integrity_check;"
```

### 4. 📦 Restauración desde Backup

Si tienes un backup de la base de datos:

```bash
# Detener la aplicación
sudo systemctl stop followup  # o el proceso que esté corriendo

# Restaurar desde backup
cp site.db.backup_YYYYMMDD_HHMMSS site.db

# Reiniciar la aplicación
sudo systemctl start followup
```

### 5. 🆕 Recreación desde Cero (Último recurso)

Si nada funciona, recrear la base de datos:

```bash
# Detener la aplicación
sudo systemctl stop followup

# Hacer backup de la base corrupta
mv site.db site.db.corrupted

# Recrear la base de datos
python3 -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('Base de datos recreada')
"

# Reiniciar la aplicación
sudo systemctl start followup
```

## ⚠️ Consideraciones Importantes

1. **Siempre hacer backup** antes de cualquier reparación
2. **Detener la aplicación** durante la reparación
3. **Verificar permisos** de archivos y directorios
4. **Comprobar espacio en disco** disponible

## 🔄 Prevención Futura

Para evitar futuras corrupciones:

1. **Usar WAL mode** (ya implementado)
2. **Hacer backups regulares**
3. **Usar un servidor WSGI** en lugar del servidor de desarrollo
4. **Configurar logging** para detectar problemas temprano

## 📞 Comandos de Verificación

```bash
# Verificar que la aplicación funciona
python3 app.py

# Verificar integridad después de reparación
sqlite3 site.db "PRAGMA integrity_check;"

# Verificar tablas
sqlite3 site.db ".tables"

# Verificar usuarios
sqlite3 site.db "SELECT COUNT(*) FROM user;"
```

## 🎯 Orden Recomendado de Ejecución

1. Ejecutar `./emergency_db_fix.sh`
2. Si falla, ejecutar `python3 fix_database.py`
3. Si sigue fallando, restaurar desde backup
4. Como último recurso, recrear la base de datos
