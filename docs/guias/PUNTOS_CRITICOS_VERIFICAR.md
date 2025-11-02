# 🎯 3 PUNTOS CRÍTICOS A VERIFICAR

**Versión**: 3.3.1  
**Lo más importante en 5 minutos**

---

## ⭐⭐⭐ PUNTO 1: CONDICIONES UNIFICADAS

### **Qué verificar**:

Ir a: http://127.0.0.1:5001/portfolio/asset-registry

**Activar filtro "Solo sin enriquecer"**

**Buscar assets específicos**:

#### Asset IBKR (ejemplo: AAPL):
```
Symbol: AAPL ✅
MIC:    (vacío) ❌
```
**¿Aparece en "Sin enriquecer"?**
- ✅ SÍ → Condiciones unificadas funcionan
- ❌ NO → Condiciones NO unificadas (ERROR)

#### Asset DeGiro (ejemplo: Grifols):
```
Symbol: (vacío o GRF si OpenFIGI lo obtuvo)
MIC:    XMAD ✅
```
**¿Aparece en "Sin enriquecer" si falta symbol?**
- ✅ SÍ → Condiciones unificadas funcionan
- ❌ NO → Condiciones NO unificadas (ERROR)

### **Resultado esperado**:
```
✅ IBKR sin MIC → needs_enrichment = True
✅ DeGiro sin symbol → needs_enrichment = True
✅ NO hay excepciones por broker
```

---

## ⭐⭐ PUNTO 2: PRIORIZACIÓN MIC > EXCHANGE

### **Qué verificar**:

En AssetRegistry, buscar: `Grifols` o `ES0113211835`

**Verificar**:
```
MIC:           XMAD ✅
IBKR Exchange: BM
Yahoo Suffix:  .MC
```

**¿De dónde viene `.MC`?**
- ✅ De MIC (`XMAD` → `.MC`) → CORRECTO
- ❌ De exchange (`BM` → `.MC`) → Ambiguo (podría ser correcto por casualidad)

### **Prueba definitiva**:

Buscar un asset US (ejemplo: AAPL o MSFT):
```
MIC:           XNAS
IBKR Exchange: NASDAQ
Yahoo Suffix:  '' (vacío)
```

**Si MIC está presente**:
- ✅ Yahoo Suffix vacío (US) → Calculado desde MIC
- ❌ Yahoo Suffix tiene valor → ERROR

### **Resultado esperado**:
```
✅ Si hay MIC → Yahoo Suffix desde MIC
✅ Si no hay MIC → Yahoo Suffix desde exchange (fallback)
```

---

## ⭐ PUNTO 3: BARRA DE PROGRESO Y CONSULTAS

### **Qué verificar**:

**Durante la importación de CSVs**:

```
🔍 Apple Inc. (US0378331005): obteniendo MIC...
🔍 Grifols SA (ES0113211835): obteniendo Symbol...
🔍 ANXIAN (HK0105006516): obteniendo Symbol + MIC...

Progreso: 50/190
Progreso: 100/190
Progreso: 190/190
```

**Verificar**:
- ✅ Mensajes dicen exactamente QUÉ se está obteniendo (Symbol, MIC, ambos)
- ✅ Total de consultas: ~190
- ✅ **NO distingue "DeGiro" o "IBKR" en los mensajes**
- ✅ Tiempo: 2-3 minutos

**Al finalizar**:
```
✅ 5 archivos importados correctamente
🔍 Enriquecimiento con OpenFIGI: 185/190 consultas exitosas
📊 Obtenidos: Symbol (DeGiro) + MIC (IBKR) + Exchange + Yahoo Suffix
```

### **Resultado esperado**:
```
✅ ~190 consultas (DeGiro ~180 + IBKR ~10)
✅ Tasa de éxito: 95-98%
✅ Mensajes claros y unificados
```

---

## 🔄 BONUS: SEGUNDA IMPORTACIÓN (CACHE)

### **Qué verificar**:

**Sin limpiar BD, volver a importar los mismos 5 CSVs**:

```
🔍 Procesando archivos...
📊 Enriquecimiento con OpenFIGI: 0/0 consultas necesarias

✅ 5 archivos importados correctamente
```

**Verificar**:
- ✅ Importación en < 10 segundos ⚡
- ✅ **0 consultas a OpenFIGI**
- ✅ Mensaje: "0/0 consultas necesarias"

### **Resultado esperado**:
```
✅ Cache funcionando perfectamente
✅ AssetRegistry reutilizado al 100%
```

---

## ✅ RESUMEN: 3 CHECKS RÁPIDOS

### **1. Condiciones unificadas** (2 min):
```bash
# Ir a AssetRegistry → Filtrar "Solo sin enriquecer"
# Verificar que aparecen assets de AMBOS brokers
# Razón: falta symbol O falta MIC (sin excepciones)
```
**¿Funciona?** → [ ] SÍ / [ ] NO

---

### **2. Priorización MIC > exchange** (1 min):
```bash
# Buscar "Grifols" en AssetRegistry
# Verificar que Yahoo Suffix = .MC (desde MIC: XMAD)
```
**¿Funciona?** → [ ] SÍ / [ ] NO

---

### **3. Barra de progreso + consultas** (3 min):
```bash
# Importar CSVs
# Observar: ~190 consultas, mensajes "obteniendo Symbol/MIC"
# Resultado: 185/190 exitoso (~97%)
```
**¿Funciona?** → [ ] SÍ / [ ] NO

---

## ⭐ PUNTO 4: SISTEMA DE MAPEOS EDITABLES (NUEVO)

### **Qué verificar**:

Ir a: http://127.0.0.1:5001/portfolio/asset-registry

**Hacer clic en "🗺️ Gestionar Mapeos"**

### **Verificar que carga la página de mappings**:

```
URL: http://127.0.0.1:5001/portfolio/mappings
```

**Verificar estadísticas**:
```
Total Mapeos:        78
MIC → Yahoo:         28
Exchange → Yahoo:    29
DeGiro → IBKR:       21
Activos:            78
```

**¿Aparecen 78 mapeos en la tabla?**
- ✅ SÍ → Sistema de mappings funcionando
- ❌ NO → Verificar que se ejecutó `populate_mappings.py`

### **Probar crear un mapeo de prueba**:

1. Clic en "➕ Nuevo Mapeo"
2. Completar:
   - Tipo: `EXCHANGE_TO_YAHOO`
   - Clave: `TEST`
   - Valor: `.TEST`
3. Guardar

**¿Aparece en la tabla?**
- ✅ SÍ → CRUD funcionando
- ❌ NO → Error en rutas

4. **Eliminar el mapeo de prueba** (botón 🗑️)

### **Verificar que mappers leen desde BD**:

```bash
cd ~/www
source venv/bin/activate
python -c "from app.services.market_data.mappers import YahooSuffixMapper; from app import create_app; app=create_app(); app.app_context().push(); print('XMAD →', YahooSuffixMapper.mic_to_yahoo_suffix('XMAD'))"
```

**Resultado esperado**:
```
XMAD → .MC
```

**¿Funciona?** → [ ] SÍ / [ ] NO

### **Resultado esperado**:
```
✅ 78 mapeos visibles en interfaz web
✅ Crear, editar, eliminar funciona
✅ Mappers leen desde BD (no hardcodeado)
✅ Sin código hardcodeado
```

---

## 🎯 SI LOS 4 PASAN → SISTEMA COMPLETO ✅

---

**Para más detalles**:
- `CHECKLIST_RAPIDA.md` (30 min, completo)
- `GUIA_VERIFICACION_COMPLETA.md` (1 hora, exhaustivo)
- `SISTEMA_MAPPINGS_COMPLETADO.md` (guía de mappings)

