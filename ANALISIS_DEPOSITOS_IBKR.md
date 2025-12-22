# Análisis: Depósitos IBKR en Producción vs Desarrollo

## Problema Reportado
En producción, los depósitos de IBKR no se están recogiendo correctamente al subir los mismos CSVs que en desarrollo.

## Análisis en Desarrollo

### Resultados del análisis:
✅ **Parser funciona correctamente**: El parser de IBKR detecta y parsea correctamente los depósitos
✅ **CSV completo encontrado**: El CSV `U12722327_20230912_20240911.csv` contiene 6 depósitos (19,500 EUR total)
✅ **Depósitos en DB coinciden**: Los 6 depósitos del CSV están correctamente importados en la base de datos

### Depósitos encontrados en CSV y DB:
- 2023-09-12: 3,000.00 EUR - ✅ En DB
- 2024-03-15: 5,000.00 EUR - ✅ En DB
- 2024-03-22: 2,000.00 EUR - ✅ En DB
- 2024-04-08: 5,000.00 EUR - ✅ En DB
- 2024-04-18: 2,500.00 EUR - ✅ En DB
- 2024-04-26: 2,000.00 EUR - ✅ En DB

**Total: 19,500.00 EUR**

### Observaciones importantes:

1. **CSVs recientes NO contienen depósitos**: Los CSVs más recientes (desde 2024-09-11 en adelante) solo contienen retiros, no depósitos. Esto es esperado porque IBKR solo muestra movimientos del período del extracto.

2. **CSV completo necesario**: Los depósitos solo aparecen en el CSV que cubre el período desde el primer depósito (2023-09-12 hasta 2024-09-11).

3. **Sección correctamente detectada**: El parser busca y encuentra la sección "Depósitos y retiradas" correctamente.

## Posibles Causas del Problema en Producción

### 1. **CSVs incompletos subidos** (MÁS PROBABLE)
Si en producción solo se subieron CSVs recientes (desde 2024-09-11), estos no contendrán los depósitos históricos. Los depósitos solo aparecen en el CSV que cubre el período completo desde el inicio.

**Solución**: Subir el CSV completo `U12722327_20230912_20240911.csv` (o el equivalente que cubra desde el primer depósito).

### 2. **Detección de duplicados demasiado estricta**
La detección de duplicados usa la clave: `(transaction_type, asset_id, date, amount, 0)`. Si hubo algún problema con el formato de fecha o redondeo de montos, podría estar marcando depósitos como duplicados incorrectamente.

**Verificación necesaria**: Revisar los logs de importación en producción para ver si se están saltando depósitos como "duplicados".

### 3. **Error silencioso durante importación**
Podría haber un error durante la importación que no se está reportando correctamente.

**Verificación necesaria**: Revisar logs de la aplicación en producción durante la importación.

### 4. **Diferencia en versión del código**
Si producción tiene una versión anterior del código, podría tener bugs en el parser o importador.

**Verificación necesaria**: Comparar versiones de código entre dev y prod.

## Scripts de Diagnóstico

Se han creado dos scripts para ayudar con el diagnóstico:

1. **`analizar_depositos_ibkr.py`**: Analiza todos los CSVs de IBKR y compara con la base de datos
2. **`analizar_depositos_ibkr_detallado.py`**: Análisis detallado de un CSV específico

## Recomendaciones

1. **Ejecutar el script de análisis en producción** para ver qué CSVs tiene y qué depósitos están en la DB
2. **Verificar que se haya subido el CSV completo** que contiene los depósitos históricos
3. **Revisar logs de importación** para ver si hay errores o depósitos siendo saltados
4. **Comparar totales de depósitos** entre dev y prod para confirmar la diferencia

