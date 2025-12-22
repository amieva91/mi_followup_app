# Explicación: Problema con Flatex Deposits y Solución

## El Problema Original

Los "flatex deposits" NO se estaban importando cuando se importaban múltiples archivos CSV en la misma sesión, aunque SÍ se importaban cuando se ejecutaba la importación directamente desde Python o cuando solo se importaba un archivo.

## ¿Por qué fue difícil de detectar?

### 1. El código PARECÍA estar funcionando
- El parser detectaba correctamente los flatex deposits ✅
- El importador los procesaba correctamente ✅
- En tests directos funcionaba ✅
- Pero en importación web multi-archivo fallaba ❌

### 2. No había diferencia lógica entre "Ingreso" y "flatex Deposit"

**Los depósitos normales ("Ingreso")**:
- Descripción: "Ingreso"
- Tipo: DEPOSIT
- Se parsean igual: `description.lower() == 'ingreso' or 'deposit' in description.lower()`

**Los flatex deposits ("flatex Deposit")**:
- Descripción: "flatex Deposit"
- Tipo: DEPOSIT (igual)
- Se parsean igual: `description.lower() == 'ingreso' or 'deposit' in description.lower()`

**NO había diferencia en la lógica de parseo ni importación.** Ambos se trataban exactamente igual.

### 3. El problema real: Orden de importación y snapshot compartido

## La Causa Raíz

El sistema de detección de duplicados creaba un **snapshot de transacciones existentes** para cada archivo:

**Antes (Comportamiento incorrecto)**:
```python
for file in files:
    importer = CSVImporterV2(...)  # Crea snapshot NUEVO
    importer.import_data(...)      # Importa usando ese snapshot
    # Commit
```

**Problema**:
- Archivo 1 (Transactions.csv): Snapshot vacío → Importa transacciones → Commit
- Archivo 2 (Account.csv con flatex deposits): Snapshot NUEVO que incluye transacciones del Archivo 1 → Si los flatex deposits comparten fecha/monto con otras transacciones, se marcan como duplicados ❌

## La Solución

**Después (Comportamiento correcto)**:
```python
# Crear snapshot UNA SOLA VEZ al inicio
shared_snapshot = crear_snapshot_inicial()  # Solo transacciones existentes en BD

for file in files:
    importer = CSVImporterV2(..., shared_snapshot=shared_snapshot)  # Usar snapshot compartido
    importer.import_data(...)  # Importa y actualiza snapshot compartido
    # Snapshot compartido ahora incluye las transacciones del Archivo 1
    # Commit
```

**Cambios clave**:

1. **Snapshot compartido creado una vez**: Al inicio del proceso de importación, no por archivo
2. **Actualización dinámica**: Cuando se crea una transacción, se añade al snapshot compartido ANTES del commit
3. **Compartido entre archivos**: Todos los archivos usan el mismo snapshot, que se va actualizando

## ¿Por qué los depósitos "Ingreso" funcionaban?

Los depósitos "Ingreso" probablemente estaban en el **primer archivo** que se importaba (Transactions.csv o similar), por lo que:
- Su snapshot estaba vacío (no había transacciones previas)
- Se importaban correctamente ✅
- El siguiente archivo ya los tenía en su snapshot inicial

Pero los flatex deposits estaban en Account.csv, que se importaba **después**, y entonces:
- El snapshot ya tenía transacciones del archivo anterior
- Si había alguna coincidencia de fecha/monto, se marcaban como duplicados ❌

## Cambios Técnicos Realizados

### 1. `CSVImporterV2.__init__`
```python
def __init__(self, ..., shared_snapshot: set = None):
    if shared_snapshot is not None:
        self.existing_transactions_snapshot = shared_snapshot  # Usar compartido
        self.shared_snapshot = shared_snapshot  # Referencia para actualizar
    else:
        self.existing_transactions_snapshot = set()  # Crear nuevo (comportamiento legacy)
```

### 2. Métodos de importación actualizan snapshot compartido
```python
def _import_cash_movements(self, parsed_data):
    for deposit_data in deposits:
        # ... crear transacción ...
        db.session.add(transaction)
        
        # NUEVO: Actualizar snapshot compartido si existe
        if self.shared_snapshot is not None:
            self.shared_snapshot.add(deposit_key)  # Añadir ANTES del commit
```

### 3. `portfolio.py` crea snapshot compartido
```python
# Crear snapshot UNA SOLA VEZ al inicio
shared_snapshot = set()
for account in all_accounts:
    # Añadir todas las transacciones existentes

for file in files:
    importer = CSVImporterV2(..., shared_snapshot=shared_snapshot)
    importer.import_data(...)
    # El snapshot se actualiza automáticamente dentro del importer
```

## Conclusión

**No había diferencia lógica entre "Ingreso" y "flatex Deposit"**. El problema era **arquitectural**: cómo se manejaba el snapshot de duplicados en importaciones multi-archivo.

La solución no cambió la lógica de parseo ni de tratamiento de depósitos, solo mejoró cómo se comparte el estado (snapshot) entre múltiples archivos durante la misma sesión de importación.
