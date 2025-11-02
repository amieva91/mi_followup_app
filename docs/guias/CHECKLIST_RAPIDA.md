# ✅ CHECKLIST RÁPIDA - Verificación v3.3.1

**Versión**: 3.3.1 (Condiciones Unificadas + MIC Enrichment)  
**Fecha**: 19 Octubre 2025

---

## 🚀 PASOS RÁPIDOS (30 minutos)

### **PREPARACIÓN** (2 min)

```bash
cd ~/www
source venv/bin/activate
echo 'SI' | python clean_all_portfolio_data.py
```

- [ ] ✅ BD limpia

---

### **PRUEBA UNITARIA** (1 min)

```bash
python test_mic_enrichment.py
```

**Verificar**:
- [ ] IBKR (AAPL): `Symbol: ✅ | MIC: ❌ | needs_enrichment: True`
- [ ] DeGiro (Grifols): `Symbol: ❌ | MIC: ✅ | needs_enrichment: True`
- [ ] Priorización MIC > exchange funcionando

---

### **INICIAR SERVIDOR** (1 min)

```bash
flask run --host=127.0.0.1 --port=5001
```

- [ ] ✅ Servidor arrancado en http://127.0.0.1:5001

---

### **IMPORTAR CSVs** ⭐ (3-5 min - OBSERVAR BIEN)

**Navegación**: http://127.0.0.1:5001/portfolio/import

**Subir los 5 CSVs**:
- [ ] IBKR.csv
- [ ] IBKR1.csv
- [ ] IBKR2.csv
- [ ] Degiro.csv
- [ ] TransaccionesDegiro.csv

**DURANTE LA IMPORTACIÓN** 🔍:
```
🔍 Apple Inc. (US0378331005): obteniendo MIC...
🔍 Grifols SA (ES0113211835): obteniendo Symbol...
🔍 ANXIAN (HK0105006516): obteniendo Symbol + MIC...

Progreso: X/190
```

**Verificar**:
- [ ] Barra de progreso muestra ~190 consultas
- [ ] Mensajes dicen "obteniendo Symbol" / "obteniendo MIC"
- [ ] **NO distingue explícitamente entre brokers**
- [ ] Tiempo: 2-3 minutos

**Al finalizar**:
```
✅ 5 archivos importados correctamente
📊 1.500 transacciones | 29 holdings | 100 dividendos
🔍 Enriquecimiento con OpenFIGI: 185/190 consultas exitosas
📊 Obtenidos: Symbol (DeGiro) + MIC (IBKR) + Exchange + Yahoo Suffix
⚠️ 5 consultas fallidas
```

- [ ] ✅ Importación exitosa
- [ ] ✅ ~185/190 enriquecidos (~97%)

---

### **VERIFICAR ASSETREGISTRY** ⭐ (5 min)

**Navegación**: http://127.0.0.1:5001/portfolio/asset-registry

**Estadísticas (arriba)**:
- [ ] Total: ~191 assets
- [ ] Enriquecidos: ~185-188 (95-98%)
- [ ] Sin enriquecer: ~3-6

**Filtrar "Solo sin enriquecer"**:
- [ ] Aparecen ~5-10 assets
- [ ] Algunos sin symbol (cualquier broker)
- [ ] Algunos sin MIC (cualquier broker)
- [ ] **NO hay separación IBKR vs DeGiro**

---

### **VERIFICAR CONDICIONES UNIFICADAS** ⭐⭐⭐ (5 min)

**A. Buscar asset IBKR**:

Buscar: `AAPL` o `US0378331005`

**Verificar**:
- [ ] Symbol: `AAPL` ✅
- [ ] MIC: Vacío o `XNAS` (depende de OpenFIGI)
- [ ] Si MIC vacío → Aparece en "Sin enriquecer" ✅
- [ ] **Condición unificada aplicada** (falta MIC → needs enrichment)

**B. Buscar asset DeGiro**:

Buscar: `Grifols` o `ES0113211835`

**Verificar**:
- [ ] Symbol: `GRF` (si OpenFIGI lo obtuvo) ✅
- [ ] MIC: `XMAD` ✅
- [ ] Yahoo Suffix: `.MC` ✅
- [ ] **Condición unificada aplicada**

**C. Verificar priorización MIC > exchange**:

Asset con ambos (MIC + Exchange):

**Verificar**:
- [ ] MIC presente: Yahoo Suffix calculado desde MIC
- [ ] MIC ausente: Yahoo Suffix calculado desde exchange (fallback)

---

### **VERIFICAR HOLDINGS** (2 min)

**Navegación**: http://127.0.0.1:5001/portfolio/holdings

**Verificar**:
- [ ] Holdings unificados: ~25-27 filas (algunos en ambos brokers)
- [ ] Columna "Cuenta": Lista vertical de brokers
  ```
  IBKR
  DeGiro
  ```
- [ ] Formato europeo: `1.234,56`
- [ ] Monedas visibles
- [ ] Nombres largos con saltos de línea

---

### **VERIFICAR TRANSACCIONES** (3 min)

**Navegación**: http://127.0.0.1:5001/portfolio/transactions

**A. Formato**:
- [ ] Números europeos: `1.234,56`
- [ ] Monedas visibles
- [ ] Sin límite de 100 (todas visibles)
- [ ] Assets muestran: Nombre + Info (Stock • AAPL • NASDAQ • USD • ISIN)

**B. Filtros automáticos**:

Seleccionar "Dividendos a revisar":
- [ ] Solo dividendos en moneda ≠ EUR
- [ ] Icono ⚠️ visible

Seleccionar "Assets sin enriquecer":
- [ ] Solo assets sin symbol O sin MIC
- [ ] ~5-10 transacciones
- [ ] **NO distingue entre IBKR y DeGiro**

**C. Ordenación**:
- [ ] Hacer clic en "Fecha" → Ordena
- [ ] Hacer clic en "Activo" → Ordena
- [ ] Todas las columnas ordenables

---

### **VERIFICAR EDICIÓN MANUAL** (2 min)

**Hacer clic en "✏️ Editar" en cualquier transacción**:

**Verificar campos**:
- [ ] Tipo, Fecha, ISIN, Symbol, Cantidad, Precio, etc.
- [ ] **Nueva sección "🌐 Identificadores de Mercado"**:
  - [ ] Exchange (editable)
  - [ ] MIC (editable)
  - [ ] Yahoo Suffix (editable)
- [ ] Botón "🔍 Enriquecer con OpenFIGI"
- [ ] Botón "🔧 Corregir con URL de Yahoo"

---

### **PROBAR CACHE (SEGUNDA IMPORTACIÓN)** ⚡ (2 min)

**Sin limpiar BD, volver a importar los mismos 5 CSVs**:

**Verificar**:
- [ ] Importación muy rápida (< 10 segundos) ⚡⚡⚡
- [ ] **0 consultas a OpenFIGI** (todo desde cache)
- [ ] Mensaje: "0/0 consultas necesarias"
- [ ] Holdings siguen siendo 29
- [ ] Duplicados rechazados

---

### **VERIFICAR SISTEMA DE MAPEOS** 🗺️ (5 min - NUEVO)

**Navegación**: http://127.0.0.1:5001/portfolio/asset-registry → Clic en "🗺️ Gestionar Mapeos"

#### **A. Ver mapeos** (2 min):
- [ ] Se carga `/portfolio/mappings` correctamente
- [ ] Estadísticas arriba: Total 78, MIC→Yahoo 28, Exchange→Yahoo 29, DeGiro→IBKR 21
- [ ] Tabla muestra 78 mapeos
- [ ] Colores diferentes por tipo de mapeo

#### **B. Probar filtros** (1 min):
- [ ] Filtro por tipo: Seleccionar "MIC → Yahoo Suffix" → Solo 28 mapeos
- [ ] Búsqueda: Escribir "XMAD" → Encuentra el mapeo
- [ ] Filtro por país: Seleccionar "ES" → Solo mapeos españoles

#### **C. CRUD básico** (2 min):

**Crear mapeo de prueba**:
1. Clic en "➕ Nuevo Mapeo"
2. Tipo: `EXCHANGE_TO_YAHOO`
3. Clave: `TEST`
4. Valor: `.TEST`
5. Guardar

- [ ] Aparece en la tabla ✅

**Editar**:
1. Clic en "✏️ Editar" del mapeo TEST
2. Cambiar valor a `.TST`
3. Guardar

- [ ] Valor actualizado ✅

**Eliminar**:
1. Clic en "🗑️" del mapeo TEST
2. Confirmar

- [ ] Mapeo eliminado ✅

#### **D. Verificar que mappers leen desde BD** (1 min - CRÍTICO):

```bash
python -c "from app.services.market_data.mappers import YahooSuffixMapper; from app import create_app; app=create_app(); app.app_context().push(); print('XMAD →', YahooSuffixMapper.mic_to_yahoo_suffix('XMAD'))"
```

**Resultado esperado**: `XMAD → .MC`

- [ ] Muestra `.MC` ✅ (lector desde BD)
- [ ] Si muestra otra cosa ❌ (aún lee diccionario hardcodeado)

**Resultado**:
- [ ] ✅ Sistema de mapeos 100% funcional
- [ ] ✅ Sin código hardcodeado (todo en BD editable)

---

### **LIMPIEZA FINAL** (1 min)

```bash
echo 'SI' | python clean_all_portfolio_data.py
```

- [ ] ✅ BD limpia para próximos tests

---

## 🎯 CRITERIOS DE ÉXITO

### ✅ **Condiciones unificadas** (LO MÁS IMPORTANTE):
```python
# Asset sin symbol (cualquier broker) → needs_enrichment = True
# Asset sin MIC (cualquier broker) → needs_enrichment = True
# NO hay diferencias IBKR vs DeGiro
```

### ✅ **Priorización MIC > exchange**:
```python
# Si hay MIC → yahoo_suffix desde MIC
# Si no hay MIC → yahoo_suffix desde exchange (fallback)
```

### ✅ **Enriquecimiento completo**:
```
Primera importación: ~190 consultas (2-3 min)
Segunda importación: 0 consultas (< 10 seg) ⚡
Tasa de éxito: 95-98%
```

### ✅ **Base de datos robusta**:
```
Assets: ~191
Con Symbol: ~191 (IBKR 10 + DeGiro ~181)
Con MIC: ~185 (OpenFIGI N/A para algunos)
Enriquecidos: ~185-188 (95-98%)
```

### ✅ **Sistema de Mapeos (NUEVO)**:
```
Total Mapeos: 78
MIC → Yahoo: 28
Exchange → Yahoo: 29
DeGiro → IBKR: 21
Sin código hardcodeado: ✅
Editable desde web: ✅
```

---

## ⚠️ SEÑALES DE ALERTA

### ❌ **Problema: Condiciones NO unificadas**
```
Asset IBKR con symbol pero sin MIC → needs_enrichment = False
```
**Debería ser**: `True` ❌

### ❌ **Problema: Priorización incorrecta**
```
Asset con MIC: XMAD
Yahoo Suffix: .MC (desde exchange BM, no desde MIC)
```
**Debería**: Calcularse desde MIC ❌

### ❌ **Problema: Cache no funciona**
```
Segunda importación: 190 consultas (igual que primera)
```
**Debería ser**: 0 consultas ❌

---

## 📊 MÉTRICAS FINALES

| Métrica | Valor esperado | Verificado |
|---------|---------------|-----------|
| Assets totales | ~191 | [ ] |
| Enriquecidos | ~185-188 (95-98%) | [ ] |
| Holdings | 29 (10 IBKR + 19 DeGiro) | [ ] |
| Transacciones | ~1.500 | [ ] |
| Dividendos | ~100 | [ ] |
| 1ª importación | 2-3 min (~190 consultas) | [ ] |
| 2ª importación | < 10 seg (0 consultas) | [ ] |

---

## 📚 DOCUMENTACIÓN COMPLETA

**Para más detalles**: `GUIA_VERIFICACION_COMPLETA.md` (18 pasos detallados)

---

**✅ Si todos los checks pasan → Sistema v3.3.1 funcionando correctamente**

