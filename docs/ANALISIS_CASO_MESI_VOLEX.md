# 📋 ANÁLISIS COMPLETO: Caso MESI y Volex

**Fecha**: 2025-01-XX  
**Objetivo**: Analizar el problema con el MIC `MESI` y el activo Volex antes de implementar cambios

---

## 🔍 1. PROBLEMA IDENTIFICADO

### Situación Actual
- **Volex** tiene:
  - `mic = 'MESI'` (obtenido del CSV DeGiro)
  - `exchange = 'EO'` (obtenido de IBKR o mapeo)
  - `country = 'GB'` (obtenido de Yahoo Finance)
  - `yahoo_suffix = '.MC'` (Madrid) ❌ **INCORRECTO**
  - Debería ser: `yahoo_suffix = '.L'` (Londres) ✅

### Comportamiento Actual
1. El sistema prioriza **MIC sobre exchange** (línea 102-107 de `asset_registry_service.py`)
2. Si hay MIC `MESI`, se busca en `MappingRegistry` y encuentra `.MC` (Madrid)
3. El exchange `EO` nunca se evalúa porque el MIC tiene prioridad absoluta
4. **Resultado**: Volex se busca como `VOLE.L` en Yahoo pero el sistema tiene `.MC` configurado

---

## 📊 2. ORIGEN DEL MIC

### ¿De dónde viene el MIC?

#### **A. CSV DeGiro** (Fuente Principal)
- **Archivo**: `app/services/parsers/degiro_transactions_parser.py`
- **Línea 99**: `mic = row[5].strip()` 
- **Columna 5 del CSV**: "Centro de" (MIC ISO 10383)
- **Ejemplo**: En el CSV de DeGiro, Volex tiene `mic = 'MESI'` en la columna 5

#### **B. OpenFIGI API** (Fuente Secundaria)
- **Archivo**: `app/services/market_data/providers/openfigi.py`
- **Línea 70**: `'mic': first_result.get('micCode')`
- **Cuándo se usa**: Cuando se enriquece un asset desde OpenFIGI
- **Prioridad**: Si OpenFIGI devuelve un MIC válido (no 'N/A'), **sobrescribe** el MIC del CSV (línea 198-201 de `asset_registry_service.py`)

### Flujo de Obtención del MIC

```
1. Import CSV DeGiro
   └─> Parser extrae MIC de columna 5
       └─> Se guarda en AssetRegistry.mic

2. (Opcional) Enriquecimiento OpenFIGI
   └─> Si OpenFIGI devuelve micCode válido
       └─> SOBRESCRIBE el MIC del CSV (línea 200)
```

**Conclusión**: El MIC viene **principalmente del CSV DeGiro**, y puede ser sobrescrito por OpenFIGI si este devuelve un valor válido.

---

## 🗂️ 3. VALORES CON MIC = MESI EN LA BASE DE DATOS

### Consulta Realizada
```python
mesis = AssetRegistry.query.filter_by(mic='MESI').all()
```

### Resultados Esperados
- **Total de assets con MIC=MESI**: Necesita ejecutarse en producción/desarrollo
- **Países asociados**: ¿Todos son de España (ES) o hay otros países?
- **Exchanges asociados**: ¿Todos tienen `exchange='EO'` o hay variaciones?

### Información del Código
- **Archivo**: `app/services/market_data/mappers/mic_mapper.py`
- **Línea 52**: `'MESI': 'XMAD'` (MESI se mapea a XMAD como MIC principal)
- **Comentario**: Indica que MESI es un segmento de Madrid

### Mapeo Actual en `yahoo_suffix_mapper.py`
- **Línea 61**: `'MESI': '.MC'` (hardcodeado, pero lee de BD)
- **Descripción**: "SIBE (Madrid electronic)"
- **Sufijo Yahoo**: `.MC` (Madrid)

---

## 🔄 4. ORDEN DE EVALUACIÓN ACTUAL

### Lógica en `_set_yahoo_suffix()` (Líneas 96-114)

```python
def _set_yahoo_suffix(self, registry: AssetRegistry, mic: str = None, exchange: str = None):
    # PRIORIDAD 1: Usar MIC (más confiable)
    if mic:
        suffix = YahooSuffixMapper.mic_to_yahoo_suffix(mic)
        if suffix is not None:
            registry.yahoo_suffix = suffix
            registry.mic = mic
            return  # ← SE DETIENE AQUÍ SI HAY MIC
    
    # PRIORIDAD 2: Usar ibkr_exchange (fallback)
    if not registry.yahoo_suffix and (exchange or registry.ibkr_exchange):
        target_exchange = exchange or registry.ibkr_exchange
        suffix = YahooSuffixMapper.exchange_to_yahoo_suffix(target_exchange)
        if suffix is not None:
            registry.yahoo_suffix = suffix
```

### Comportamiento
1. **Si hay MIC**: Se busca en `MappingRegistry` tipo `MIC_TO_YAHOO`
2. **Si encuentra mapeo**: Se asigna y **se detiene** (return)
3. **Si NO hay MIC o no encuentra mapeo**: Evalúa el exchange
4. **Si hay exchange**: Se busca en `MappingRegistry` tipo `EXCHANGE_TO_YAHOO`

### Problema
- **Volex tiene MIC='MESI'** → Se encuentra mapeo `MESI → .MC` → Se asigna `.MC` y se detiene
- **Nunca se evalúa** `exchange='EO'` que tiene mapeo `EO → .L` (Londres)

---

## 🔧 5. HARDCODEADOS EN EL CÓDIGO

### A. Diccionarios Hardcodeados (Aún Existentes)

#### **1. `yahoo_suffix_mapper.py`**
- **Línea 11-151**: `MIC_TO_YAHOO_SUFFIX = {...}` (diccionario hardcodeado)
- **Línea 236-277**: `EXCHANGE_TO_YAHOO_SUFFIX = {...}` (diccionario hardcodeado)
- **Estado**: Estos diccionarios **NO se usan** en producción (líneas 192-209 y 280-298 leen de BD)
- **Problema**: Son código muerto que puede confundir

#### **2. `mic_mapper.py`**
- **Línea 11-15**: `PRIMARY_MICS = {...}` (set hardcodeado)
- **Línea 18-79**: `MTF_TO_PRIMARY = {...}` (diccionario hardcodeado)
- **Estado**: Se usa para lógica interna de mapeo de MTFs a MICs principales

#### **3. `populate_mappings.py`**
- **Línea 11-130**: `MAPPINGS_DATA = {...}` (diccionario hardcodeado)
- **Estado**: Este es el **script de inicialización** que migra datos a BD
- **Propósito**: Poblar `MappingRegistry` con datos iniciales
- **Nota**: Este archivo es **legítimo** como script de inicialización

### B. Mapeos en Base de Datos

#### **Tabla `mapping_registry`**
- **Tipo**: `MIC_TO_YAHOO`
  - `MESI → .MC` (Madrid)
  - `XMAD → .MC` (Madrid)
  - `XLON → .L` (Londres)
  - ... (más mapeos)

- **Tipo**: `EXCHANGE_TO_YAHOO`
  - `EO → .L` (Londres) ✅ **Este mapeo existe**
  - `BM → .MC` (Madrid)
  - `LSE → .L` (Londres)
  - ... (más mapeos)

### C. Hardcodeados que Deben Eliminarse

1. **`yahoo_suffix_mapper.py`**:
   - Eliminar `MIC_TO_YAHOO_SUFFIX` (líneas 11-151)
   - Eliminar `EXCHANGE_TO_YAHOO_SUFFIX` (líneas 236-277)
   - Mantener solo los métodos que leen de BD

2. **`mic_mapper.py`**:
   - Evaluar si `PRIMARY_MICS` y `MTF_TO_PRIMARY` deben moverse a BD
   - Si se usan solo para lógica interna, pueden quedarse

---

## 📋 6. INFORMACIÓN SOBRE MESI

### Fuente de Información "MESI es el MIC de la Bolsa de Madrid"

#### **A. Código del Sistema**
- **Archivo**: `app/services/market_data/mappers/yahoo_suffix_mapper.py`
- **Línea 61**: `'MESI': '.MC',  # SIBE (Madrid electronic)`
- **Archivo**: `app/services/market_data/mappers/mic_mapper.py`
- **Línea 52**: `'MESI': 'XMAD'` (MESI se relaciona con XMAD)

#### **B. Estándar ISO 10383**
- **MESI** es efectivamente el MIC de **SIBE** (Sistema de Interconexión Bursátil Español)
- **SIBE** es la plataforma electrónica de la **Bolsa de Madrid**
- **Fuente**: ISO 10383 - Market Identifier Codes

#### **C. Problema con Volex**
- **Volex** es una empresa **británica** (GB)
- **Tiene MIC='MESI'** en el CSV DeGiro (posible error del broker o dato histórico)
- **Tiene exchange='EO'** que es correcto para Londres
- **Debería usar**: `.L` (Londres) en lugar de `.MC` (Madrid)

### Valores Adicionales con MIC = MESI

**Necesita consulta en BD**:
```sql
SELECT isin, name, country, ibkr_exchange, yahoo_suffix, symbol
FROM asset_registry
WHERE mic = 'MESI';
```

**Preguntas clave**:
1. ¿Cuántos assets tienen `mic='MESI'`?
2. ¿Todos son de España (`country='ES'`) o hay otros países?
3. ¿Hay assets con `mic='MESI'` y `country='GB'` (como Volex)?

---

## 🎯 7. PLAN DE ACCIÓN PROPUESTO

### Objetivo
Resolver el caso de Volex (y similares) donde el MIC no corresponde al país real del activo, implementando una lógica condicional basada en el país.

### Pasos

#### **Paso 1: Investigación**
1. ✅ Consultar BD para listar todos los assets con `mic='MESI'`
2. ✅ Verificar países asociados (`country` field)
3. ✅ Verificar exchanges asociados (`ibkr_exchange` field)
4. ✅ Identificar casos donde `mic='MESI'` pero `country != 'ES'`

#### **Paso 2: Eliminar Hardcodeados**
1. ✅ Eliminar `MIC_TO_YAHOO_SUFFIX` de `yahoo_suffix_mapper.py`
2. ✅ Eliminar `EXCHANGE_TO_YAHOO_SUFFIX` de `yahoo_suffix_mapper.py`
3. ✅ Verificar que todos los mapeos estén en `populate_mappings.py` y BD

#### **Paso 3: Implementar Lógica Condicional**
1. ✅ Modificar `_set_yahoo_suffix()` para considerar el país
2. ✅ Si `mic='MESI'` y `country='GB'` (o `country='United Kingdom'`):
   - **Priorizar** `exchange` sobre `mic`
   - O crear mapeo específico: `MESI+GB → .L`
3. ✅ Si `mic='MESI'` y `country='ES'`:
   - **Mantener** comportamiento actual: `MESI → .MC`

#### **Paso 4: Actualizar Mapeos en BD**
1. ✅ Si hay múltiples países con `mic='MESI'`:
   - Crear mapeos condicionales en `MappingRegistry`
   - O implementar lógica en código que considere `country`
2. ✅ Si solo hay un caso (Volex):
   - Crear mapeo específico: `EO+GB → .L` (ya existe)
   - O excepción en código: `if mic='MESI' and country='GB': use exchange`

#### **Paso 5: Testing**
1. ✅ Probar con Volex (debe usar `.L`)
2. ✅ Probar con assets españoles con `mic='MESI'` (deben usar `.MC`)
3. ✅ Verificar que no se rompa nada más

---

## 📝 8. RESUMEN DEL PROBLEMA

### Problema Principal
**Volex** tiene un MIC incorrecto (`MESI` = Madrid) pero es un activo británico que debería usar el sufijo `.L` (Londres).

### Causa Raíz
1. El CSV DeGiro proporciona `mic='MESI'` para Volex (posible error del broker)
2. El sistema prioriza MIC sobre exchange
3. El mapeo `MESI → .MC` se aplica sin considerar el país del activo

### Solución Propuesta
Implementar lógica condicional que considere el `country` del activo al determinar el `yahoo_suffix`:
- Si `mic='MESI'` y `country='GB'` → usar `exchange` (EO → .L)
- Si `mic='MESI'` y `country='ES'` → usar `mic` (MESI → .MC)

### Alternativas
1. **Corregir datos en BD**: Cambiar `mic='MESI'` a `mic='XLON'` para Volex (manual)
2. **Mapeo condicional en BD**: Crear tipo `MIC_COUNTRY_TO_YAHOO` (MESI+GB → .L)
3. **Lógica en código**: Excepción en `_set_yahoo_suffix()` para casos específicos

---

## 🔗 9. ARCHIVOS RELACIONADOS

### Archivos a Modificar
1. `app/services/asset_registry_service.py` (líneas 96-114)
2. `app/services/market_data/mappers/yahoo_suffix_mapper.py` (limpiar hardcodeados)
3. `populate_mappings.py` (verificar que todos los mapeos estén)

### Archivos de Consulta
1. `app/services/parsers/degiro_transactions_parser.py` (origen del MIC)
2. `app/services/market_data/providers/openfigi.py` (enriquecimiento MIC)
3. `app/models/mapping_registry.py` (modelo de mapeos)

---

## ✅ 10. CHECKLIST PRE-IMPLEMENTACIÓN

- [ ] Consultar BD para listar todos los `mic='MESI'` con sus países
- [ ] Verificar si hay otros casos similares (MIC incorrecto por país)
- [ ] Documentar todos los hardcodeados encontrados
- [ ] Decidir estrategia: ¿lógica condicional o mapeo en BD?
- [ ] Crear plan de testing
- [ ] Backup de BD antes de cambios

---

**Próximo Paso**: Ejecutar consultas en BD para obtener datos reales y decidir la mejor estrategia de implementación.

