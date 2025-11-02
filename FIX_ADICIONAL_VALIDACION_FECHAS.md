# 🔧 FIX ADICIONAL: Validación de Fechas en TODAS las Transacciones

**Fecha**: 2 de noviembre de 2025  
**Versión**: v3.3.5b  
**Estado**: ✅ CORREGIDO

---

## ❌ **PROBLEMA DETECTADO EN PRODUCCIÓN**

Después de implementar el fix de dividendos sin fecha, el usuario reportó un nuevo error al intentar importar `Degiro.csv`:

```
NOT NULL constraint failed: transactions.transaction_date
transaction_type='FEE', transaction_date=None
description='Apalancamiento DeGiro'
```

### **Causa**
La validación de fecha solo se había aplicado a `_import_dividends()`, pero no a:
- `_import_fees()`
- `_import_cash_movements()` (deposits/withdrawals)

---

## ✅ **SOLUCIÓN IMPLEMENTADA**

Se agregó la misma validación de fecha a **todas las funciones de importación**:

### **1. _import_fees()**
```python
def _import_fees(self, parsed_data: Dict[str, Any]):
    """Importa comisiones/fees"""
    for fee_data in parsed_data.get('fees', []):
        fee_date_raw = fee_data.get('date') or fee_data.get('date_time')
        fee_date = parse_datetime(fee_date_raw)
        
        # VALIDACIÓN CRÍTICA: Saltar si no hay fecha válida
        if not fee_date:
            print(f"   ⚠️  ADVERTENCIA: Fee sin fecha ({fee_data.get('description', 'sin descripción')}) - Saltado")
            continue
        
        # ... crear transacción ...
```

### **2. _import_cash_movements() - Deposits**
```python
for deposit_data in parsed_data.get('deposits', []):
    deposit_date_raw = deposit_data.get('date') or deposit_data.get('date_time')
    deposit_date = parse_datetime(deposit_date_raw)
    
    # VALIDACIÓN CRÍTICA: Saltar si no hay fecha válida
    if not deposit_date:
        print(f"   ⚠️  ADVERTENCIA: Depósito sin fecha - Saltado")
        continue
    
    # ... crear transacción ...
```

### **3. _import_cash_movements() - Withdrawals**
```python
for withdrawal_data in parsed_data.get('withdrawals', []):
    withdrawal_date_raw = withdrawal_data.get('date') or withdrawal_data.get('date_time')
    withdrawal_date = parse_datetime(withdrawal_date_raw)
    
    # VALIDACIÓN CRÍTICA: Saltar si no hay fecha válida
    if not withdrawal_date:
        print(f"   ⚠️  ADVERTENCIA: Retiro sin fecha - Saltado")
        continue
    
    # ... crear transacción ...
```

---

## 🔍 **INVESTIGACIÓN ADICIONAL: ¿Por qué todos los dividendos tienen fecha None?**

El usuario reportó que **159 dividendos de DeGiro fueron saltados** por no tener fecha. Esto es **muy sospechoso**.

### **Análisis del CSV**
Se ejecutó un script de debugging que confirmó que las fechas en el CSV están correctas:
```
Fila 1:
  Fecha: '04-10-2025' (len=10)
  Hora: '06:50'
  Descripción: 'Dividendo'
  Producto: 'ANXIAN YUAN CHINA HOLDINGS LTD'
  ISIN: 'BMG0400Q1197'
```

**Conclusión**: Las fechas SÍ existen en el CSV y tienen el formato correcto (`dd-mm-yyyy`).

### **Hipótesis**
El problema podría estar en cómo el parser de DeGiro almacena y consolida los dividendos. Se agregó debug logging para identificar dónde se pierde la fecha:

```python
# DEBUG: Verificar si _parse_date falla
fecha_parsed = self._parse_date(fecha)
if not fecha_parsed:
    print(f"   🐛 DEBUG: _parse_date() devolvió None para fecha='{fecha}' (len={len(fecha)})")

self.dividend_related_rows.append({
    'fecha_hora': fecha_hora,
    'isin': isin,
    'producto': producto,
    'description': description,
    'currency': currency,
    'amount': amount_value,
    'fecha_str': fecha_parsed  # ← Esta es la que llega a None
})
```

---

## 📊 **RESULTADO ESPERADO**

Al importar `Degiro.csv` de nuevo, deberías ver:

1. **Sin debug**: Si `_parse_date()` funciona correctamente, no verás mensajes `🐛 DEBUG`
2. **Con debug**: Si `_parse_date()` falla, verás líneas como:
   ```
   🐛 DEBUG: _parse_date() devolvió None para fecha='04-10-2025' (len=10)
   ```

Esto nos ayudará a identificar **dónde exactamente** se pierde la fecha.

---

## 📝 **ARCHIVOS MODIFICADOS**

| Archivo | Cambios | Líneas |
|---------|---------|--------|
| `app/services/importer_v2.py` | Validación en `_import_fees()` | 478-481 |
| `app/services/importer_v2.py` | Validación en `_import_cash_movements()` (deposits) | 508-511 |
| `app/services/importer_v2.py` | Validación en `_import_cash_movements()` (withdrawals) | 536-539 |
| `app/services/parsers/degiro_parser.py` | Debug logging en `_store_dividend_related_row()` | 260-263 |

---

## 🚀 **PRÓXIMOS PASOS**

1. **Vaciar la cuenta de DeGiro** en `/portfolio/accounts`
2. **Reimportar `Degiro.csv`**
3. **Observar la consola** para:
   - ¿Aparecen mensajes `🐛 DEBUG: _parse_date() devolvió None`?
   - ¿Aparecen warnings de "Fee sin fecha" o "Depósito sin fecha"?
   - ¿Cuántos dividendos se importan?
4. **Reportar resultados** para continuar la investigación

---

**Estado**: ✅ Validación implementada, esperando resultados de prueba para continuar investigación de dividendos.

