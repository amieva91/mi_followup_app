# 🔍 FIX: Debug Completo para Diagnosticar Errores

## ❌ **PROBLEMA ACTUAL**

Los archivos CSV están fallando al importarse:
```
📊 DEBUG: Preparando redirect con stats: {'files_failed': 2, ...}
```

**Pero NO sabemos por qué**, porque el `except` no estaba imprimiendo los errores.

---

## ✅ **SOLUCIÓN: Debug Extensivo**

### **1. Prints en CADA Etapa**

He añadido prints detallados en cada paso del proceso:

```python
# Al guardar el archivo
print(f"\n📊 DEBUG: Archivo guardado: {filepath}")

# Al detectar formato
print(f"📊 DEBUG: Detectando formato del CSV...")

# Al parsear
print(f"📊 DEBUG: CSV parseado correctamente. Formato: {parsed_data.get('format', 'unknown')}")

# Al importar
print(f"\n📊 DEBUG: Iniciando importación para archivo: {filename}")
print(f"📊 DEBUG: Llamando a importer.import_data()...")
print(f"📊 DEBUG: Importación completada. Stats: {stats}")
```

---

### **2. Traceback Completo en Errores**

Ahora cuando falla un archivo, se imprime el **traceback completo**:

```python
except Exception as e:
    print(f"\n❌ ERROR importando {file.filename}:")
    print(f"   Tipo de error: {type(e).__name__}")
    print(f"   Mensaje: {str(e)}")
    import traceback
    print(f"   Traceback:\n{traceback.format_exc()}")
```

**Esto te dirá**:
- ✅ **Qué archivo** falló
- ✅ **Tipo de error** (ValueError, KeyError, etc.)
- ✅ **Mensaje de error** exacto
- ✅ **Línea exacta** donde falló (traceback completo)

---

### **3. Banner de Error en Frontend**

Ahora si hay errores, verás un **banner rojo** con:
- Número de archivos fallidos
- Primeros 50 caracteres de cada error
- Un consejo para revisar la consola del servidor

```
┌─────────────────────────────────────────────┐
│ ❌  Error en la Importación                 │
│                                              │
│ • 2 archivo(s) fallaron al importarse       │
│                                              │
│ Errores:                                     │
│ Degiro.csv: KeyError: 'symbol' not found    │
│ IBKR.csv: ValueError: invalid date format   │
│                                              │
│ 💡 Consejo: Revisa la consola del servidor  │
│    para ver el error completo (traceback).  │
└─────────────────────────────────────────────┘
```

---

## 🚀 **PROBAR AHORA**

### **1. Reiniciar el servidor**:
```bash
cd ~/www
PORT=5001 python run.py
```

### **2. Importar tus CSVs de nuevo**:
- Ve a: http://127.0.0.1:5001/portfolio/import
- **Refresca** (Ctrl+Shift+R)
- Selecciona tus 2 CSVs de DeGiro
- Haz clic en "Importar CSV"

### **3. Observar la CONSOLA del servidor**:

**Si falla al guardar el archivo:**
```
📊 DEBUG: Archivo guardado: /uploads/temp_1_Degiro.csv
❌ ERROR importando Degiro.csv:
   Tipo de error: FileNotFoundError
   Mensaje: [Errno 2] No such file or directory: '/uploads/...'
   Traceback:
     File "app/routes/portfolio.py", line 1030, in import_csv_process
       file.save(filepath)
     ...
```

**Si falla al detectar formato:**
```
📊 DEBUG: Archivo guardado: /uploads/temp_1_Degiro.csv
📊 DEBUG: Detectando formato del CSV...
❌ ERROR importando Degiro.csv:
   Tipo de error: ValueError
   Mensaje: Formato de CSV no reconocido
   Traceback:
     File "app/routes/portfolio.py", line 1035, in import_csv_process
       parsed_data = detect_and_parse(filepath)
     File "app/services/csv_detector.py", line 45, in detect_and_parse
       raise ValueError("Formato de CSV no reconocido")
```

**Si falla al parsear:**
```
📊 DEBUG: Archivo guardado: /uploads/temp_1_Degiro.csv
📊 DEBUG: Detectando formato del CSV...
❌ ERROR importando Degiro.csv:
   Tipo de error: KeyError
   Mensaje: 'ISIN'
   Traceback:
     File "app/routes/portfolio.py", line 1035, in import_csv_process
       parsed_data = detect_and_parse(filepath)
     File "app/services/parsers/degiro_parser.py", line 120, in parse
       isin = row['ISIN']
     KeyError: 'ISIN'
```

**Si falla al importar:**
```
📊 DEBUG: Archivo guardado: /uploads/temp_1_Degiro.csv
📊 DEBUG: Detectando formato del CSV...
📊 DEBUG: CSV parseado correctamente. Formato: DEGIRO_TRANSACTIONS
📊 DEBUG: Iniciando importación para archivo: Degiro.csv
📊 DEBUG: Llamando a importer.import_data()...
❌ ERROR importando Degiro.csv:
   Tipo de error: IntegrityError
   Mensaje: (sqlite3.IntegrityError) UNIQUE constraint failed: assets.isin
   Traceback:
     File "app/routes/portfolio.py", line 1053, in import_csv_process
       stats = importer.import_data(parsed_data, progress_callback=progress_callback)
     File "app/services/importer.py", line 150, in import_data
       db.session.commit()
     ...
```

---

### **4. Copiar el error completo**

Una vez que veas el error en la consola:

1. **Copia TODO el traceback** (desde `❌ ERROR` hasta el final)
2. **Pégalo aquí** para que pueda diagnosticar el problema exacto

---

## 🎯 **ERRORES COMUNES Y SOLUCIONES**

### **A) "Formato de CSV no reconocido"**
**Causa**: El CSV no es de IBKR ni DeGiro, o tiene un formato diferente.

**Solución**:
- Verifica que sea el CSV correcto
- Para IBKR: "Activity Statement (CSV)"
- Para DeGiro: "Estado de cuenta (CSV)" o "Transacciones (CSV)"

---

### **B) "KeyError: 'ISIN'" o similar**
**Causa**: Falta una columna esperada en el CSV.

**Solución**:
- El parser espera ciertas columnas
- Puede que DeGiro haya cambiado el formato
- Envíame las primeras 5 líneas del CSV para ajustar el parser

---

### **C) "UNIQUE constraint failed: assets.isin"**
**Causa**: Ya existe un asset con ese ISIN en la BD.

**Solución**:
- Debería detectarse como duplicado, no fallar
- Puede ser un bug en el importer
- Envíame el traceback completo

---

### **D) "FileNotFoundError" al guardar archivo**
**Causa**: No existe la carpeta `uploads/`.

**Solución**:
```bash
cd ~/www
mkdir -p uploads
chmod 755 uploads
```

---

## 📝 **EJEMPLO DE REPORTE DE ERROR**

Cuando me envíes el error, incluye:

1. **Traceback completo de la consola**:
```
❌ ERROR importando Degiro.csv:
   Tipo de error: KeyError
   Mensaje: 'ISIN'
   Traceback:
     File "app/routes/portfolio.py", line 1035, in import_csv_process
       parsed_data = detect_and_parse(filepath)
     File "app/services/parsers/degiro_parser.py", line 120, in parse
       isin = row['ISIN']
     KeyError: 'ISIN'
```

2. **Qué CSV estabas importando**:
   - "TransaccionesDegiro.csv" o "Degiro.csv" (Estado de cuenta)

3. **Primera línea del CSV** (headers):
```
Fecha,Hora,Producto,ISIN,Descripción,Variación,Saldo,Orden
```

---

## ✅ **SIGUIENTES PASOS**

1. **Reinicia el servidor** con `PORT=5001 python run.py`
2. **Intenta importar de nuevo**
3. **Copia TODO el traceback** de la consola del servidor
4. **Pégalo aquí** para diagnosticar el problema exacto

Con estos debug messages, podré identificar el problema en **segundos**. 🚀

---

## 📊 **ARCHIVOS MODIFICADOS**

1. ✅ `app/routes/portfolio.py` - Debug extensivo + traceback + banner de error
2. ✅ `app/templates/portfolio/import_csv.html` - Banner de error en UI
3. ✅ `FIX_DEBUG_COMPLETO.md` - Esta documentación

---

**🔍 Ahora tenemos debug completo. Reinicia el servidor e intenta de nuevo!**

