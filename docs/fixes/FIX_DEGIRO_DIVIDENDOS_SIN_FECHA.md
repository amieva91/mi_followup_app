# 🐛 FIX: DeGiro Dividendos "sin fecha"

**Fecha:** 2 de noviembre de 2025  
**Versión afectada:** v3.3.4  
**Versión corregida:** v3.3.5

---

## 📌 PROBLEMA

Al importar el CSV "Estado de Cuenta" de DeGiro (`Degiro.csv`), TODAS las transacciones (dividendos, fees, depósitos, retiros) eran rechazadas con el error:

```bash
⚠️  ADVERTENCIA: Dividendo sin fecha para ES0109067019 - AMADEUS IT GROUP - Saltado
⚠️  ADVERTENCIA: Fee sin fecha (Apalancamiento DeGiro) - Saltado
⚠️  ADVERTENCIA: Depósito sin fecha - Saltado
⚠️  ADVERTENCIA: Retiro sin fecha - Saltado
```

**Resultado:** 0 transacciones importadas, a pesar de que el CSV contenía 158 dividendos, 169 fees, 9 depósitos y 71 retiros.

---

## 🔍 DIAGNÓSTICO

### Investigación

1. **Parser (degiro_parser.py):**
   - ✅ Las fechas se parseaban correctamente
   - ✅ Los dividendos se consolidaban correctamente
   - ✅ `self.dividends` contenía 158 dividendos con fechas válidas
   - Formato de fecha: `datetime.date(2018, 2, 1)`

2. **Importer (importer_v2.py):**
   - ❌ La función `parse_datetime()` rechazaba las fechas
   - ❌ Devolvía `None` para todos los objetos `datetime.date`

### Causa raíz

La función `parse_datetime()` en `app/services/importer_v2.py` solo manejaba:
- Objetos `datetime` (con hora): `datetime(2018, 2, 1, 10, 42, 0)`
- Strings en formato ISO: `"2018-02-01"`

Pero **NO** manejaba objetos `datetime.date` (sin hora): `date(2018, 2, 1)`

El parser de DeGiro devolvía fechas como `datetime.date`, causando que `parse_datetime()` fallara y devolviera `None`.

---

## ✅ SOLUCIÓN

### Cambios en `app/services/importer_v2.py`

Agregué soporte para objetos `datetime.date` en la función `parse_datetime()`:

```python
def parse_datetime(date_value: Union[str, datetime, None]) -> Union[datetime, None]:
    """
    Convierte una fecha (string, datetime, o date) a objeto datetime.
    
    Args:
        date_value: Fecha como string ISO, objeto datetime, objeto date, o None
    
    Returns:
        Objeto datetime o None
    """
    from datetime import date
    
    if date_value is None:
        return None
    
    # Si ya es datetime, retornar tal cual
    if isinstance(date_value, datetime):
        return date_value
    
    # ✅ NUEVO: Si es date (sin hora), convertir a datetime con hora 00:00:00
    if isinstance(date_value, date):
        return datetime.combine(date_value, datetime.min.time())
    
    if isinstance(date_value, str):
        # Intentar parsear ISO format (YYYY-MM-DDTHH:MM:SS o YYYY-MM-DD)
        try:
            return datetime.fromisoformat(date_value)
        except ValueError:
            # Si falla, intentar solo fecha (YYYY-MM-DD)
            try:
                return datetime.strptime(date_value, '%Y-%m-%d')
            except ValueError:
                # Si todo falla, retornar None
                print(f"⚠️ WARNING: No se pudo parsear fecha: {date_value}")
                return None
    
    return None
```

**Explicación:**
- Si la fecha es un objeto `datetime.date`, se convierte a `datetime` usando `datetime.combine(date_value, datetime.min.time())`
- Esto crea un `datetime` con la misma fecha y hora `00:00:00`
- **IMPORTANTE:** El check de `isinstance(date_value, date)` debe ir **DESPUÉS** del check de `datetime`, porque `datetime` hereda de `date`

### Cambios en `app/services/parsers/degiro_parser.py`

Agregué un fallback de seguridad en `_consolidate_dividend_group()`:

```python
# Fallback: Si fecha_str es None, extraer de fecha_hora_ref
if not fecha_str and fecha_hora_ref:
    fecha_str = fecha_hora_ref.date()
elif not fecha_str:
    # Sin fecha válida, saltar este dividendo
    return
```

---

## 🧪 RESULTADOS

### Antes del fix
```bash
📊 DEBUG: Importación completada. Stats: {
    'transactions_created': 0,
    'dividends_created': 0,
    'fees_created': 0,
    'deposits_created': 0,
    'withdrawals_created': 0
}
```

### Después del fix
```bash
📊 DEBUG: Importación completada. Stats: {
    'transactions_created': 0,
    'dividends_created': 158,  ✅
    'fees_created': 169,       ✅
    'deposits_created': 9,     ✅
    'withdrawals_created': 71  ✅
}
✅ DEBUG: 407 transacciones total en esta cuenta
```

---

## 📚 LECCIONES APRENDIDAS

1. **Type Checking:** Siempre verificar que las funciones de parsing manejen todos los tipos posibles de entrada
2. **Debugging incremental:** El debug exhaustivo (imprimir en cada paso del flujo) fue clave para identificar dónde se perdían las fechas
3. **Herencia de clases:** `datetime` hereda de `date`, por lo que el orden de los `isinstance()` checks es crítico
4. **Parsers vs Importers:** Los parsers pueden devolver diferentes tipos de objetos; los importers deben ser flexibles

---

## ✅ VERIFICACIÓN

Para verificar que el fix funciona:

1. Vaciar cuenta DeGiro
2. Importar `Degiro.csv`
3. Verificar que se importan:
   - 158 dividendos
   - 169 fees
   - 9 depósitos
   - 71 retiros
4. Filtrar por tipo "DIVIDEND" y verificar que las fechas son correctas
5. Verificar que los dividendos en EUR y con conversión FX se muestran correctamente

---

## 📦 ARCHIVOS MODIFICADOS

- `app/services/importer_v2.py`: Función `parse_datetime()` (líneas 16-52)
- `app/services/parsers/degiro_parser.py`: Función `_consolidate_dividend_group()` (líneas 450-455)

---

## 🔄 DEPLOY

Este fix es **crítico** y debe desplegarse a producción lo antes posible, ya que afecta a:
- Importación de dividendos DeGiro
- Importación de fees DeGiro
- Importación de depósitos/retiros DeGiro

**Versión:** v3.3.5  
**Tag Git:** `v3.3.5-fix-degiro-dates`

