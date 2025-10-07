# 🚀 MIGRACIÓN A PRODUCCIÓN - COMANDOS ESPECÍFICOS

## 📋 **RESUMEN DE CAMBIOS A MIGRAR**

### **🗑️ Tablas Eliminadas:**
- `goals` (0 registros)
- `goal_progress` (0 registros) 
- `goal_history` (0 registros)
- `alert_configuration` (0 registros)
- `mailbox_message` (0 registros)
- `email_queue` (0 registros)
- `historical_metal_price` (0 registros)

### **🧹 Código Actualizado:**
- **app.py**: Eliminados modelos no utilizados, función `get_historical_metal_price_eur()` modificada
- **models.py**: Eliminados modelos no utilizados
- **routes.py**: Importaciones limpiadas
- **templates/base.html**: Contador de mensajes eliminado

---

## 🔄 **COMANDOS PARA MIGRAR A PRODUCCIÓN**

### **1. Desde tu máquina de desarrollo:**

```bash
# Copiar archivos de la aplicación (incluyendo el script de migración)
scp -i .ssh/ssh-key-2025-08-21.key -r /home/ssoo/www/* ubuntu@140.238.120.92:/home/ubuntu/www/

# Copiar la base de datos actualizada (opcional - solo si quieres usar la de desarrollo)
scp -i .ssh/ssh-key-2025-08-21.key /home/ssoo/www/site.db ubuntu@140.238.120.92:/home/ubuntu/www/
```

### **2. En el servidor de producción:**

```bash
# Conectar al servidor
ssh -i .ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92

# Navegar al directorio de la aplicación
cd /home/ubuntu/www

# Verificar que los archivos se copiaron correctamente
ls -la

# Verificar que el script de migración está presente
ls -la migrate_database.py
```

### **3. Ejecutar el script de migración:**

```bash
# Hacer el script ejecutable
chmod +x migrate_database.py

# Ejecutar la migración de base de datos
python3 migrate_database.py
```

### **4. Reiniciar el servicio:**

```bash
# Detener el servicio
sudo systemctl stop followup.service

# Reiniciar el servicio
sudo systemctl start followup.service

# Verificar estado
sudo systemctl status followup.service

# Verificar que la aplicación esté corriendo
ps aux | grep python3 | grep app.py

# Verificar puerto
sudo netstat -tlnp | grep :5000
```

---

## 🔧 **SCRIPT COMPLETO DE MIGRACIÓN**

### **Crear archivo `migrate_to_production.sh` en el servidor:**

```bash
#!/bin/bash
# Script completo de migración a producción

echo "🔄 Iniciando migración completa a producción..."

# 1. Detener el servicio
echo "🛑 Deteniendo servicio followup..."
sudo systemctl stop followup.service

# 2. Verificar que no haya procesos restantes
echo "🔍 Verificando que no haya procesos restantes..."
ps aux | grep python3 | grep app.py
if [ $? -eq 0 ]; then
    echo "⚠️  Aún hay procesos corriendo, matándolos..."
    sudo pkill -f "python3.*app.py"
    sleep 2
fi

# 3. Crear backup con timestamp
echo "📦 Creando backup..."
BACKUP_DIR="/home/ubuntu/www_backup_$(date +%Y%m%d_%H%M%S)"
sudo cp -r /home/ubuntu/www "$BACKUP_DIR"
echo "✅ Backup creado en: $BACKUP_DIR"

# 4. Verificar que los archivos están presentes
echo "🔍 Verificando archivos..."
if [ -f "app.py" ] && [ -f "migrate_database.py" ]; then
    echo "✅ Archivos principales presentes"
else
    echo "❌ Error: Archivos principales no encontrados"
    exit 1
fi

# 5. Instalar dependencias
echo "📦 Instalando dependencias..."
sudo pip3 install -r requirements.txt --break-system-packages

# 6. Verificar sintaxis
echo "✅ Verificando sintaxis..."
python3 -c "import ast; ast.parse(open('app.py').read()); print('✅ Sintaxis correcta')"

if [ $? -ne 0 ]; then
    echo "❌ Error de sintaxis en app.py"
    exit 1
fi

# 7. Ejecutar migración de base de datos
echo "🗄️ Ejecutando migración de base de datos..."
python3 migrate_database.py

if [ $? -ne 0 ]; then
    echo "❌ Error en la migración de base de datos"
    exit 1
fi

# 8. Reiniciar el servicio
echo "🚀 Reiniciando servicio..."
sudo systemctl enable followup.service
sudo systemctl start followup.service

# 9. Verificar estado
echo "🔍 Verificando estado del servicio..."
sudo systemctl status followup.service

# 10. Verificar que la aplicación esté corriendo
echo "🔍 Verificando procesos..."
ps aux | grep python3 | grep app.py

# 11. Verificar puerto
echo "🌐 Verificando puerto 5000..."
sudo netstat -tlnp | grep :5000

# 12. Verificar logs
echo "📋 Últimos logs del servicio:"
sudo journalctl -u followup.service --no-pager -n 10

echo ""
echo "🎉 ¡Migración completada!"
echo "📦 Backup guardado en: $BACKUP_DIR"
echo "🌐 La aplicación debería estar funcionando en: http://140.238.120.92:5000"
echo ""
echo "📝 Para ver logs en tiempo real:"
echo "sudo journalctl -u followup.service -f"
```

---

## ⚠️ **CONSIDERACIONES IMPORTANTES**

### **1. Backup Automático:**
- El script crea un backup automático antes de cualquier cambio
- La base de datos se respalda con timestamp

### **2. Verificaciones de Seguridad:**
- Verifica que los archivos principales estén presentes
- Verifica la sintaxis de la aplicación
- Verifica que el servicio se reinicie correctamente

### **3. Migración de Base de Datos:**
- El script `migrate_database.py` elimina solo las tablas no utilizadas
- Crea backup automático de la base de datos
- Verifica que las tablas importantes sigan funcionando

### **4. Rollback en Caso de Problemas:**
```bash
# Si algo sale mal, restaurar desde backup:
sudo systemctl stop followup.service
sudo cp -r /home/ubuntu/www_backup_YYYYMMDD_HHMMSS/* /home/ubuntu/www/
sudo systemctl start followup.service
```

---

## 🧪 **PRUEBAS POST-MIGRACIÓN**

### **1. Verificar Funcionalidades Básicas:**
- ✅ Login de usuario
- ✅ Dashboard principal
- ✅ Metales preciosos (oro y plata)
- ✅ Crypto portfolio
- ✅ Reportes financieros

### **2. Verificar que las Tablas Eliminadas No Causan Errores:**
- ✅ No errores de importación
- ✅ No referencias a tablas eliminadas
- ✅ Aplicación arranca correctamente

### **3. Verificar Logs:**
```bash
# Ver logs en tiempo real
sudo journalctl -u followup.service -f

# Ver logs de errores
sudo journalctl -u followup.service --no-pager | grep -i error
```

---

## 📞 **COMANDOS DE EMERGENCIA**

### **Si la aplicación no arranca:**
```bash
# Ver logs detallados
sudo journalctl -u followup.service --no-pager -n 50

# Verificar sintaxis
python3 -c "import ast; ast.parse(open('app.py').read())"

# Probar importación manual
python3 -c "from app import app; print('✅ Aplicación importa correctamente')"
```

### **Si hay problemas con la base de datos:**
```bash
# Verificar estructura de la base de datos
sqlite3 site.db ".tables"

# Verificar tablas importantes
sqlite3 site.db "SELECT COUNT(*) FROM user;"
sqlite3 site.db "SELECT COUNT(*) FROM precious_metal_price;"
```

---

## 🎯 **RESUMEN DE COMANDOS**

### **Secuencia completa:**
1. **Copiar archivos**: `scp -i .ssh/ssh-key-2025-08-21.key -r /home/ssoo/www/* ubuntu@140.238.120.92:/home/ubuntu/www/`
2. **Conectar al servidor**: `ssh -i .ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92`
3. **Ejecutar migración**: `python3 migrate_database.py`
4. **Reiniciar servicio**: `sudo systemctl restart followup.service`
5. **Verificar estado**: `sudo systemctl status followup.service`

**¡La migración está lista para ejecutarse!** 🚀
