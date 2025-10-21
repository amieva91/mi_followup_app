# 🧪 TEST: Botón Enriquecer en AssetRegistry

## 📋 Pasos de Prueba

### **TEST 1: Enriquecer AAPL (sin MIC)**
1. Ir a: http://127.0.0.1:5001/portfolio/asset-registry
2. Buscar Apple (US0378331005) o filtrar por "⚠️ Pendiente"
3. Hacer clic en "✏️ Editar"
4. Verificar campos actuales:
   - Symbol: AAPL ✅
   - MIC: (vacío) ❌
   - Exchange: NASDAQ ✅
   - Yahoo Suffix: (vacío) ✅ (correcto para US)

5. **Hacer scroll hasta el final del modal**
6. Ver sección azul "🔍 Enriquecimiento Automático"
7. Hacer clic en "🔍 Enriquecer con OpenFIGI"
8. **Esperar 2-3 segundos**

### **Resultado Esperado**:
```
✅ Mensaje: "Asset enriquecido correctamente"
✅ Campos actualizados automáticamente:
   - Symbol: AAPL (sin cambios)
   - MIC: XNAS (NUEVO! ✅)
   - Exchange: NASDAQ (sin cambios)
   - Yahoo Suffix: (vacío, correcto para US)
   - Nombre: Apple Inc. (sin cambios o actualizado)

✅ Estado visual: Verde con checkmark
✅ Mensaje: "Datos actualizados. Haz clic en Guardar Cambios para aplicar."
```

9. **Hacer clic en "Guardar Cambios"**
10. Verificar en la tabla que AAPL ahora muestra:
    - MIC: XNAS ✅
    - Estado: ✅ CSV_IMPORT (cambia a verde)

---

## ✅ **Validaciones**

### **Estados del Botón**:
- **Inicial**: Verde, texto "🔍 Enriquecer con OpenFIGI"
- **Loading**: Gris deshabilitado, texto "⏳ Consultando OpenFIGI..."
- **Éxito**: Verde deshabilitado, texto "✅ Enriquecido"
- **Error**: Verde habilitado, texto "🔍 Reintentar"

### **Mensajes de Status**:
- **Loading**: Azul, "Consultando OpenFIGI API..."
- **Éxito**: Verde, "✅ Asset enriquecido correctamente" → "✅ Datos actualizados. Haz clic en..."
- **Error**: Rojo, "❌ [mensaje de error]"

---

## 🔧 **Si hay Problemas**

### **Error: "Asset sin ISIN"**
- El registro no tiene ISIN, no se puede enriquecer

### **Error: "No results from OpenFIGI"**
- OpenFIGI no encontró el asset con ese ISIN
- Intenta editar manualmente los campos

### **Error: "Rate limit"**
- Espera 1 minuto y reintenta

### **Error 500**
- Ver logs: `tail -f ~/www/flask.log`
- Verificar que el servidor esté corriendo: `ps aux | grep 'python.*app.py'`

---

## 📊 **Comparación con Método Anterior**

| Aspecto | Antes | Ahora |
|---------|-------|-------|
| **Ubicación** | Solo en transacciones | ✅ También en AssetRegistry |
| **Accesibilidad** | 3 clics + scroll | ✅ 2 clics desde tabla |
| **Intuitivo** | ⚠️ No obvio | ✅ Sección dedicada en modal |
| **Feedback** | Básico | ✅ Estados visuales claros |

---

## 🎯 **Ventajas del Nuevo Botón**

✅ **Más directo**: Desde la tabla de AssetRegistry
✅ **Más visible**: Sección dedicada con explicación
✅ **Mismo lugar**: Editas y enriqueces en el mismo modal
✅ **Menos confuso**: No necesitas ir a transacciones

---

## ✅ **COMPLETADO**

- [x] Ruta backend `/asset-registry/<id>/enrich`
- [x] Botón en modal de edición
- [x] JavaScript con estados visuales
- [x] Actualización automática de campos
- [x] Manejo de errores
- [x] Documentación de uso

