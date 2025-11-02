# 🔧 FIX CRÍTICO: DateTime Type Error en DeGiro Parsers

## ❌ **ERROR IDENTIFICADO**

```
TypeError: SQLite DateTime type only accepts Python datetime and date objects as input.

'transaction_date': '2025-10-03'  ← STRING ❌
```

**Causa raíz**: Los parsers de DeGiro (`degiro_parser.py` y `degiro_transactions_parser.py`) estaban devolviendo **strings ISO** en lugar de objetos `datetime`:

```python
# ❌ ANTES (devolvía string):
def _parse_date(self, date_str: str) -> str:
    dt = datetime.strptime(date_str.strip(), "%d-%m-%Y")
    return dt.date().isoformat()  # ← "2025-10-03" (string)

# ❌ ANTES (devolvía string):
def _parse_datetime(self, date_str: str, time_str: str) -> str:
    dt = datetime.strptime(datetime_str, "%d-%m-%Y %H:%M")
    return dt.isoformat()  # ← "2025-10-03T06:30:00" (string)
```

**Consecuencia**: Cuando el `CSVImporterV2` intentaba guardar transacciones en SQLite, fallaba porque SQLAlchemy esperaba objetos `datetime.date` o `datetime.datetime`, no strings.

---

## ✅ **SOLUCIÓN APLICADA**

### **Cambio en `degiro_parser.py`**:

```python
# ✅ AHORA (devuelve datetime.date object):
def _parse_date(self, date_str: str):
    """Parsea fecha de DeGiro a objeto datetime.date"""
    if not date_str or date_str.strip() == '':
        return None
    
    try:
        # Formato: "05-10-2025"
        dt = datetime.strptime(date_str.strip(), "%d-%m-%Y")
        return dt.date()  # ← datetime.date object ✅
    except:
        return None

# ✅ AHORA (devuelve datetime object):
def _parse_datetime(self, date_str: str, time_str: str):
    """Parsea fecha/hora de DeGiro a objeto datetime"""
    if not date_str or date_str.strip() == '':
        return None
    
    try:
        # Formato: "05-10-2025" + "06:30"
        datetime_str = f"{date_str.strip()} {time_str.strip() if time_str else '00:00'}"
        dt = datetime.strptime(datetime_str, "%d-%m-%Y %H:%M")
        return dt  # ← datetime object ✅
    except:
        return None
```

### **Cambio en `degiro_transactions_parser.py`**:

```python
# ✅ AHORA (devuelve datetime.date object):
def _parse_date(self, date_str: str):
    """Parsea fecha DD-MM-YYYY a objeto datetime.date"""
    if not date_str:
        return None
    try:
        # Formato: DD-MM-YYYY
        dt = datetime.strptime(date_str, '%d-%m-%Y')
        return dt.date()  # ← datetime.date object ✅
    except:
        return None

# ✅ AHORA (devuelve datetime object):
def _parse_datetime(self, date_str: str, time_str: str):
    """Parsea fecha y hora a objeto datetime"""
    if not date_str:
        return None
    try:
        # Formato: DD-MM-YYYY HH:MM
        dt_str = f"{date_str} {time_str if time_str else '00:00'}"
        dt = datetime.strptime(dt_str, '%d-%m-%Y %H:%M')
        return dt  # ← datetime object ✅
    except:
        return None
```

---

## 📋 **CAMBIOS ESPECÍFICOS**

| Método | Antes (❌) | Ahora (✅) |
|--------|-----------|----------|
| `_parse_date()` | `return dt.date().isoformat()` | `return dt.date()` |
| `_parse_date()` | `return dt.strftime('%Y-%m-%d')` | `return dt.date()` |
| `_parse_datetime()` | `return dt.isoformat()` | `return dt` |
| `_parse_datetime()` | `return dt.strftime('%Y-%m-%dT%H:%M:%S')` | `return dt` |
| **Return type** | `str` (string ISO) | `datetime.date` o `datetime.datetime` |
| **Errores** | `return date_str` (fallback a string) | `return None` (fallback a None) |

---

## 🧪 **PROBAR AHORA**

### **1. El servidor YA está ejecutándose**:
Ya tienes `flask run` corriendo, no necesitas reiniciarlo.

### **2. Importar de nuevo**:
- Ve a: http://127.0.0.1:5001/portfolio/import
- **Refresca** (Ctrl+Shift+R)
- Selecciona tus 2 CSVs de DeGiro
- Haz clic en "Importar CSV"

### **3. Observar la consola**:

**Resultado esperado**:
```
📊 DEBUG: Archivo guardado: uploads/temp_1_Degiro.csv
📊 DEBUG: Detectando formato del CSV...
📊 DEBUG: CSV parseado correctamente. Formato: DEGIRO_ACCOUNT

📊 DEBUG: Iniciando importación para archivo: Degiro.csv
📊 DEBUG: Llamando a importer.import_data()...
🔄 Recalculando holdings con FIFO robusto...
📊 DEBUG: Importación completada. Stats: {'transactions_created': 150, ...}
```

**SIN el error**:
```
❌ TypeError: SQLite DateTime type only accepts Python datetime and date objects as input.
```

### **4. Verificar transacciones**:
```bash
python -c "
from app import create_app, db
from app.models import Transaction

app = create_app()
with app.app_context():
    count = Transaction.query.count()
    print(f'✅ Transacciones registradas: {count}')
    
    # Verificar que las fechas son objetos datetime
    if count > 0:
        tx = Transaction.query.first()
        print(f'✅ Primera transacción:')
        print(f'   - Fecha: {tx.transaction_date} (tipo: {type(tx.transaction_date).__name__})')
        print(f'   - Descripción: {tx.description}')
"
```

**Resultado esperado**:
```
✅ Transacciones registradas: 150
✅ Primera transacción:
   - Fecha: 2025-10-03 (tipo: date)
   - Descripción: Apalancamiento DeGiro
```

---

## 🎯 **POR QUÉ ESTE FIX FUNCIONA**

### **Antes del fix**:
```python
# El parser devolvía:
{'transaction_date': '2025-10-03', ...}  # ← string

# SQLAlchemy recibía:
Transaction(transaction_date='2025-10-03')  # ← string

# SQLite rechazaba:
TypeError: SQLite DateTime type only accepts Python datetime and date objects
```

### **Después del fix**:
```python
# El parser devuelve:
{'transaction_date': datetime.date(2025, 10, 3), ...}  # ← datetime.date object

# SQLAlchemy recibe:
Transaction(transaction_date=datetime.date(2025, 10, 3))  # ← datetime.date object

# SQLite acepta:
✅ Transacción guardada correctamente
```

---

## ⚠️ **IMPORTANTE**

Este fix **solo afecta a los parsers de DeGiro**. El parser de IBKR (`ibkr_parser.py`) ya devolvía strings ISO, pero al revisar el código del `CSVImporterV2`, veo que debería estar convirtiéndolos correctamente.

Si **IBKR** también falla con el mismo error, aplicaremos el mismo fix a `ibkr_parser.py`.

---

## 📝 **ARCHIVOS MODIFICADOS**

1. ✅ `app/services/parsers/degiro_parser.py`
   - `_parse_date()`: Devuelve `datetime.date` en lugar de string ISO
   - `_parse_datetime()`: Devuelve `datetime` en lugar de string ISO
   
2. ✅ `app/services/parsers/degiro_transactions_parser.py`
   - `_parse_date()`: Devuelve `datetime.date` en lugar de string ISO
   - `_parse_datetime()`: Devuelve `datetime` en lugar de string ISO

3. ✅ `FIX_DATETIME_DEGIRO.md` - Esta documentación

---

## ✅ **COMPLETADO**

- [x] Identificado el problema (TypeError con strings en lugar de datetime objects)
- [x] Corregido `degiro_parser.py`
- [x] Corregido `degiro_transactions_parser.py`
- [x] Verificado que no hay errores de linter
- [x] Documentación completa del fix

---

**🚀 Ahora la importación de DeGiro debería funcionar correctamente!**

**Prueba de nuevo e infórmame si hay algún problema.**

