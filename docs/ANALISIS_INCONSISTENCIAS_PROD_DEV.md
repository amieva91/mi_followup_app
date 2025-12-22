# 🔍 ANÁLISIS: Inconsistencias entre Producción y Desarrollo

**Fecha**: 2025-01-XX  
**Objetivo**: Investigar por qué hay diferencias entre producción y desarrollo sin hacer cambios

---

## 📊 PROBLEMAS IDENTIFICADOS

### 1. **Diferencia en Enriquecimiento (33 vs 34)**
- **Dev**: 33/59 assets enriquecidos con OpenFIGI
- **Prod**: 34/59 assets enriquecidos con OpenFIGI
- **Diferencia**: 1 asset más enriquecido en producción

### 2. **Volex Falla en Escaneo de Precios**
- Volex no se actualiza correctamente en el escaneo de precios
- Símbolo diferente: `VLXGBP` (dev) vs `VLX` (prod)

### 3. **Inconsistencia en Precios: ANDEAN PRECIOUS METALS**
- **Dev**: Precio 9,91 CAD → Ganancia +1.319,14 EUR
- **Prod**: Precio 1,30 CAD → Pérdida -1.871,60 EUR
- **Diferencia**: Precio 7.6x mayor en desarrollo

---

## 🔍 ANÁLISIS DETALLADO

### **1. Diferencia en Enriquecimiento (33 vs 34)**

#### **Causa Raíz:**
La lógica de enriquecimiento depende de:
```python
def _registry_needs_enrichment(self, isin: str) -> bool:
    registry = AssetRegistry.query.filter_by(isin=isin).first()
    if not registry:
        return False
    
    # Falta symbol (puede ser DeGiro o IBKR sin symbol)
    if not registry.symbol:
        return True
    
    # Falta MIC (puede ser IBKR o DeGiro sin MIC)
    if not registry.mic:
        return True
    
    return False
```

#### **Posibles Causas:**
1. **Estado diferente de AssetRegistry entre entornos**:
   - Un asset puede tener `symbol` en prod pero no en dev (o viceversa)
   - Un asset puede tener `mic` en prod pero no en dev (o viceversa)
   - Esto puede deberse a:
     - Enriquecimientos manuales previos en un entorno
     - Importaciones anteriores con diferentes configuraciones
     - Datos residuales de pruebas

2. **Orden de procesamiento diferente**:
   - Si hay múltiples assets con el mismo ISIN, el orden puede afectar qué se enriquece primero
   - Si un asset se enriquece manualmente antes de la importación, puede afectar el conteo

3. **Errores silenciosos en OpenFIGI**:
   - Si OpenFIGI falla para un asset en un entorno pero no en otro
   - Si hay rate limiting diferente entre entornos

#### **Cómo Verificar:**
```sql
-- En ambos entornos, ejecutar:
SELECT isin, symbol, mic, is_enriched, enrichment_source
FROM asset_registry
WHERE symbol IS NULL OR mic IS NULL
ORDER BY isin;
```

---

### **2. Volex Falla en Escaneo de Precios**

#### **Causa Raíz:**
El ticker de Yahoo se construye así:
```python
@property
def yahoo_ticker(self):
    """Construye el ticker completo para Yahoo Finance"""
    if not self.symbol:
        return None
    suffix = self.yahoo_suffix or ''
    return f"{self.symbol}{suffix}"
```

#### **Problema Identificado:**
1. **Símbolo diferente entre entornos**:
   - **Dev**: `symbol='VLXGBP'` → `yahoo_ticker='VLXGBP.L'` (si `yahoo_suffix='.L'`)
   - **Prod**: `symbol='VLX'` → `yahoo_ticker='VLX.L'` (si `yahoo_suffix='.L'`)

2. **Yahoo Suffix puede estar incorrecto**:
   - Si Volex tiene `mic='MESI'` y el mapeo MESI todavía existe en BD → `yahoo_suffix='.MC'`
   - Entonces:
     - Dev: `VLXGBP.MC` → ❌ No existe en Yahoo
     - Prod: `VLX.MC` → ❌ No existe en Yahoo

3. **Después de corregir símbolo en dev**:
   - Si cambias `symbol='VLXGBP'` a `symbol='VLX'` en dev
   - Y si `yahoo_suffix='.L'` (después de eliminar MESI)
   - Entonces: `VLX.L` → ✅ Existe en Yahoo

#### **Verificación Necesaria:**
```sql
-- En ambos entornos, verificar Volex:
SELECT isin, symbol, mic, yahoo_suffix, ibkr_exchange, country
FROM asset_registry
WHERE isin = 'GB0009390070' OR name LIKE '%VOLEX%';

-- Y en Asset local:
SELECT id, symbol, mic, yahoo_suffix, exchange, country
FROM assets
WHERE isin = 'GB0009390070';
```

#### **Causa del Símbolo Diferente:**
- **Origen del símbolo**:
  - Puede venir del CSV (IBKR trae symbol)
  - Puede venir de OpenFIGI durante el enriquecimiento
  - Puede ser editado manualmente

- **Por qué puede ser diferente**:
  1. **CSV diferente**: Si los CSVs tienen símbolos diferentes
  2. **OpenFIGI devuelve diferente**: OpenFIGI puede devolver `VLX` o `VLXGBP` según el contexto
  3. **Edición manual**: Si alguien editó manualmente en un entorno

---

### **3. Inconsistencia en Precios: ANDEAN PRECIOUS METALS**

#### **Causa Raíz:**
El precio se obtiene de Yahoo Finance usando:
```python
yahoo_ticker = f"{symbol}{yahoo_suffix}"
# Ejemplo: APM.TOR (si symbol='APM' y yahoo_suffix='.TOR')
```

#### **Problema Identificado:**
1. **Precio diferente (9.91 CAD vs 1.30 CAD)**:
   - Esto indica que se está consultando **diferentes tickers** en Yahoo Finance
   - O que Yahoo Finance tiene datos inconsistentes

2. **Posibles Causas**:
   - **Símbolo diferente**: `APM` vs `APM.TOR` vs otro símbolo
   - **Yahoo Suffix diferente**: `.TOR` vs `.TO` vs sin sufijo
   - **Ticker incorrecto**: Si el ticker está mal construido, Yahoo puede devolver un precio de otro asset

3. **Verificación del Ticker**:
   ```python
   # Dev: ¿Qué ticker se está usando?
   # Prod: ¿Qué ticker se está usando?
   # ¿Son iguales?
   ```

#### **Cómo Verificar:**
```sql
-- En ambos entornos:
SELECT isin, symbol, yahoo_suffix, 
       CONCAT(symbol, COALESCE(yahoo_suffix, '')) as yahoo_ticker,
       current_price, currency, last_price_update
FROM assets
WHERE isin = 'CA03349X1015' OR name LIKE '%ANDEAN%';
```

#### **Posibles Escenarios:**
1. **Ticker mal construido**:
   - Dev: `APM.TOR` (correcto para Toronto)
   - Prod: `APM` (sin sufijo, puede devolver precio de otro mercado)

2. **Símbolo diferente**:
   - Dev: `symbol='APM'`
   - Prod: `symbol='APM.TOR'` (símbolo ya incluye sufijo)

3. **Yahoo Suffix diferente**:
   - Dev: `yahoo_suffix='.TOR'`
   - Prod: `yahoo_suffix=''` o `.TO`

4. **Datos históricos en cache**:
   - Si hay precios en cache de actualizaciones anteriores
   - Los precios pueden no actualizarse si hay errores silenciosos

---

## 🔧 VERIFICACIONES NECESARIAS

### **1. Verificar Estado de AssetRegistry**
```sql
-- Comparar AssetRegistry entre entornos
SELECT isin, symbol, mic, yahoo_suffix, ibkr_exchange, country, 
       is_enriched, enrichment_source
FROM asset_registry
ORDER BY isin;
```

### **2. Verificar Estado de Assets Locales**
```sql
-- Comparar Assets entre entornos
SELECT isin, symbol, mic, yahoo_suffix, exchange, country,
       current_price, currency, last_price_update
FROM assets
ORDER BY isin;
```

### **3. Verificar Mapeos en MappingRegistry**
```sql
-- Verificar que MESI no esté mapeado
SELECT * FROM mapping_registry 
WHERE mapping_type = 'MIC_TO_YAHOO' AND source_key = 'MESI';

-- Verificar que EO esté mapeado
SELECT * FROM mapping_registry 
WHERE mapping_type = 'EXCHANGE_TO_YAHOO' AND source_key = 'EO';
```

### **4. Verificar Tickers de Yahoo**
```python
# Para cada asset problemático, verificar:
asset.yahoo_ticker  # ¿Qué ticker se construye?
# Luego verificar en Yahoo Finance si ese ticker existe
```

---

## 🎯 CONCLUSIONES

### **Problema 1: Enriquecimiento (33 vs 34)**
- **Causa probable**: Estado diferente de `AssetRegistry` entre entornos
- **Solución**: Sincronizar `AssetRegistry` entre dev y prod, o verificar qué asset tiene estado diferente

### **Problema 2: Volex**
- **Causa probable**: 
  1. Símbolo diferente (`VLXGBP` vs `VLX`)
  2. Yahoo suffix incorrecto (`.MC` en lugar de `.L`)
- **Solución**: 
  1. Verificar y corregir símbolo en ambos entornos
  2. Verificar que `yahoo_suffix='.L'` (no `.MC`)
  3. Asegurar que MESI no esté mapeado en BD

### **Problema 3: ANDEAN PRECIOUS METALS**
- **Causa probable**: Ticker de Yahoo construido diferente entre entornos
- **Solución**: 
  1. Verificar `symbol` y `yahoo_suffix` en ambos entornos
  2. Asegurar que el ticker construido sea el mismo
  3. Verificar que Yahoo Finance tenga el mismo precio para ese ticker

---

## 📝 PRÓXIMOS PASOS (SIN HACER CAMBIOS AÚN)

1. ✅ Ejecutar consultas SQL en ambos entornos para comparar datos
2. ✅ Verificar logs de importación para ver qué assets se enriquecieron
3. ✅ Verificar logs de actualización de precios para ver qué tickers se consultaron
4. ✅ Comparar CSVs importados para ver si hay diferencias en los datos fuente
5. ✅ Verificar si hay ediciones manuales en un entorno que no están en el otro

---

**Estado**: Análisis completo, esperando verificación de datos antes de implementar soluciones

