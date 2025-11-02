# 🐛 FIX: AssetRegistry - Tooltip y Filtro Incorrecto

**Fecha:** 2 de noviembre de 2025  
**Versión:** v3.3.5 (complemento)

---

## 📌 PROBLEMAS

### **Problema 1: Tooltip en el lugar incorrecto**
El tooltip explicativo del estado "⚠️ Pendiente" aparecía en cada badge individual en las filas de la tabla, pero debería estar en el **encabezado de la columna "⚠️ Estado"** como información general.

**Ubicación incorrecta:**
```html
<span class="px-2 py-1 bg-orange-100 text-orange-800 rounded text-xs font-medium cursor-help" 
      title="⚠️ Estado: Pendiente...">
    ⚠️ Pendiente
</span>
```

### **Problema 2: Filtro "Solo sin enriquecer" incorrecto**
El checkbox "Solo sin enriquecer" mostraba assets que **SÍ** estaban enriquecidos.

**Ejemplo:** ASTS
- ✅ Symbol: `ASTS`
- ✅ Exchange: `US`
- ✅ Yahoo: `ASTS`
- ✅ Estado: `✓ OPENFIGI` (enriquecido)
- ❌ MIC: `-` (vacío)

ASTS aparecía en el filtro "Solo sin enriquecer" **incorrectamente** porque el filtro era:

```python
query = query.filter(
    db.or_(
        AssetRegistry.symbol.is_(None),  # ❌ ASTS tiene symbol
        AssetRegistry.mic.is_(None)       # ✅ ASTS no tiene MIC → MATCH
    )
)
```

Esto filtraba por `symbol IS NULL OR mic IS NULL`, cuando debería filtrar solo por `is_enriched == False`.

---

## ✅ SOLUCIÓN

### **Fix 1: Tooltip movido al encabezado de columna**

**Archivo**: `app/templates/portfolio/asset_registry.html`

**Cambio en el `<th>` (líneas 113-122):**
```html
<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
    <a href="?sort_by=is_enriched&sort_order={% if sort_by == 'is_enriched' and sort_order == 'asc' %}desc{% else %}asc{% endif %}" 
       class="hover:text-gray-700 flex items-center gap-1">
        <span>⚠️ Estado</span>
        <span class="cursor-help" title="⚠️ Estado del Asset&#10;&#10;✓ Enriquecido: Tiene Symbol (ticker del activo)&#10;⚠️ Pendiente: Le falta el Symbol&#10;&#10;Nota: El MIC es opcional pero mejora la precisión.&#10;&#10;Puedes enriquecer un asset editándolo y haciendo clic en '🔍 Enriquecer con OpenFIGI'.">ℹ️</span>
        {% if sort_by == 'is_enriched' %}
            {% if sort_order == 'asc' %}↑{% else %}↓{% endif %}
        {% endif %}
    </a>
</th>
```

**Cambio en el badge (líneas 196-198):**
```html
<!-- ANTES: Con tooltip en cada fila -->
<span class="px-2 py-1 bg-orange-100 text-orange-800 rounded text-xs font-medium cursor-help" 
      title="⚠️ Estado: Pendiente...">
    ⚠️ Pendiente
</span>

<!-- DESPUÉS: Sin tooltip individual -->
<span class="px-2 py-1 bg-orange-100 text-orange-800 rounded text-xs font-medium">
    ⚠️ Pendiente
</span>
```

### **Fix 2: Filtro corregido**

**Archivo**: `app/routes/portfolio.py` (líneas 491-494)

**Antes:**
```python
# Filtro: Solo sin enriquecer (condiciones unificadas: sin symbol O sin MIC)
unenriched_only = request.args.get('unenriched_only', '').strip()
if unenriched_only:
    query = query.filter(
        db.or_(
            AssetRegistry.symbol.is_(None),
            AssetRegistry.mic.is_(None)
        )
    )
```

**Después:**
```python
# Filtro: Solo sin enriquecer (is_enriched == False, es decir, sin symbol)
unenriched_only = request.args.get('unenriched_only', '').strip()
if unenriched_only:
    query = query.filter(AssetRegistry.is_enriched == False)
```

**Explicación:**
- La columna `is_enriched` de la BD ya refleja si el asset está enriquecido (`symbol` presente)
- El MIC es **opcional** y no debe afectar el estado de enriquecimiento
- Usar `is_enriched == False` es más simple, más rápido, y consistente con la lógica del modelo

---

## 🧪 VERIFICACIÓN

### **Antes del fix:**
```
Solo sin enriquecer ✓

ASTS    AST SPACEMOBILE INC    USD    US    -    ASTS    ✓ OPENFIGI    6    ❌ NO DEBERÍA APARECER
```

### **Después del fix:**
```
Solo sin enriquecer ✓

[Solo assets sin symbol, como los 19 pendientes reales]

ASTS ya NO aparece en la lista ✅
```

### **Tooltip:**
- **Antes**: Aparecía al pasar el mouse sobre cada badge "⚠️ Pendiente" individual
- **Después**: Aparece al pasar el mouse sobre el ℹ️ en el encabezado "⚠️ Estado"

---

## 📦 ARCHIVOS MODIFICADOS

1. `app/templates/portfolio/asset_registry.html`:
   - Líneas 113-122: Tooltip agregado al header "⚠️ Estado"
   - Líneas 196-198: Tooltip eliminado del badge "⚠️ Pendiente"

2. `app/routes/portfolio.py`:
   - Líneas 491-494: Filtro corregido para usar `is_enriched == False`

---

## 🎯 IMPACTO

- ✅ **UX mejorada**: El tooltip ahora está en el lugar correcto (encabezado de columna)
- ✅ **Filtro preciso**: Solo muestra assets que realmente necesitan enriquecimiento (sin symbol)
- ✅ **Consistencia**: El filtro ahora coincide con la lógica del modelo `AssetRegistry`
- ✅ **Performance**: Filtro más eficiente (un solo check de columna booleana indexada)

---

## 🔄 DEPLOY

Este fix es **complementario** a v3.3.5 y debe desplegarse junto con el fix de DeGiro.

**Versión:** v3.3.5  
**Tag Git:** `v3.3.5-fix-degiro-dates`

