# 🔧 FIX: UI de Progreso + Banner de Resultados

**Fecha**: 21 de octubre de 2025
**Versión**: v3.3.1 - Fix 2

---

## ❌ **PROBLEMAS IDENTIFICADOS Y RESUELTOS**

### **Problema 1: Datos de archivos no se muestran**

**Síntoma**:
```
📁 Procesando: -
✅ Completados: Ninguno
⏳ En cola: -
```

**Causa raíz**:
- El backend SÍ estaba calculando `current_file`, `pending_files`, `completed_files`
- Pero el endpoint `/import/progress` **NO los devolvía** en el JSON
- El JavaScript solo recibía: `current`, `total`, `message`, `percentage`

**Solución**:
- Actualizado el endpoint `/import/progress` para incluir los campos de archivos
- Añadido debugging en `updateFileInfo()` para verificar datos recibidos

---

### **Problema 2: Banner de resultados no se muestra**

**Síntoma**:
- La importación termina correctamente
- El backend hace redirect a `/portfolio/import?success=1&...`
- Pero el banner de éxito NO se muestra

**Causa raíz**:
- El JavaScript hacía `window.location.href = '{{ url_for("portfolio.import_csv") }}'`
- Esto ignora el redirect del servidor y va directamente a `/portfolio/import` **sin query params**
- Por eso el banner nunca se muestra

**Solución**:
- Cambiar a `window.location.href = response.url`
- Esto sigue la URL final después del redirect, **incluyendo los query params**
- Ahora el JavaScript va a `/portfolio/import?success=1&...` y el banner se muestra

---

### **Problema 3: Pendientes incluyen archivo actual**

**Síntoma**:
- Durante el procesamiento del primer archivo, "En cola" muestra 2 archivos
- Debería mostrar solo 1 (el segundo archivo)

**Causa raíz**:
- El cálculo de `pending_files` estaba incorrecto

**Solución**:
- Corregido el cálculo para que solo incluya archivos **después** del actual
- Ahora usa `range(file_index, len(files))` correctamente

---

## 📝 **ARCHIVOS MODIFICADOS**

### **1. Backend: `app/routes/portfolio.py`**

#### **Línea 964-976**: Endpoint `/import/progress` actualizado

**ANTES**:
```python
return jsonify({
    'status': 'processing',
    'current': progress.get('current', 0),
    'total': progress.get('total', 0),
    'message': progress.get('message', ''),
    'percentage': progress.get('percentage', 0)
})
```

**AHORA**:
```python
return jsonify({
    'status': 'processing',
    'current': progress.get('current', 0),
    'total': progress.get('total', 0),
    'message': progress.get('message', ''),
    'percentage': progress.get('percentage', 0),
    # Info de archivos ← NUEVO
    'current_file': progress.get('current_file'),
    'file_number': progress.get('file_number'),
    'total_files': progress.get('total_files'),
    'completed_files': progress.get('completed_files', []),
    'pending_files': progress.get('pending_files', [])
})
```

---

#### **Línea 1050-1066**: Callback de progreso con debugging

**ANTES**:
```python
def progress_callback(current, total, message):
    with progress_lock:
        import_progress_cache[user_key] = {
            'current': current,
            'total': total,
            'message': message,
            'percentage': int((current / total) * 100) if total > 0 else 0,
            'current_file': filename,
            'file_number': file_index,
            'total_files': total_files,
            'completed_files': completed_files.copy(),
            'pending_files': pending_files.copy()
        }
```

**AHORA**:
```python
def progress_callback(current, total, message):
    # Recalcular pendientes cada vez (excluye el actual)
    remaining = [secure_filename(files[i].filename) for i in range(file_index, len(files))]
    
    with progress_lock:
        import_progress_cache[user_key] = {
            'current': current,
            'total': total,
            'message': message,
            'percentage': int((current / total) * 100) if total > 0 else 0,
            'current_file': filename,
            'file_number': file_index,
            'total_files': total_files,
            'completed_files': completed_files.copy(),
            'pending_files': remaining.copy()
        }
        print(f"   📊 DEBUG Progress: {file_index}/{total_files}, completed={completed_files}, pending={remaining}")
```

---

### **2. Frontend: `app/templates/portfolio/import_csv.html`**

#### **Línea 253-283**: AJAX fetch actualizado

**ANTES**:
```javascript
const response = await fetch('{{ url_for("portfolio.import_csv_process") }}', {
    method: 'POST',
    body: formData
});

console.log('Respuesta del servidor:', response.status, response.statusText);

stopProgressPolling();
await new Promise(resolve => setTimeout(resolve, 1500));

const responseText = await response.text();
console.log('Response completada, redirigiendo...');

// ❌ PROBLEMA: Ignora el redirect del servidor
window.location.href = '{{ url_for("portfolio.import_csv") }}';
```

**AHORA**:
```javascript
const response = await fetch('{{ url_for("portfolio.import_csv_process") }}', {
    method: 'POST',
    body: formData
});

console.log('Respuesta del servidor:', response.status, response.statusText);
console.log('URL final después de redirects:', response.url); // ← NUEVO

stopProgressPolling();
await new Promise(resolve => setTimeout(resolve, 1500));

// ✅ SOLUCIÓN: Sigue el redirect del servidor
window.location.href = response.url;
```

---

#### **Línea 331-360**: updateFileInfo() con debugging

**ANTES**:
```javascript
function updateFileInfo(data) {
    if (data.current_file && data.file_number && data.total_files) {
        document.getElementById('currentFileInfo').textContent = 
            `${data.file_number}/${data.total_files}: ${data.current_file}`;
    }
    // ... resto del código sin debugging
}
```

**AHORA**:
```javascript
function updateFileInfo(data) {
    console.log('updateFileInfo called with data:', data); // ← NUEVO
    
    if (data.current_file && data.file_number && data.total_files) {
        const text = `${data.file_number}/${data.total_files}: ${data.current_file}`;
        console.log('Actualizando archivo actual:', text); // ← NUEVO
        document.getElementById('currentFileInfo').textContent = text;
    } else {
        console.log('No hay datos de current_file'); // ← NUEVO
    }
    
    // ... resto con debugging
}
```

---

## 🎯 **QUÉ ESPERAR AHORA**

### **Durante la importación:**

**Primera barra (Degiro.csv)**:
```
📁 Procesando: 1/2: Degiro.csv
✅ Completados: Ninguno
⏳ En cola: • TransaccionesDegiro.csv
```

**Segunda barra (TransaccionesDegiro.csv)**:
```
📁 Procesando: 2/2: TransaccionesDegiro.csv
✅ Completados: ✓ Degiro.csv
⏳ En cola: Ninguno
```

---

### **En la consola del navegador (F12)**:

```
updateFileInfo called with data: {
  current: 5,
  total: 60,
  message: "Obteniendo Symbol + MIC...",
  percentage: 8,
  current_file: "Degiro.csv",
  file_number: 1,
  total_files: 2,
  completed_files: [],
  pending_files: ["TransaccionesDegiro.csv"]
}
Actualizando archivo actual: 1/2: Degiro.csv
Actualizando pendientes: ["TransaccionesDegiro.csv"]
```

---

### **Después de la importación:**

**Banner de éxito visible**:
```
✅ Importación Completada

• 2 archivo(s) procesados
• 1704 transacciones importadas
• 19 posiciones detectadas
• 158 dividendos registrados
• 169 comisiones
• 80 depósitos/retiros
• 177/200 assets enriquecidos con OpenFIGI
```

---

## 🚀 **PRUEBA AHORA**

1. **Abre la consola del navegador** (F12)
2. **Importa los 2 archivos de DeGiro**
3. **Observa**:
   - ✅ La sección de archivos se actualiza en tiempo real
   - ✅ Verás logs de `updateFileInfo` en la consola
   - ✅ Después de terminar, verás el banner de éxito

---

## 📊 **DEBUGGING**

Si los datos de archivos aún NO se muestran:

1. **Verifica en la consola**:
   - ¿Se llama `updateFileInfo`?
   - ¿Tiene los campos `current_file`, `completed_files`, `pending_files`?

2. **Verifica en el terminal del servidor**:
   ```
   📊 DEBUG Progress: 1/2, completed=[], pending=['TransaccionesDegiro.csv']
   ```

3. **Si NO aparecen los logs**, el problema es que el endpoint no está devolviendo los datos

---

**¡Prueba de nuevo e infórmame si funciona!** 🎯

