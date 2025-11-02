# ✅ PASOS DE COMPROBACIÓN - AssetRegistry v3.3.0

**Fecha**: 19 Octubre 2025  
**Sistema**: AssetRegistry - Base de Datos Global Compartida

---

## 🎯 RESUMEN DE IMPLEMENTACIÓN

Has recibido un sistema completamente nuevo que gestiona un registro global compartido de assets. Este sistema:

1. **Evita llamadas repetidas a APIs** - Cache global ISIN → Symbol, Exchange, MIC
2. **Se alimenta automáticamente** - IBKR aporta symbol/exchange, DeGiro aporta ISIN/MIC
3. **Enriquece automáticamente** - Usa OpenFIGI para assets sin symbol
4. **Permite gestión completa** - Interfaz para buscar, editar, eliminar registros

---

## 📋 COMPROBACIONES PASO A PASO

### **FASE 1: Verificación de Base de Datos** (5 min)

#### ✅ **1.1. Verificar que la tabla AssetRegistry existe**

```bash
cd ~/www
source venv/bin/activate
python verify_asset_registry.py
```

**Resultado esperado**:
```
✅ Tabla existe. Registros actuales: 0
✅ Tabla Asset existe. Assets actuales: 0
✅ Servicio inicializado correctamente
✅ CSVImporterV2 disponible
✅ Propiedades funcionando correctamente
```

#### ✅ **1.2. Verificar pruebas del sistema**

```bash
python test_complete_system.py
```

**Resultado esperado**:
```
1️⃣ Registro creado desde IBKR:
   - ISIN: US0378331005
   - Symbol: AAPL
   - Is Enriched: True
   - Source: CSV_IMPORT

2️⃣ Registro creado desde DeGiro:
   - Symbol: None (esperado)
   - Exchange (mapeado): BM
   - Needs Enrichment: True

3️⃣ Registro actualizado:
   - Mismo ID: True
   - Usage Count: 2

✅ TODAS LAS PRUEBAS PASARON
```

---

### **FASE 2: Verificación de Interfaz Web** (15 min)

#### ✅ **2.1. Iniciar servidor**

```bash
cd ~/www
source venv/bin/activate
pkill -f 'flask run'  # Matar servidor anterior
flask run --host=127.0.0.1 --port=5001
```

**URL**: http://127.0.0.1:5001

---

#### ✅ **2.2. Verificar acceso al Registro Global**

**Paso 1**: Ir a http://127.0.0.1:5001/portfolio/transactions

**Paso 2**: Buscar el banner morado que dice:
```
┌─────────────────────────────────────────────────────────┐
│ 🗄️ Registro Global de Assets          [Ver Registro] →  │
│ Gestiona la base de datos compartida...                 │
└─────────────────────────────────────────────────────────┘
```

**Paso 3**: Click en "📊 Ver Registro Global →"

**Resultado esperado**:
- URL cambia a `/portfolio/asset-registry`
- Se muestra la interfaz con 4 cards de estadísticas
- Panel de búsqueda y filtros
- Tabla vacía (aún no hay registros)

---

#### ✅ **2.3. Verificar estadísticas**

**En la página del Registro Global**, verifica las 4 cards:

1. **Total Registros**: Debe mostrar 2 (de la prueba anterior: AAPL + Grifols)
2. **Enriquecidos**: Debe mostrar 1 (AAPL)
3. **Pendientes**: Debe mostrar 1 (Grifols)
4. **Completitud**: Debe mostrar 50.0%

---

#### ✅ **2.4. Verificar búsqueda**

**Paso 1**: En el campo "Buscar", escribe: `AAPL`

**Resultado esperado**:
- La tabla se actualiza y muestra solo el registro de Apple
- Columnas visibles: ISIN, Symbol, Nombre, Moneda, Exchange, MIC, Yahoo, Estado, Uso, Acciones

**Paso 2**: Limpia la búsqueda y activa el filtro "Solo sin enriquecer"

**Resultado esperado**:
- Solo aparece Grifols (ES0113211835)
- Estado: "⚠️ Pendiente"

---

#### ✅ **2.5. Verificar edición**

**Paso 1**: En la fila de Grifols, click en "✏️ Editar"

**Resultado esperado**:
- Se abre un modal con 6 campos
- Los campos están prellenados con los datos actuales

**Paso 2**: Rellenar el campo "Symbol" con: `GRF`

**Paso 3**: Click en "Guardar Cambios"

**Resultado esperado**:
- Modal se cierra
- Flash message: "✅ Registro actualizado: ES0113211835"
- Estado de Grifols cambia a "✓ MANUAL"
- Badge cambia de naranja a verde

---

#### ✅ **2.6. Verificar ordenación**

**Paso 1**: Click en el encabezado "Symbol"

**Resultado esperado**:
- Tabla se reordena alfabéticamente por Symbol
- URL cambia a `?sort_by=symbol&sort_order=asc`
- Aparece ↑ en el encabezado

**Paso 2**: Click nuevamente en "Symbol"

**Resultado esperado**:
- Orden se invierte (desc)
- URL cambia a `?sort_by=symbol&sort_order=desc`
- Aparece ↓ en el encabezado

---

### **FASE 3: Verificación de Importación** (20 min)

#### ✅ **3.1. Limpiar base de datos**

```bash
cd ~/www
source venv/bin/activate
echo 'SI' | python clean_all_portfolio_data.py
```

**Resultado esperado**:
```
✅ Datos eliminados:
   • Transaction: XXXX
   • PortfolioHolding: XX
   • Asset: XXX
   • AssetRegistry: 2  ← Se mantiene el registro global
```

**NOTA**: Los registros de AssetRegistry **NO** se eliminan porque son compartidos globalmente.

---

#### ✅ **3.2. Importar CSVs**

**Paso 1**: Ir a http://127.0.0.1:5001/portfolio/import

**Paso 2**: Subir tus 5 CSVs:
- IBKR.csv
- IBKR1.csv
- IBKR2.csv
- TransaccionesDegiro.csv
- Degiro.csv (Estado de Cuenta)

**Paso 3**: Seleccionar cuenta de broker y click en "Importar"

**Resultado esperado** (se mostrará en flash messages):
```
✅ 5 archivos importados correctamente
📊 XXXX transacciones | XX holdings nuevos | XXX dividendos | XX comisiones | X depósitos
🔍 Enriquecimiento: 180/191 assets obtenidos desde OpenFIGI
⚠️ 11 assets no pudieron enriquecerse (usa filtro "Assets sin enriquecer")
```

**Tiempo de importación**: ~2-5 minutos (dependiendo del enriquecimiento)

---

#### ✅ **3.3. Verificar registro global después de importación**

**Paso 1**: Ir a http://127.0.0.1:5001/portfolio/asset-registry

**Resultado esperado**:
- **Total**: ~191 registros (todos los assets únicos de los CSVs)
- **Enriquecidos**: ~180 (los que OpenFIGI pudo procesar + los de IBKR que ya venían con symbol)
- **Pendientes**: ~11 (los que fallaron)
- **Completitud**: ~94%

**Paso 2**: Activar filtro "Solo sin enriquecer"

**Resultado esperado**:
- Ver solo los ~11 assets que necesitan corrección manual
- Todos con badge naranja "⚠️ Pendiente"

---

#### ✅ **3.4. Verificar holdings**

**Paso 1**: Ir a http://127.0.0.1:5001/portfolio/holdings

**Resultado esperado**:
- **IBKR**: 10 holdings
- **DeGiro**: 19 holdings
- Holdings unificados por asset (si hay mismo asset en ambos brokers, se agrupa)

**Paso 2**: Verificar que NO aparecen:
- ❌ VARTA AG (balance 0)
- ❌ Forex (EUR.GBP, etc.)

---

### **FASE 4: Verificación de Enriquecimiento Manual** (10 min)

#### ✅ **4.1. Desde el Registro Global**

**Paso 1**: En `/portfolio/asset-registry`, filtrar "Solo sin enriquecer"

**Paso 2**: Elegir un asset pendiente y click en "✏️ Editar"

**Paso 3**: Rellenar manualmente:
- Symbol (ej: `ABC`)
- Exchange (ej: `NASDAQ`)
- MIC (ej: `XNAS`)
- Yahoo Suffix (vacío si US, o `.MC`, `.L`, etc.)

**Paso 4**: Guardar

**Resultado esperado**:
- Badge cambia a verde "✓ MANUAL"
- Contador de pendientes disminuye en 1

---

#### ✅ **4.2. Desde Edición de Transacciones**

**Paso 1**: Ir a `/portfolio/transactions`

**Paso 2**: Activar filtro "Assets sin enriquecer 🔧"

**Resultado esperado**:
- Solo aparecen transacciones de assets sin symbol o sin exchange

**Paso 3**: Click en "Editar" en cualquier transacción filtrada

**Paso 4**: Scroll hasta la sección "🌐 Identificadores de Mercado"

**Resultado esperado**:
- Se muestran 2 botones:
  - "🤖 Enriquecer con OpenFIGI"
  - "🌐 Desde URL de Yahoo"

**Paso 5**: Click en "🌐 Desde URL de Yahoo"

**Paso 6**: Pegar una URL (ej: `https://finance.yahoo.com/quote/GRF.MC/`)

**Resultado esperado**:
- Campos `Symbol`, `Yahoo Suffix` se autocompletan
- Mensaje: "✅ Actualizado: GRF.MC"
- AssetRegistry se actualiza automáticamente

---

### **FASE 5: Verificación de Filtros** (5 min)

#### ✅ **5.1. Filtro "Dividendos a revisar"**

**Paso 1**: Ir a `/portfolio/transactions`

**Paso 2**: Activar checkbox "Dividendos a revisar"

**Resultado esperado**:
- Solo aparecen dividendos con `currency != 'EUR'`
- Icono ⚠️ visible junto a cada dividendo

---

#### ✅ **5.2. Filtro "Assets sin enriquecer"**

**Paso 1**: En la misma página, activar checkbox "Assets sin enriquecer 🔧"

**Resultado esperado**:
- Solo aparecen transacciones de assets sin symbol o sin exchange en AssetRegistry
- Sirve para identificar qué necesita corrección

---

### **FASE 6: Verificación de Estadísticas Finales** (5 min)

#### ✅ **6.1. Verificar contador de uso**

**Paso 1**: Ir a `/portfolio/asset-registry`

**Paso 2**: Ordenar por "Uso" (click en encabezado "Uso")

**Resultado esperado**:
- Assets más usados aparecen primero
- `usage_count` refleja cuántas veces se ha importado cada asset

---

#### ✅ **6.2. Verificar enrichment_source**

**Paso 1**: En la tabla, observar la columna "Estado"

**Resultado esperado** (diferentes fuentes):
- ✓ OPENFIGI (enriquecido automáticamente durante importación)
- ✓ CSV_IMPORT (IBKR aportó symbol directamente)
- ✓ MANUAL (editado manualmente)
- ✓ YAHOO_URL (enriquecido con URL de Yahoo)

---

## 📊 MÉTRICAS ESPERADAS

### **Después de importar todos los CSVs**:

```
Assets (locales):         ~191
AssetRegistry (global):   ~191
Holdings:                 ~29 (10 IBKR + 19 DeGiro)
Transactions:             ~1700+
Dividends:                ~100+
Enriquecimiento:          ~95%+ (symbol + MIC obtenidos)
```

### **Consultas a OpenFIGI durante importación**:

```
DeGiro assets:  ~180 consultas (para obtener symbol)
IBKR assets:    ~10 consultas (para obtener MIC)
Total:          ~190 consultas (mostradas en barra de progreso)
Tiempo:         ~2-3 minutos (rate limit de OpenFIGI: ~100/min)
```

**IMPORTANTE**: 
- Primera importación será lenta (todas las consultas a OpenFIGI)
- Segunda importación será instantánea (reutiliza AssetRegistry)
- Assets IBKR con symbol pero sin MIC también se enriquecen ahora

---

## 🚨 PROBLEMAS POTENCIALES Y SOLUCIONES

### **Problema 1: "Port 5001 is in use"**

**Solución**:
```bash
pkill -f 'flask run'
flask run --host=127.0.0.1 --port=5001
```

---

### **Problema 2: "No se ven registros en AssetRegistry"**

**Solución**:
- Ejecutar `python test_complete_system.py` para poblar con datos de prueba
- O importar CSVs para poblar automáticamente

---

### **Problema 3: "Enriquecimiento muy lento"**

**Explicación**:
- OpenFIGI tiene rate limit (~100 requests/minuto)
- Para ~191 assets únicos, tarda ~2-3 minutos
- Es normal y solo ocurre la primera vez

**Optimización futura**:
- Los assets ya enriquecidos se reutilizan (cache)
- Segunda importación será instantánea

---

### **Problema 4: "Assets no se enriquecen"**

**Causas posibles**:
1. OpenFIGI no tiene ese asset en su base de datos
2. ISIN incorrecto en el CSV
3. Rate limit de OpenFIGI alcanzado

**Solución**:
- Usar enriquecimiento manual (botones en edición de transacciones)
- Editar directamente en `/portfolio/asset-registry`

---

## ✅ CHECKLIST FINAL

Marca cada item cuando lo completes:

- [ ] Tabla AssetRegistry creada y funcionando
- [ ] Pruebas de sistema pasadas (test_complete_system.py)
- [ ] Servidor iniciado en puerto 5001
- [ ] Banner de acceso visible en /portfolio/transactions
- [ ] Interfaz de gestión accesible en /portfolio/asset-registry
- [ ] Estadísticas mostrándose correctamente (4 cards)
- [ ] Búsqueda funcionando
- [ ] Filtro "Solo sin enriquecer" funcionando
- [ ] Edición en modal funcionando
- [ ] Ordenación por columnas funcionando
- [ ] Eliminación con confirmación funcionando
- [ ] Importación de CSVs completada
- [ ] AssetRegistry poblado con ~191 registros
- [ ] Enriquecimiento automático ejecutado (~94%)
- [ ] Holdings correctos (10 IBKR + 19 DeGiro)
- [ ] Filtro "Dividendos a revisar" funcionando
- [ ] Filtro "Assets sin enriquecer" funcionando
- [ ] Botones de enriquecimiento manual visibles en edición de transacciones
- [ ] Enriquecimiento con OpenFIGI funcionando
- [ ] Enriquecimiento con Yahoo URL funcionando
- [ ] Contador de uso incrementándose correctamente

---

## 📝 NOTAS FINALES

1. **AssetRegistry es global**: Los registros se comparten entre todos los usuarios. Esto acelera importaciones futuras.

2. **IBKR vs DeGiro**:
   - IBKR aporta `symbol` + `exchange` completos
   - DeGiro aporta `ISIN` + `MIC` (se mapea localmente)

3. **Enriquecimiento**:
   - Automático durante importación (si falta symbol)
   - Manual desde UI (botones en edición o desde /asset-registry)

4. **Próximo paso**: Deploy a producción cuando todo esté verificado.

---

**¡Buena suerte con las pruebas! 🚀**

Si encuentras algún problema, revisa la documentación actualizada en:
- README.md
- TU_PLAN_MAESTRO.md
- SPRINT3_DISEÑO_BD.md
- DESIGN_SYSTEM.md
- WORKFLOW_DEV_A_PRODUCCION.md

