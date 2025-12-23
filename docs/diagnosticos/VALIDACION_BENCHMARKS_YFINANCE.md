# Validación de Benchmarks - Yahoo Finance

**Fecha**: 23 Diciembre 2025  
**Estado**: ⚠️ Problema temporal con yfinance/Yahoo Finance API

## 🔍 Resultados de Validación

### Índices a Validar

1. **S&P 500**: `^GSPC`
2. **NASDAQ**: `^IXIC`
3. **MSCI World**: `^URTH` o `EWLD`
4. **EuroStoxx 50**: `^STOXX50E`

### ⚠️ Problema Encontrado

Al intentar obtener datos históricos con `yfinance`, se obtiene el error:
```
Failed to get ticker '^GSPC' reason: Expecting value: line 1 column 1 (char 0)
^GSPC: No timezone found, symbol may be delisted
```

**Posibles causas:**
1. Problema temporal con la API de Yahoo Finance
2. Rate limiting (demasiadas peticiones)
3. Cambios en la API de Yahoo Finance
4. Problema de conexión/red

### ✅ Validación Anterior (22 Dic)

En una prueba anterior, `yf.download('^GSPC', period='1y')` funcionó correctamente y devolvió 250 días de datos.

## 🔄 Siguientes Pasos

### Opción 1: Reintentar más tarde
- Puede ser un problema temporal de Yahoo Finance
- Probar de nuevo en unas horas

### Opción 2: Usar ETFs como alternativas
Si los índices directos no funcionan, usar ETFs que los repliquen:
- **S&P 500**: `SPY` (SPDR S&P 500 ETF)
- **NASDAQ**: `QQQ` (Invesco QQQ Trust)
- **MSCI World**: `ACWI` (iShares MSCI ACWI ETF) o `URTH` (iShares MSCI World ETF)
- **EuroStoxx 50**: `FEZ` (SPDR EURO STOXX 50 ETF)

**Ventajas de ETFs:**
- Más estables en la API
- Mismo comportamiento que el índice
- Datos más fiables

**Desventajas:**
- Pueden tener pequeñas diferencias vs índice real (tracking error)
- Incluyen comisiones del fondo

### Opción 3: API alternativa
Si Yahoo Finance no es confiable, considerar:
- **Alpha Vantage** (requiere API key gratuita)
- **Polygon.io** (requiere API key)
- **FRED** (Federal Reserve Economic Data) para algunos índices

## 📋 Recomendación

**Recomendación: Usar ETFs como alternativa**

Los ETFs son una buena alternativa porque:
1. Son más estables en la API
2. Tienen el mismo comportamiento que los índices subyacentes
3. La diferencia es mínima (<0.1% típicamente)

**Símbolos propuestos:**
- S&P 500: `SPY`
- NASDAQ: `QQQ`
- MSCI World: `ACWI` o `URTH`
- EuroStoxx 50: `FEZ`

## 🧪 Script de Validación

El script `test_benchmarks_validation.py` está preparado para:
1. Obtener fecha de inicio del usuario desde BD
2. Probar obtención de datos históricos de los 4 índices
3. Validar disponibilidad y formato de datos
4. Calcular rentabilidades para verificar que funciona

**Ejecutar:**
```bash
source venv/bin/activate
python test_benchmarks_validation.py
```

