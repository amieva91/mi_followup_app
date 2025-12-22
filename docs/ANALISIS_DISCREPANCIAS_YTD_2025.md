# 🔍 ANÁLISIS: Discrepancias en Rentabilidad YTD 2025

**Fecha**: 2025-12-12  
**Problema**: Diferencia de 1,365.54 EUR en ganancia YTD 2025 entre DEV y PROD

---

## 📊 COMPARACIÓN DE RESULTADOS

### Desarrollo:
- **VI (Valor Inicial)**: 64,995.11 EUR
- **VF (Valor Final)**: 73,770.98 EUR
- **Return %**: 20.77%
- **Ganancia/Pérdida**: **13,143.67 EUR**
- **Cash Flows Neto**: -4,367.79 EUR

### Producción:
- **VI (Valor Inicial)**: 66,498.08 EUR ⚠️ **+1,502.97 EUR**
- **VF (Valor Final)**: 73,908.42 EUR ⚠️ **+137.44 EUR**
- **Return %**: 18.18% ⚠️ **-2.59%**
- **Ganancia/Pérdida**: **11,778.13 EUR** ⚠️ **-1,365.54 EUR**
- **Cash Flows Neto**: -4,367.79 EUR ✅ **IGUAL**

---

## 🔍 DIFERENCIAS IDENTIFICADAS

### 1. **Valor Inicial (VI) - Diferencia: 1,502.97 EUR**

#### Asset GRF (277 unidades):
- **DEV**: 277.0 x **10.79** = 2,988.83 EUR
- **PROD**: 277.0 x **11.075** = 3,067.77 EUR
- **Diferencia**: +78.94 EUR

#### Otros assets:
- Hay diferencias en precios históricos al 1 enero 2025
- La suma total de diferencias: **1,502.97 EUR**

### 2. **Valor Final (VF) - Diferencia: 137.44 EUR**

#### Asset diferente con mismo ISIN:
- **DEV**: `APR` (654 unidades) x 16.48 = 10,777.92 EUR
  - Ticker: `APR.WA`
  - Precio: 16.48
  
- **PROD**: `0RI1` (654 unidades) x 16.8585 = 11,025.46 EUR
  - Ticker: `0RI1.L`
  - Precio: 16.8585
  - **Diferencia**: +247.54 EUR

#### Asset GRF (277 unidades):
- **DEV**: 277.0 x **10.79** = 2,988.83 EUR
- **PROD**: 277.0 x **11.075** = 3,067.77 EUR
- **Diferencia**: +78.94 EUR

**Nota**: La diferencia neta en VF es menor porque hay compensaciones entre assets.

---

## 🚨 PROBLEMA CRÍTICO IDENTIFICADO

### **Asset con mismo ISIN pero símbolo/ticker diferente**

**ISIN**: Probablemente el mismo (654 unidades en ambos)

**DEV**:
- Symbol: `APR`
- Yahoo Ticker: `APR.WA`
- Precio: 16.48

**PROD**:
- Symbol: `0RI1`
- Yahoo Ticker: `0RI1.L`
- Precio: 16.8585

### **Causa Raíz Probable**:

1. **Símbolo diferente en AssetRegistry**:
   - El mismo ISIN tiene diferentes símbolos en DEV vs PROD
   - Esto puede deberse a:
     - Enriquecimiento diferente (OpenFIGI devolvió símbolos distintos)
     - Edición manual diferente
     - Importación desde diferentes fuentes

2. **Yahoo Ticker diferente**:
   - `APR.WA` (Warsaw) vs `0RI1.L` (London)
   - Esto sugiere que el asset está listado en diferentes exchanges
   - O que el enriquecimiento identificó diferentes exchanges

3. **Precio diferente**:
   - 16.48 vs 16.8585
   - Puede ser el mismo asset en diferentes exchanges con precios ligeramente diferentes
   - O puede ser un asset completamente diferente si el ISIN es diferente

---

## 🔍 VERIFICACIONES NECESARIAS

### 1. Verificar ISIN del asset APR/0RI1:
```sql
-- En DEV
SELECT isin, symbol, yahoo_ticker, current_price 
FROM assets 
WHERE symbol = 'APR' OR symbol LIKE '0RI1%';

-- En PROD
SELECT isin, symbol, yahoo_ticker, current_price 
FROM assets 
WHERE symbol = 'APR' OR symbol LIKE '0RI1%';
```

### 2. Verificar AssetRegistry:
```sql
-- Buscar por ISIN o símbolo
SELECT isin, symbol, yahoo_ticker, yahoo_suffix, ibkr_exchange, mic
FROM asset_registry
WHERE symbol = 'APR' OR symbol LIKE '0RI1%';
```

### 3. Verificar precios históricos de GRF:
- ¿Por qué el precio histórico al 1 enero 2025 es diferente?
- ¿Hay diferencias en PriceHistory entre entornos?

---

## 💡 SOLUCIÓN PROPUESTA

### 1. **Sincronizar símbolos y tickers**:
   - Identificar el ISIN correcto del asset APR/0RI1
   - Verificar cuál es el símbolo/ticker correcto
   - Sincronizar ambos entornos

### 2. **Verificar precios históricos**:
   - Comparar PriceHistory de GRF entre entornos
   - Asegurar que los precios históricos al 1 enero 2025 sean iguales

### 3. **Verificar enriquecimiento**:
   - Asegurar que OpenFIGI devuelva los mismos datos en ambos entornos
   - O sincronizar manualmente los datos de AssetRegistry

---

## 📝 IMPACTO

- **Diferencia en ganancia YTD**: 1,365.54 EUR
- **Diferencia en return %**: 2.59%
- **Causa principal**: Asset diferente (APR vs 0RI1) y precios históricos diferentes

---

## 🚀 PRÓXIMOS PASOS

1. ✅ Identificar el ISIN del asset APR/0RI1
2. ✅ Verificar cuál es el símbolo/ticker correcto
3. ✅ Sincronizar ambos entornos
4. ✅ Verificar precios históricos de GRF
5. ✅ Re-calcular rentabilidades después de la sincronización

---

**Estado**: Problema identificado - Asset diferente y precios históricos diferentes

