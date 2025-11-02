# 🚀 DEPLOY A PRODUCCIÓN - v3.3.4

**Fecha**: 21 Octubre 2025  
**Versión**: v3.3.4 - MappingRegistry + Fixes de Estabilidad  
**Branch**: develop → main → producción

---

## ✅ CAMBIOS EN ESTA VERSIÓN

### **Nuevas Funcionalidades**

1. **MappingRegistry - Sistema de Mapeos Editables**
   - Nueva tabla `mapping_registry` para mapeos configurables
   - Interfaz web `/portfolio/mappings` con CRUD completo
   - Mappers dinámicos que leen de BD
   - Acceso bidireccional desde AssetRegistry

2. **AssetRegistry - Mejoras**
   - Columna "Uso" ahora ordenable con tooltip
   - Botón de enriquecimiento directo en modal de edición
   - Campo para URL de Yahoo Finance en modal
   - Estado correcto: solo requiere symbol (MIC opcional)

### **Correcciones de Bugs**

3. **Progreso de Importación**
   - Primer archivo ahora visible en "Completados"
   - Conteo correcto: 5/5 en lugar de 4/5
   - Fix de índices 0-based en bucle de archivos

4. **Botones de Enriquecimiento**
   - Funcionales en edición de transacciones
   - Validación de campos antes de actualizar
   - Banners detallados con feedback visual

5. **Estado de AssetRegistry**
   - Lógica actualizada: solo requiere `symbol`
   - Assets con symbol pero sin MIC ahora muestran "✓ Enriquecido"

---

## 📋 PRE-DEPLOY CHECKLIST

### En DESARROLLO

- [x] **1. Commit de todos los cambios**
```bash
git add .
git commit -m "v3.3.4: MappingRegistry + Fixes de estabilidad"
```

- [x] **2. Verificar que todo funciona localmente**
  - Importación de múltiples CSVs (primer archivo visible)
  - Botones de enriquecimiento en transacciones
  - AssetRegistry: columna Uso ordenable
  - MappingRegistry: CRUD completo funcional

- [x] **3. Push a branch develop**
```bash
git push origin develop
```

- [ ] **4. Merge a main**
```bash
git checkout main
git merge develop
git push origin main
```

### En PRODUCCIÓN (Opcional - Manual)

- [ ] **5. Backup manual de BD** (el script ya lo hace automáticamente)
```bash
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92
cd ~/www
cp instance/app.db instance/app.db.backup_manual_$(date +%Y%m%d_%H%M%S)
exit
```

---

## 🚀 COMANDOS DE DEPLOY

### **Opción 1: Deploy Automático (RECOMENDADO)**

Ejecuta el script que hace todo automáticamente:

```bash
bash subidaPRO.sh
```

Este script hace:
1. ✅ Backup automático de la BD
2. ✅ Pull de cambios desde `origin main`
3. ✅ Activa el virtualenv
4. ✅ Aplica migraciones (`flask db upgrade`)
5. ✅ Reinicia el servicio
6. ✅ Muestra el estado del servicio

---

### **Opción 2: Deploy Manual (Paso a Paso)**

Si prefieres hacerlo manualmente:

```bash
# 1. Conectar a producción
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92

# 2. Ir al directorio
cd ~/www

# 3. Backup de BD
cp instance/app.db instance/app.db.backup_$(date +%Y%m%d_%H%M%S)

# 4. Pull de cambios
git fetch origin
git pull origin main

# 5. Activar virtualenv
source venv/bin/activate

# 6. Aplicar migraciones
export FLASK_APP=run.py
flask db upgrade

# 7. Poblar MappingRegistry (si es primera vez)
python populate_mappings.py

# 8. Reiniciar servicio
sudo systemctl restart followup

# 9. Verificar estado
sudo systemctl status followup --no-pager -l

# 10. Salir
exit
```

---

## 🧪 POST-DEPLOY TESTING

Una vez desplegado, verifica que todo funciona:

### **1. Acceder a la aplicación**
- URL: https://followup.fit/
- Login con tu usuario

### **2. Verificar MappingRegistry**
```
1. Ve a /portfolio/asset-registry
2. Haz clic en "🗺️ Gestionar Mapeos"
3. Verifica que aparecen los mapeos (MIC→Yahoo, Exchange→Yahoo, DeGiro→IBKR)
4. Prueba crear un nuevo mapeo
5. Prueba editar uno existente
6. Prueba desactivar/activar
```

### **3. Verificar AssetRegistry**
```
1. Ve a /portfolio/asset-registry
2. Verifica que la columna "Uso" es ordenable (click en el encabezado)
3. Haz clic en "✏️ Editar" de cualquier asset
4. Verifica que aparece el botón "🔍 Enriquecer con OpenFIGI" dentro del modal
5. Verifica que aparece el campo "Yahoo URL" con botón "🔗 Desde URL"
```

### **4. Verificar Progreso de Importación**
```
1. Ve a /portfolio/import
2. Sube 5 archivos CSV (3 IBKR + 2 DeGiro)
3. Verifica que el primer archivo aparece en "Procesando"
4. Verifica que cuando termina, aparece en "Completados"
5. Verifica que el banner final dice "5 archivo(s) procesados"
```

### **5. Verificar Botones de Enriquecimiento**
```
1. Ve a /portfolio/transactions
2. Haz clic en "Editar" de cualquier transacción
3. Baja a "🌐 Identificadores de Mercado"
4. Haz clic en "🤖 Enriquecer con OpenFIGI"
5. Verifica que aparece un banner verde con los datos
6. Haz clic en "🌐 Desde URL de Yahoo"
7. Pega una URL (ej: https://finance.yahoo.com/quote/AAPL/)
8. Verifica que aparece un banner verde con los datos
```

---

## 🔄 ROLLBACK (Si algo falla)

Si necesitas volver atrás:

```bash
# 1. Conectar a producción
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92

# 2. Ir al directorio
cd ~/www

# 3. Ver commits recientes
git log --oneline -5

# 4. Volver al commit anterior
git reset --hard HEAD~1  # O el hash del commit específico

# 5. Restaurar BD del backup (si es necesario)
cp instance/app.db.backup_YYYYMMDD_HHMMSS instance/app.db

# 6. Reiniciar servicio
sudo systemctl restart followup

# 7. Salir
exit
```

---

## 📊 MIGRACIONES INCLUIDAS

Esta versión incluye las siguientes migraciones nuevas:

1. **`ba500a563900_add_mappingregistry_table_for_editable_.py`**
   - Crea tabla `mapping_registry`
   - Índices: `mapping_type`, `source_key`, `is_active`
   - Constraint único: `mapping_type + source_key`

**Nota**: La migración se aplicará automáticamente con `flask db upgrade`

---

## 📝 ARCHIVOS PRINCIPALES MODIFICADOS

### Backend
- `app/models/mapping_registry.py` (NUEVO)
- `app/models/asset_registry.py` (needs_enrichment simplificado)
- `app/routes/portfolio.py` (fix índices, nuevas rutas mappings)
- `app/services/market_data/mappers/*.py` (mappers dinámicos)
- `app/templates/portfolio/mappings.html` (NUEVO)
- `app/templates/portfolio/asset_registry.html` (botones en modal)
- `app/templates/portfolio/transaction_form.html` (fix botones)

### Migraciones
- `migrations/versions/ba500a563900_*.py` (NUEVO)

### Scripts
- `populate_mappings.py` (NUEVO)

---

## ✅ CRITERIOS DE ÉXITO

El deploy es exitoso si:

- ✅ La aplicación carga correctamente en https://followup.fit/
- ✅ `/portfolio/mappings` es accesible y funcional
- ✅ `/portfolio/asset-registry` muestra columna "Uso" ordenable
- ✅ Importación muestra 5/5 archivos (no 4/5)
- ✅ Botones de enriquecimiento funcionan en transacciones
- ✅ No hay errores en `sudo systemctl status followup`
- ✅ No hay errores en logs del servidor

---

## 🆘 TROUBLESHOOTING

### **Error: "No module named 'app.models.mapping_registry'"**

**Solución**:
```bash
# Asegurarse de que el import está en __init__.py
grep "MappingRegistry" app/models/__init__.py

# Si no está, añadirlo manualmente en producción
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92
cd ~/www
nano app/models/__init__.py
# Añadir: from app.models.mapping_registry import MappingRegistry
sudo systemctl restart followup
```

### **Error: "Table mapping_registry doesn't exist"**

**Solución**:
```bash
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92
cd ~/www
source venv/bin/activate
export FLASK_APP=run.py
flask db upgrade  # Ejecutar de nuevo
python populate_mappings.py  # Poblar datos
sudo systemctl restart followup
```

### **Error: "Mappings vacío"**

**Solución**:
```bash
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92
cd ~/www
source venv/bin/activate
python populate_mappings.py  # Ejecutar el script de población
sudo systemctl restart followup
```

---

## 📞 CONTACTO

Si encuentras problemas durante el deploy:

1. Revisa los logs del servicio:
   ```bash
   sudo journalctl -u followup -f
   ```

2. Revisa el estado de la BD:
   ```bash
   sqlite3 instance/app.db ".tables"
   sqlite3 instance/app.db "SELECT COUNT(*) FROM mapping_registry;"
   ```

3. Si todo falla, ejecuta rollback y documenta el error.

---

**¡Listo para deploy!** 🚀

Ejecuta `bash subidaPRO.sh` cuando estés preparado.

