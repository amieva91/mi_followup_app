# ✅ **PLAN DE PRUEBAS - MARKET DATA**

**Fecha:** 2025-10-17  
**Objetivo:** Verificar que la importación, enriquecimiento y corrección manual funcionan correctamente

---

## 📋 **CHECKLIST DE PRUEBAS**

### **🔹 FASE 1: Importación Rápida (CRÍTICO)**

#### **1.1 Limpiar datos previos (opcional)**
```bash
# Solo si quieres empezar desde cero
flask shell
>>> from app.models import Asset, PortfolioHolding, Transaction
>>> Asset.query.delete()
>>> PortfolioHolding.query.delete()
>>> Transaction.query.delete()
>>> from app import db
>>> db.session.commit()
>>> exit()
```

#### **1.2 Importar CSV**
1. **Ve a:** http://127.0.0.1:5001/portfolio/import
2. **Sube:** `uploads/TransaccionesDegiro.csv`
3. **Selecciona:** Tu cuenta de DeGiro
4. **Clic:** "Importar"

**✅ Resultado esperado:**
- ⏱️ Importación completada en **1-3 segundos** (no más de 5)
- ✅ Flash verde: "Importación completada"
- ✅ Estadísticas mostradas (X trades, Y assets, Z holdings)

**❌ Si falla:**
- Error de rate limit → Normal si ya enriqueciste antes
- Timeout → Revisar `enable_enrichment=False` en importer

#### **1.3 Verificar assets creados**
```bash
flask shell
```

```python
from app.models import Asset

# Contar assets
total_assets = Asset.query.count()
print(f"✅ Total assets: {total_assets}")
# Esperado: 180-200 assets

# Ver un asset español (Grifols Madrid)
grifols = Asset.query.filter_by(isin='ES0171996087').first()
if grifols:
    print(f"\n📊 Asset: {grifols.name}")
    print(f"   Symbol: {grifols.symbol or '❌ NULL (esperado)'}")
    print(f"   ISIN: {grifols.isin}")
    print(f"   MIC: {grifols.mic}")  # Esperado: XMAD
    print(f"   Yahoo Suffix: {grifols.yahoo_suffix}")  # Esperado: .MC
    print(f"   Exchange: {grifols.exchange}")  # Esperado: BM
    print(f"   Yahoo Ticker: {grifols.yahoo_ticker or '❌ Requiere symbol'}")
else:
    print("⚠️  Grifols no encontrado")

# Ver un asset US
assets_us = Asset.query.filter_by(currency='USD').first()
if assets_us:
    print(f"\n📊 Asset US: {assets_us.name}")
    print(f"   Symbol: {assets_us.symbol or '❌ NULL (esperado)'}")
    print(f"   MIC: {assets_us.mic}")  # Esperado: XNAS, XNYS, etc.
    print(f"   Yahoo Suffix: {assets_us.yahoo_suffix}")  # Esperado: '' (vacío)
    print(f"   Exchange: {assets_us.exchange}")

# Ver assets sin symbol (esperado para todos sin enriquecimiento)
sin_symbol = Asset.query.filter(Asset.symbol.is_(None)).count()
print(f"\n📊 Assets sin symbol: {sin_symbol}/{total_assets}")
# Esperado: Todos si no has enriquecido

# Ver assets con MIC
con_mic = Asset.query.filter(Asset.mic.isnot(None)).count()
print(f"📊 Assets con MIC: {con_mic}/{total_assets}")
# Esperado: Todos o casi todos

# Ver assets con yahoo_suffix
con_suffix = Asset.query.filter(Asset.yahoo_suffix.isnot(None)).count()
print(f"📊 Assets con Yahoo Suffix: {con_suffix}/{total_assets}")
# Esperado: Todos o casi todos

exit()
```

**✅ Checklist Fase 1:**
- [ ] Importación completada en < 5 segundos
- [ ] Assets creados (180-200)
- [ ] `mic` poblado para la mayoría
- [ ] `yahoo_suffix` poblado para la mayoría
- [ ] `symbol` = NULL para todos (esperado)
- [ ] `exchange` poblado para la mayoría

---

### **🔹 FASE 2: Verificar Holdings y Transacciones**

#### **2.1 Ver holdings**
1. **Ve a:** http://127.0.0.1:5001/portfolio/holdings

**✅ Verificar:**
- [ ] Se muestran 19 holdings (o el número esperado)
- [ ] Nombres de assets visibles
- [ ] Icono 🔧 aparece junto a assets (porque `symbol` es NULL)
- [ ] Cantidades y costes se muestran correctamente
- [ ] Información de la segunda línea: `Stock • [Exchange] • EUR • ISIN`

#### **2.2 Ver transacciones**
1. **Ve a:** http://127.0.0.1:5001/portfolio/transactions

**✅ Verificar:**
- [ ] Se muestran todas las transacciones
- [ ] Tipos: BUY, SELL, DIVIDEND, FEE, DEPOSIT, WITHDRAWAL
- [ ] Formato europeo de números (1.234,56)
- [ ] Divisas correctas
- [ ] Filtros funcionan

---

### **🔹 FASE 3: Enriquecimiento con OpenFIGI (OPCIONAL)**

**⚠️ IMPORTANTE:** Este paso tarda ~30 segundos y consulta OpenFIGI.

```bash
cd ~/www
source venv/bin/activate
python app/services/enrich_existing_assets.py
```

**Durante la ejecución:**
```
📊 Assets encontrados que necesitan enriquecimiento: 185
⏱️  Tiempo estimado: ~28 segundos

¿Continuar con el enriquecimiento? (s/N): s  # ← Escribe 's' y Enter
```

**✅ Observar:**
- [ ] Contador [1/185], [2/185], etc.
- [ ] Para cada asset:
  - `🔍 Enriqueciendo [nombre]... (ISIN: xxx, MIC: xxx)`
  - `✅ Obtenido: [SYMBOL] → [SUFFIX]` (si exitoso)
  - `⚠️ Sin ticker desde OpenFIGI` (si falla)

**✅ Resultado esperado:**
```
RESUMEN
======================================================================

✅ Enriquecidos exitosamente: 170-180
⚠️  Sin cambios (sin datos):   5-15
❌ Fallidos:                    0-5

Total procesados: 185
```

#### **3.1 Verificar enriquecimiento**
```bash
flask shell
```

```python
from app.models import Asset

# Ver Grifols ahora (debería tener symbol)
grifols = Asset.query.filter_by(isin='ES0171996087').first()
if grifols:
    print(f"📊 Grifols ENRIQUECIDO:")
    print(f"   Symbol: {grifols.symbol}")  # Esperado: GRF o similar
    print(f"   Yahoo Ticker: {grifols.yahoo_ticker}")  # Esperado: GRF.MC
    print(f"   MIC: {grifols.mic}")  # XMAD
    print(f"   Yahoo Suffix: {grifols.yahoo_suffix}")  # .MC

# Contar cuántos tienen symbol ahora
con_symbol = Asset.query.filter(Asset.symbol.isnot(None)).count()
total = Asset.query.count()
print(f"\n📊 Assets con symbol: {con_symbol}/{total}")
# Esperado: 170-180/185 (90-95%)

exit()
```

**✅ Checklist Fase 3:**
- [ ] Script ejecutado sin errores
- [ ] 170-180 assets enriquecidos (90-95%)
- [ ] `symbol` poblado para la mayoría
- [ ] `yahoo_ticker` disponible para assets enriquecidos
- [ ] 5-15 assets sin enriquecer (normal para assets exóticos)

---

### **🔹 FASE 4: Corrección Manual con Modal 🔧**

**Para assets que no se enriquecieron con OpenFIGI:**

#### **4.1 Identificar asset sin ticker**
1. **Ve a:** http://127.0.0.1:5001/portfolio/holdings
2. **Busca:** Asset con icono 🔧 (sin symbol)

#### **4.2 Buscar en Yahoo Finance**
1. **Abre:** https://finance.yahoo.com/
2. **Busca:** El nombre del asset (ej: "Grifols Madrid")
3. **Copia:** La URL completa (ej: `https://finance.yahoo.com/quote/GRF.MC/`)

#### **4.3 Aplicar corrección**
1. **Clic:** En 🔧 junto al asset
2. **Modal:** Se abre
3. **Pega:** La URL de Yahoo
4. **Clic:** "Aplicar"

**✅ Resultado esperado:**
- ✅ Alert: "Asset actualizado: Symbol: GRF, Yahoo Ticker: GRF.MC"
- ✅ Página se recarga
- ✅ Icono 🔧 desaparece (ya tiene ticker)
- ✅ Symbol visible en la segunda línea

#### **4.4 Verificar en BD**
```bash
flask shell
```

```python
from app.models import Asset

# Ver el asset corregido
asset = Asset.query.filter_by(name='[NOMBRE DEL ASSET]').first()
print(f"Symbol: {asset.symbol}")
print(f"Yahoo Suffix: {asset.yahoo_suffix}")
print(f"Yahoo Ticker: {asset.yahoo_ticker}")

exit()
```

**✅ Checklist Fase 4:**
- [ ] Modal se abre al hacer clic en 🔧
- [ ] URL parseada correctamente
- [ ] `symbol` y `yahoo_suffix` actualizados
- [ ] Página recarga automáticamente
- [ ] Icono 🔧 desaparece

---

### **🔹 FASE 5: Edición de Transacciones**

#### **5.1 Editar transacción**
1. **Ve a:** http://127.0.0.1:5001/portfolio/transactions
2. **Busca:** Una transacción (ej: primera compra)
3. **Clic:** "Editar"

**✅ Verificar formulario:**
- [ ] Datos prellenados correctamente
- [ ] Sección "🌐 Identificadores de Mercado" visible con 3 campos:
  - Exchange (ej: BM, NASDAQ)
  - MIC (ej: XMAD, XNAS)
  - Yahoo Suffix (ej: .MC, .L)
- [ ] Campos editables

#### **5.2 Modificar y guardar**
1. **Cambia:** Yahoo Suffix (ej: de `.MC` a `.MA`)
2. **Clic:** "Registrar Transacción"

**✅ Resultado esperado:**
- ✅ Flash verde: "Transacción actualizada correctamente"
- ✅ Holdings recalculados automáticamente
- ✅ Cambio persistido en BD

#### **5.3 Verificar cambio**
```bash
flask shell
```

```python
from app.models import Asset

# Ver el asset editado
asset = Asset.query.filter_by(name='[NOMBRE]').first()
print(f"Yahoo Suffix: {asset.yahoo_suffix}")  # Debería ser .MA

exit()
```

**✅ Checklist Fase 5:**
- [ ] Formulario muestra campos de market identifiers
- [ ] Campos prellenados correctamente
- [ ] Cambios se guardan
- [ ] Holdings se recalculan
- [ ] Sin errores en consola

---

### **🔹 FASE 6: Actualización de Precios**

**⚠️ SOLO funciona para assets con `symbol` (enriquecidos o corregidos)**

```bash
cd ~/www
source venv/bin/activate
python app/services/update_prices.py
```

**✅ Observar:**
```
🔄 Actualizando precios para X assets con holdings activos...

   ✓ Grifols SA (GRF.MC): 12.45 EUR
   ✓ Apple Inc. (AAPL): 178.23 USD
   ⊘ ASSET_SIN_TICKER: Sin yahoo_ticker (symbol: None, suffix: .MC)
   ✗ ASSET_FALLIDO (TICKER.XX): No se pudo obtener precio

✅ Actualización completada:
   ✓ Actualizados: 15
   ✗ Fallidos: 2
   ⊘ Omitidos: 2
```

#### **6.1 Verificar precios actualizados**
```bash
flask shell
```

```python
from app.models import Asset
from datetime import datetime, timedelta

# Ver assets con precio
con_precio = Asset.query.filter(Asset.last_price.isnot(None)).all()
print(f"📊 Assets con precio: {len(con_precio)}")

for asset in con_precio[:5]:  # Ver los primeros 5
    print(f"\n{asset.name}:")
    print(f"   Precio: {asset.last_price} {asset.currency}")
    print(f"   Actualizado: {asset.last_price_update}")
    
    # Verificar que la actualización es reciente (< 5 min)
    if asset.last_price_update:
        minutes_ago = (datetime.utcnow() - asset.last_price_update).seconds / 60
        print(f"   ⏱️  Hace {minutes_ago:.1f} minutos")

exit()
```

**✅ Checklist Fase 6:**
- [ ] Script ejecutado sin errores
- [ ] 15-18 precios actualizados (solo holdings > 0 con symbol)
- [ ] `last_price` poblado
- [ ] `last_price_update` es reciente (< 5 min)
- [ ] Assets sin symbol fueron omitidos (esperado)

---

### **🔹 FASE 7: Dashboard Final**

#### **7.1 Ver dashboard**
1. **Ve a:** http://127.0.0.1:5001/portfolio/

**✅ Verificar:**
- [ ] Holdings unificados mostrados
- [ ] Nombres correctos
- [ ] Información completa en segunda línea
- [ ] Icono 🔧 solo en assets sin symbol
- [ ] Cantidades y costes correctos
- [ ] Si hay precios: Valor actual visible

---

## 🐛 **PROBLEMAS COMUNES Y SOLUCIONES**

### **1. ImportError al ejecutar scripts**
```
ModuleNotFoundError: No module named 'app'
```

**Solución:**
```bash
cd ~/www
source venv/bin/activate
python app/services/[script].py  # Usar esta ruta
```

### **2. Importación tarda mucho (> 10 seg)**
**Causa:** `enable_enrichment=True` activado por error

**Solución:**
```python
# Verificar en app/services/importer.py línea 18
def __init__(self, user_id: int, broker_account_id: int, enable_enrichment: bool = False):
#                                                                                  ^^^^^^^^
# Debe ser False
```

### **3. Modal 🔧 no aparece**
**Causa:** Asset ya tiene `symbol`

**Solución:** Normal, el icono solo aparece si `symbol` es NULL

### **4. Yahoo URL no parsea**
**Formatos válidos:**
- ✅ `https://finance.yahoo.com/quote/GRF.MC/`
- ✅ `https://es.finance.yahoo.com/quote/AAPL`
- ❌ `GRF.MC` (falta URL completa)

### **5. PriceUpdater omite todos los assets**
**Causa:** Ningún asset tiene `symbol`

**Solución:** Ejecutar primero `enrich_existing_assets.py` o corregir manualmente con modal

---

## ✅ **RESUMEN DE COMANDOS ÚTILES**

```bash
# Activar entorno
cd ~/www
source venv/bin/activate

# Limpiar BD (opcional)
flask shell
>>> Asset.query.delete(); db.session.commit(); exit()

# Enriquecer assets
python app/services/enrich_existing_assets.py

# Actualizar precios
python app/services/update_prices.py

# Flask shell para verificaciones
flask shell
>>> from app.models import Asset
>>> Asset.query.count()
>>> exit()
```

---

## 📊 **RESULTADOS ESPERADOS FINALES**

Después de completar todas las fases:

| Métrica | Valor Esperado |
|---------|----------------|
| **Assets importados** | 180-200 |
| **Assets con MIC** | 180-200 (99%) |
| **Assets con yahoo_suffix** | 180-200 (99%) |
| **Assets con symbol** | 170-190 (90-95%) |
| **Assets con precio** | 15-20 (solo holdings > 0) |
| **Holdings detectados** | 19 (tu portfolio real) |
| **Transacciones importadas** | 400-600 (depende del CSV) |

---

**🎯 ¡LISTO PARA PROBAR!**

Empieza por la **FASE 1** y avísame cuando completes cada fase o si encuentras algún problema.

