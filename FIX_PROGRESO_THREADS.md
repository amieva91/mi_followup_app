# 🔧 FIX: Barra de Progreso Thread-Safe

## ❌ **PROBLEMA ORIGINAL**

La barra de progreso se quedaba congelada mostrando el último asset procesado (100%) porque:

1. **Flask session NO es thread-safe**: Cuando el progreso se actualizaba en el thread de importación, el thread que consultaba `/import/progress` no veía los cambios.

2. **Session se limpiaba inmediatamente**: Al terminar la importación, se llamaba a `session.pop('import_progress')`, eliminando el progreso antes de que el frontend pudiera leerlo.

---

## ✅ **SOLUCIÓN IMPLEMENTADA**

### **1. Cache Global Thread-Safe**

En lugar de usar `session`, ahora usamos un **diccionario global** con un **Lock** para sincronización:

```python
from threading import Lock

# Cache global para progreso de importación (thread-safe)
import_progress_cache = {}
progress_lock = Lock()
```

### **2. Progreso por Usuario**

Cada usuario tiene su propia clave en el cache:

```python
user_key = f"user_{current_user.id}"

def progress_callback(current, total, message):
    with progress_lock:
        import_progress_cache[user_key] = {
            'current': current,
            'total': total,
            'message': message,
            'percentage': int((current / total) * 100) if total > 0 else 0
        }
```

### **3. Lectura Thread-Safe**

El endpoint `/import/progress` lee del cache con el lock:

```python
@portfolio_bp.route('/import/progress')
@login_required
def import_progress():
    user_key = f"user_{current_user.id}"
    
    with progress_lock:
        progress = import_progress_cache.get(user_key, {})
    
    return jsonify({
        'status': 'processing',
        'current': progress.get('current', 0),
        'total': progress.get('total', 0),
        'message': progress.get('message', ''),
        'percentage': progress.get('percentage', 0)
    })
```

### **4. Limpieza con Delay**

El progreso se limpia **después de 0.5 segundos** para que el frontend pueda leer el estado final (100%):

```python
# Limpiar progreso (después de un breve delay para que el frontend lea el último estado)
time.sleep(0.5)
with progress_lock:
    import_progress_cache.pop(user_key, None)
```

---

## 🔄 **FLUJO COMPLETO**

```
THREAD 1 (Import):                    THREAD 2 (Progress):
--------------------                  ---------------------
1. Inicia importación
                                     2. Poll cada 500ms
                                        GET /import/progress
3. progress_callback(1, 20, msg)
   → cache[user_1] = {1/20}
                                     4. Lee cache[user_1]
                                        → {1/20} ✅
5. progress_callback(2, 20, msg)
   → cache[user_1] = {2/20}
                                     6. Lee cache[user_1]
                                        → {2/20} ✅
...
19. progress_callback(20, 20, msg)
    → cache[user_1] = {20/20}
                                     20. Lee cache[user_1]
                                         → {20/20} ✅
21. sleep(0.5)
                                     22. Lee cache[user_1]
                                         → {20/20} ✅
23. pop cache[user_1]
                                     24. Lee cache[user_1]
                                         → {} (idle)
```

---

## 🎯 **VENTAJAS**

✅ **Thread-safe**: El Lock garantiza que no hay race conditions
✅ **Aislamiento por usuario**: Cada usuario ve solo su progreso
✅ **Sincronización real**: Ambos threads ven los mismos datos
✅ **No bloquea**: Los locks son muy rápidos (microsegundos)
✅ **Cleanup automático**: Se limpia después de cada importación

---

## 📝 **ARCHIVOS MODIFICADOS**

1. **`app/routes/portfolio.py`**:
   - Añadido `import_progress_cache` global
   - Añadido `progress_lock` para thread-safety
   - Modificado `import_progress()` para leer del cache
   - Modificado `import_csv_process()` para escribir al cache
   - Añadido delay de 0.5s antes de limpiar

2. **`run.py`**:
   - Añadido `threaded=True` para permitir múltiples peticiones simultáneas

---

## 🧪 **CÓMO PROBAR**

### **1. Reiniciar el servidor**:
```bash
cd ~/www
source venv/bin/activate
PORT=5001 python run.py
```

### **2. Importar CSVs**:
- Ve a: http://127.0.0.1:5001/portfolio/import
- Selecciona tus CSVs
- Haz clic en "Importar CSV"

### **3. Observar la barra**:
Ahora deberías ver:
```
📊 Importando archivos...

🔍 Apple Inc.: obteniendo Symbol + MIC...         15%
██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

Procesando: 3 de 20 assets
```

Y **los mensajes se actualizan en tiempo real** cada segundo aproximadamente.

---

## 🐛 **TROUBLESHOOTING**

### **Si todavía no funciona**:

1. **Verificar que Flask usa threads**:
   ```bash
   # Debe iniciar con: "threaded=True"
   PORT=5001 python run.py
   ```

2. **Ver el progreso en el backend**:
   Añade esto temporalmente en `/import/progress`:
   ```python
   print(f"DEBUG: Progress for {user_key}: {progress}")
   ```

3. **Ver en consola del navegador** (F12):
   ```javascript
   // Debería mostrar datos cada 500ms
   console.log(data);
   ```

4. **Limpiar cache del navegador**:
   - Ctrl+Shift+R (forzar recarga)
   - O modo incógnito

---

## ✅ **COMPLETADO**

- [x] Cache global thread-safe implementado
- [x] Lock para sincronización añadido
- [x] Progreso por usuario aislado
- [x] Delay de 0.5s antes de limpiar
- [x] Endpoint `/import/progress` actualizado
- [x] Callback de progreso actualizado
- [x] `threaded=True` en run.py
- [x] Documentación completa

---

## 🚀 **LISTO PARA PROBAR**

Reinicia el servidor con `PORT=5001 python run.py` y prueba la importación.

**Ahora la barra debería actualizarse correctamente en tiempo real!** 🎉

