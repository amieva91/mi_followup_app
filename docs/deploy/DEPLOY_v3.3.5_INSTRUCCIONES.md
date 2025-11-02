# 🚀 DEPLOY v3.3.5 - Instrucciones Manuales

**Fecha:** 2 de noviembre de 2025  
**Versión:** v3.3.5 (Fix Crítico: DeGiro Dividendos/Fees)

---

## 📋 CAMBIOS EN ESTA VERSIÓN

### **Fix Crítico: DeGiro Dividendos/Fees sin Fecha**
- ✅ **407 transacciones** ahora se importan correctamente (antes: 0)
  - 158 dividendos ✅
  - 169 fees (comisiones) ✅
  - 9 depósitos ✅
  - 71 retiros ✅
- ✅ Soporte para `datetime.date` en `parse_datetime()`
- ✅ Fallback de seguridad en DeGiro parser

### **Mejoras Adicionales**
- ✅ Tooltip AssetRegistry movido al encabezado "⚠️ Estado"
- ✅ Filtro "Solo sin enriquecer" corregido (`is_enriched == False`)
- ✅ Documentación organizada (29 archivos movidos a `docs/`)

### **Archivos Modificados**
1. `app/services/importer_v2.py` - Fix `parse_datetime()` para `datetime.date`
2. `app/services/parsers/degiro_parser.py` - Fallback para fechas
3. `app/templates/portfolio/asset_registry.html` - Tooltip en header
4. `app/routes/portfolio.py` - Filtro `is_enriched`
5. `app/templates/base/layout.html` - Fix dropdown bug
6. `app/templates/portfolio/import_csv.html` - Fix botón "Importar CSV"
7. Documentación actualizada: `README.md`, `TU_PLAN_MAESTRO.md`, `WORKFLOW_DEV_A_PRODUCCION.md`, `SPRINT3_DISEÑO_BD.md`

---

## 🔧 INSTRUCCIONES DE DEPLOY

### **Opción A: Deploy con Git (Recomendado)**

Si tienes acceso SSH al servidor de producción:

```bash
# 1. Conectar al servidor
ssh ubuntu@followup.fit

# 2. Navegar al directorio del proyecto
cd ~/www

# 3. Pull de los últimos cambios
git pull origin main

# 4. Activar entorno virtual
source venv/bin/activate

# 5. Reiniciar el servicio
sudo systemctl restart followup

# 6. Verificar que el servicio está corriendo
sudo systemctl status followup

# 7. Verificar logs
sudo journalctl -u followup -f
```

### **Opción B: Deploy Manual (Sin Git)**

Si no tienes acceso Git configurado en producción:

```bash
# 1. Desde tu máquina local, crear un archivo tar.gz con los cambios
cd ~/www
tar -czf deploy_v3.3.5.tar.gz \
    app/services/importer_v2.py \
    app/services/parsers/degiro_parser.py \
    app/templates/portfolio/asset_registry.html \
    app/templates/base/layout.html \
    app/templates/portfolio/import_csv.html \
    app/routes/portfolio.py \
    README.md \
    TU_PLAN_MAESTRO.md \
    WORKFLOW_DEV_A_PRODUCCION.md \
    SPRINT3_DISEÑO_BD.md \
    docs/

# 2. Subir al servidor
scp deploy_v3.3.5.tar.gz ubuntu@followup.fit:~/

# 3. Conectar al servidor
ssh ubuntu@followup.fit

# 4. Extraer los archivos
cd ~/www
tar -xzf ~/deploy_v3.3.5.tar.gz

# 5. Reiniciar el servicio
sudo systemctl restart followup

# 6. Verificar
sudo systemctl status followup
```

### **Opción C: Deploy con Script (Automático)**

Si existe el script `subidaPRO.sh`:

```bash
# Desde tu máquina local WSL
cd ~/www
./subidaPRO.sh
```

---

## ✅ VERIFICACIÓN POST-DEPLOY

Una vez desplegado, verifica que todo funciona correctamente:

### **1. Servicio Activo**
```bash
sudo systemctl status followup
```

Debe mostrar: `Active: active (running)`

### **2. Página Principal**
```bash
curl -I https://followup.fit/
```

Debe devolver: `HTTP/1.1 200 OK`

### **3. Importación DeGiro**
1. Ve a https://followup.fit/portfolio/import
2. Sube el archivo `Degiro.csv`
3. Verifica que se importan:
   - 158 dividendos
   - 169 fees
   - 9 depósitos
   - 71 retiros

### **4. AssetRegistry**
1. Ve a https://followup.fit/portfolio/asset-registry?unenriched_only=1
2. Verifica que **NO** aparece ASTS (que SÍ está enriquecido)
3. Pasa el mouse sobre el ℹ️ en el header "⚠️ Estado"
4. Debe aparecer el tooltip explicativo

### **5. Logs**
```bash
sudo journalctl -u followup -n 100
```

No debe haber errores recientes.

---

## 🐛 TROUBLESHOOTING

### **Error: "ImportError: No module named 'app'"**
```bash
cd ~/www
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart followup
```

### **Error: "Permission denied"**
```bash
sudo chown -R ubuntu:ubuntu ~/www
sudo chmod -R 755 ~/www
```

### **Error: "Port 5000 already in use"**
```bash
sudo systemctl stop followup
sudo systemctl start followup
```

### **Servicio no arranca**
```bash
# Ver logs detallados
sudo journalctl -u followup -xe

# Verificar archivo de servicio
sudo cat /etc/systemd/system/followup.service

# Recargar systemd
sudo systemctl daemon-reload
sudo systemctl restart followup
```

---

## 📊 COMMITS INCLUIDOS

```bash
0b9680a - fix: v3.3.5 - DeGiro dividends/fees date parsing + AssetRegistry tooltip/filter fixes
da62104 - docs: organize documentation - keep only 5 main files in root
```

---

## 📝 DOCUMENTACIÓN RELACIONADA

- **Fix Principal**: `docs/fixes/FIX_DEGIRO_DIVIDENDOS_SIN_FECHA.md`
- **Fix Adicional**: `docs/fixes/FIX_ASSETREGISTRY_TOOLTIP_Y_FILTRO.md`
- **Arquitectura BD**: `SPRINT3_DISEÑO_BD.md`
- **Workflow**: `WORKFLOW_DEV_A_PRODUCCION.md`

---

## 🎯 PRÓXIMOS PASOS

Una vez completado el deploy:
1. ✅ Verificar que todos los endpoints funcionan
2. ✅ Probar la importación de CSVs (IBKR + DeGiro)
3. ✅ Verificar dividendos, fees, depósitos y retiros
4. ✅ Verificar AssetRegistry y filtros
5. ✅ Actualizar el tag en Git: `git tag v3.3.5 && git push origin v3.3.5`

---

**Última actualización:** 2 Noviembre 2025 - 20:45 UTC  
**Estado:** ✅ LISTO PARA DEPLOY

