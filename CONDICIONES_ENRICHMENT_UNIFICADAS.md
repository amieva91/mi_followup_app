# 🔄 CONDICIONES DE ENRICHMENT (UNIFICADAS)

**Actualizado**: 19 Octubre 2025 - Noche

---

## **Importante: Criterios iguales para IBKR y DeGiro**

La lógica de `needs_enrichment` es **idéntica** para ambos brokers:

```python
@property
def needs_enrichment(self):
    """
    Condiciones unificadas para TODOS los assets (sin distinguir broker):
    - Falta symbol → needs_enrichment = True
    - Falta MIC → needs_enrichment = True
    """
    return not self.symbol or not self.mic
```

---

## **Ejemplos prácticos**:

| Asset | Symbol | MIC | needs_enrichment | Acción OpenFIGI |
|-------|--------|-----|------------------|-----------------|
| IBKR - AAPL | ✅ AAPL | ❌ None | ✅ True | Obtener MIC |
| DeGiro - Grifols | ❌ None | ✅ XMAD | ✅ True | Obtener Symbol |
| DeGiro - ANXIAN | ❌ None | ❌ None | ✅ True | Obtener Symbol + MIC |
| IBKR completo | ✅ MSFT | ✅ XNAS | ❌ False | Sin acción |

---

## **NO hay condiciones diferentes**:

### ❌ Incorrecto (antes):
- "DeGiro necesita symbol pero no MIC"
- "IBKR necesita MIC pero no symbol"
- Condiciones diferentes según broker

### ✅ Correcto (ahora):
- **TODOS los assets necesitan AMBOS campos** (symbol + MIC)
- **NO distingue** entre IBKR y DeGiro
- Solo verifica: ¿falta symbol? ¿falta MIC? → Enrichment needed

---

## **Implementación en el código**:

### **1. Modelo `AssetRegistry` (app/models/asset_registry.py)**:

```python
@property
def needs_enrichment(self):
    """
    Indica si necesita ser enriquecido con OpenFIGI
    
    Condiciones unificadas para TODOS los assets (sin distinguir broker):
    - Falta symbol → needs_enrichment = True
    - Falta MIC → needs_enrichment = True
    """
    return not self.symbol or not self.mic
```

### **2. Servicio `CSVImporterV2` (app/services/importer_v2.py)**:

```python
def _registry_needs_enrichment(self, isin: str) -> bool:
    """
    Verifica si un registro necesita enriquecimiento
    
    Aplica a TODOS los assets (IBKR y DeGiro por igual):
    - Sin symbol → Consultar OpenFIGI para obtener symbol
    - Sin MIC → Consultar OpenFIGI para obtener MIC
    
    No distingue origen del asset (broker), solo verifica campos faltantes
    """
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

---

## **Resultado esperado**:

### **Para DeGiro** (~180 assets):
```
Asset sin symbol:        180/180 → Consultar OpenFIGI (symbol + MIC)
Asset sin MIC:           180/180 → Consultar OpenFIGI (symbol + MIC)
Total consultas:         ~180
```

### **Para IBKR** (~10 assets):
```
Asset con symbol:        10/10
Asset sin MIC:           10/10 → Consultar OpenFIGI (MIC)
Total consultas:         ~10
```

### **Total general**:
```
Consultas OpenFIGI:      ~190
Tiempo estimado:         2-3 minutos (rate limit ~100/min)
Completitud esperada:    95%+ (symbol + MIC obtenidos)
```

---

## **Beneficios de la unificación**:

1. ✅ **Consistencia**: Misma lógica para todos los assets
2. ✅ **Simplicidad**: Sin condiciones especiales por broker
3. ✅ **Completitud**: Base de datos más robusta (symbol + MIC para todos)
4. ✅ **Mantenibilidad**: Código más fácil de entender y mantener
5. ✅ **Escalabilidad**: Preparado para futuros brokers sin cambios

---

## **Verificación manual**:

### **Paso 1: Limpiar BD**
```bash
echo 'SI' | python clean_all_portfolio_data.py
```

### **Paso 2: Importar CSVs**
- Subir 5 CSVs (3 IBKR + 2 DeGiro)
- Observar barra de progreso: ~190 consultas

### **Paso 3: Verificar AssetRegistry**
- Ir a `/portfolio/asset-registry`
- Filtrar "Solo sin enriquecer"
- Deberían quedar ~5-10 assets (los que OpenFIGI no pudo enriquecer)

### **Paso 4: Verificar holdings**
- Todos los assets deberían tener symbol Y MIC (cuando fue exitoso)
- Yahoo suffix calculado con prioridad MIC > exchange

---

**✅ Condiciones unificadas implementadas y documentadas**

