# Plan de Implementación: Módulo Bancos + Ajustes + Sync Broker + Resúmenes

**Fecha**: Febrero 2026  
**Versión**: v9.1.0  
**Documento de referencia**: Especificación acordada en conversación

---

## Resumen Ejecutivo

1. **Módulo Bancos**: Nueva pestaña para registrar saldos mensuales por entidad bancaria
2. **Ajustes dinámicos**: Reconciliación entre cash bancario e ingresos/gastos (categoría "Ajustes", bloqueada)
3. **Sync Broker**: DEPOSIT/WITHDRAWAL de IBKR/DeGiro reflejados como gasto/ingreso
4. **Resúmenes**: Formato media+(total), cuadros de resumen encima de categorías

---

## FASE 1: Modelo y CRUD Bancos

### 1.1 Modelo de datos

**Archivo**: `app/models/bank.py` (nuevo)

```python
# Bank: entidad bancaria
- id, user_id, name, icon (opcional, default '🏦'), color (opcional)
- created_at

# BankBalance: saldo por banco y mes
- id, user_id, bank_id, year (int), month (int), amount (float)
- created_at, updated_at
- UniqueConstraint: (bank_id, year, month)
```

**Migración**: Crear tablas `banks` y `bank_balances`

### 1.2 Rutas y vistas

**Blueprint**: `app/routes/banks.py` (nuevo)
- `banks_bp`, prefix `/banks`

**Rutas**:
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Dashboard bancos: lista de bancos, selector de mes, formulario saldos, gráfico evolución |
| GET/POST | `/new` | Crear banco |
| GET/POST | `/<id>/edit` | Editar banco |
| POST | `/<id>/delete` | Eliminar banco (validar si tiene saldos) |
| POST | `/balances` | Guardar/actualizar saldos del mes (JSON o form) |

### 1.3 Templates

**Directorio**: `app/templates/banks/`
- `list.html` o `dashboard.html`: Vista principal con:
  - Lista de bancos con enlaces editar/eliminar
  - Selector año/mes
  - Formulario: input de cantidad por cada banco
  - Gráfico de evolución (Chart.js, suma total por mes)
  - Botón "Añadir banco"

- `bank_form.html`: Formulario crear/editar banco (nombre, icono opcional)

### 1.4 Servicio

**Archivo**: `app/services/bank_service.py` (nuevo)
- `get_total_cash_by_month(user_id, year, month)` → float
- `get_cash_evolution(user_id, months=12)` → lista {month_label, total}
- `get_balances_for_month(user_id, year, month)` → dict {bank_id: amount}

---

## FASE 2: Categoría "Ajustes" y servicio de ajuste

### 2.1 Categoría "Ajustes"

**En ambos modelos** (Income y Expense):
- Crear categoría "Ajustes" si no existe (por usuario)
- Campo o flag: `is_system_category` o `name == 'Ajustes'` → bloquear para uso manual
  - En formularios de nuevo ingreso/gasto: excluir "Ajustes" del selector
  - En categorías: mostrar como solo lectura, sin opción eliminar (o con aviso)

**Helper**: `app/services/category_helpers.py` o en cada modelo
- `get_or_create_ajustes_category(user_id, income_or_expense)` → category_id

### 2.2 Servicio de ajuste

**Archivo**: `app/services/reconciliation_service.py` (nuevo)

```python
def get_adjustment_for_month(user_id, year, month) -> Optional[float]:
    """
    Ajuste = Gastos_reales - Gastos_registrados
    Gastos_reales = Cash(mes-1) + Ingresos(mes) - Cash(mes)
    
    Requiere: BankBalance para (year, month) y (year, month-1)
    Returns: float (positivo → gasto, negativo → ingreso) o None si no aplica
    """
```

**Consideraciones**:
- Ingresos del mes: incluir Income manual + WITHDRAWAL broker (Fase 4)
- Gastos del mes: incluir Expense manual + DEPOSIT broker (Fase 4), excluir cuotas futuras deuda
- Si no hay dos meses consecutivos con saldo → return None

---

## FASE 3: Integración del ajuste en Gastos e Ingresos

### 3.1 Modelos y consultas

**Income** (ya tiene `get_total_by_period`, `get_category_summary`, `get_monthly_totals`):
- Modificar para que acepten un parámetro opcional `include_adjustment=True`
- Cuando True, sumar el ajuste negativo (como ingreso) al total del mes
- En `get_category_summary`: añadir categoría "Ajustes" con el ajuste (si < 0)

**Expense** (igual):
- Sumar ajuste positivo (como gasto) al total
- En `get_category_summary`: añadir "Ajustes" con el ajuste (si > 0)

**Alternativa más limpia**: No modificar los modelos, sino un servicio de agregación que llame a Income/Expense y añada el ajuste al resultado. Así los modelos siguen con datos "reales" y el ajuste se inyecta en la capa de presentación.

**Recomendación**: Servicio `app/services/income_expense_aggregator.py`:
- `get_income_total_with_adjustment(user_id, start, end)` 
- `get_expense_total_with_adjustment(user_id, start, end)`
- `get_income_category_summary_with_adjustment(user_id, months)` 
- `get_expense_category_summary_with_adjustment(user_id, months)`
- `get_income_monthly_totals_with_adjustment(user_id, months)`
- `get_expense_monthly_totals_with_adjustment(user_id, months)`

Estos métodos llaman a los modelos existentes y añaden el ajuste donde corresponda.

### 3.2 Rutas

**incomes.py** y **expenses.py**: Sustituir llamadas a modelo por el agregador (solo donde se pasen totales a la plantilla).

### 3.3 Lista de gastos/ingresos

En la tabla, ¿mostrar una fila "Ajuste de cierre" por mes?
- Opción A: No, solo en resúmenes y gráficos
- Opción B: Sí, fila sintética en la tabla cuando hay ajuste

Recomendación: **A** (solo en resúmenes). Si el usuario quiere verlo en detalle, puede ir a la pestaña Bancos.

---

## FASE 4: Sync Broker (DEPOSIT/WITHDRAWAL → Ingreso/Gasto)

### 4.1 Lógica

- **WITHDRAWAL** (broker → banco) = **Ingreso**, categoría "Dividendos"
- **DEPOSIT** (banco → broker) = **Gasto**, categoría "Deposito en Broker IBKR" o "Deposito en Broker DeGiro"

Solo cuentas de brokers **IBKR** y **DeGiro** (Stock/ETF).

### 4.2 Implementación dinámica

No crear registros Income/Expense. Incluir los importes al calcular totales.

**Archivo**: `app/services/broker_sync_service.py` (nuevo)

```python
def get_broker_withdrawals_by_month(user_id, year, month) -> float:
    """Suma de WITHDRAWAL en EUR para cuentas IBKR/DeGiro en ese mes"""

def get_broker_deposits_by_month(user_id, year, month) -> dict:
    """Dict {broker_name: amount} para DEPOSIT en ese mes (IBKR, DeGiro)"""
```

Usar `convert_to_eur` para transacciones en otras divisas.

### 4.3 Categorías

- **Ingresos**: "Dividendos" (crear si no existe). Sumar WITHDRAWAL al total de esa categoría.
- **Gastos**: "Deposito en Broker IBKR", "Deposito en Broker DeGiro" (crear si no existen). Son categorías de primer nivel (sin padre).

### 4.4 Integración en agregador

El `income_expense_aggregator` debe:
- Al sumar ingresos del mes: + `get_broker_withdrawals_by_month()`
- Al sumar gastos del mes: + `get_broker_deposits_by_month()` (suma total)
- En resumen por categoría: añadir "Dividendos" (broker) y "Deposito en Broker X" con sus importes

### 4.5 Filtro Stock/ETF

Las cuentas IBKR/DeGiro suelen ser Stock/ETF. Si hay cuentas mixtas, filtrar por `Broker.name in ('IBKR', 'DeGiro')`. No incluir brokers Manual u otros.

---

## FASE 5: Resúmenes por categoría (formato media + total)

### 5.1 Cambio de formato

**Antes**: `450 €` (solo total)
**Después**: `450 €/mes (5.400 €)` → media mensual + total entre paréntesis

### 5.2 Modelos

**Income.get_category_summary** (o el agregador):
- Calcular `total` (suma)
- Calcular `months_with_data` (meses con ingresos > 0)
- `average = total / months_with_data` si months_with_data > 0, si no 0
- Añadir `average` y `total` a cada item

**Expense.get_category_summary**:
- Igual, con estructura jerárquica (padres e hijos)

### 5.3 Templates

**incomes/list.html** y **expenses/list.html**:
- Cambiar `{{ item.total }}` por `{{ '%.2f'|format(item.average) }} €/mes ({{ '%.2f'|format(item.total) }} €)`
- En expenses con hijos: aplicar el mismo formato

---

## FASE 6: Cuadros de resumen (encima de categorías)

### 6.1 Indicadores Gastos

| Indicador | Cálculo |
|-----------|---------|
| Media mensual | Promedio gastos/mes en período |
| Total período | Suma gastos últimos 12 meses (o disponible) |
| Mes con más gastos | Mes y importe máximo |
| Meses con datos | Número de meses con gastos > 0 |
| Tendencia (opcional) | Último mes vs media (↑↓≈) |

### 6.2 Indicadores Ingresos

| Indicador | Cálculo |
|-----------|---------|
| Media mensual | Promedio ingresos/mes |
| Total período | Suma ingresos |
| Mes con más ingresos | Mes y importe máximo |
| Meses con datos | Número de meses |
| Tendencia (opcional) | Último mes vs media |

### 6.3 Servicio

**Archivo**: `app/services/summary_metrics_service.py` (nuevo) o extender agregador
- `get_expense_summary_metrics(user_id, months=12)`
- `get_income_summary_metrics(user_id, months=12)`

### 6.4 Templates

Añadir bloque encima del resumen por categoría en `incomes/list.html` y `expenses/list.html`:
- Grid de cards con los indicadores
- Estilo similar a las cards del dashboard principal

---

## FASE 7: Navbar y registro

### 7.1 Navbar

**Archivo**: `app/templates/base/layout.html`
- Añadir dropdown "🏦 Bancos" entre Deudas y Portfolio
- Enlaces: Dashboard Bancos (o similar)

### 7.2 App init

**Archivo**: `app/__init__.py`
- Importar y registrar `banks_bp`

---

## Orden de implementación recomendado

| # | Fase | Dependencias |
|---|------|--------------|
| 1 | Modelo Bank, BankBalance + migración | - |
| 2 | CRUD Bancos, vistas, formulario saldos | Fase 1 |
| 3 | Gráfico evolución en vista Bancos | Fase 1, 2 |
| 4 | Categoría Ajustes (crear, bloquear) | - |
| 5 | ReconciliationService (cálculo ajuste) | Fase 1 |
| 6 | BrokerSyncService (DEPOSIT/WITHDRAWAL) | - |
| 7 | IncomeExpenseAggregator (incluye ajuste + broker) | Fases 4, 5, 6 |
| 8 | Integración agregador en rutas incomes/expenses | Fase 7 |
| 9 | Formato categorías: media + (total) | - |
| 10 | SummaryMetricsService + cuadros resumen | - |
| 11 | Pestaña Bancos en navbar + registro blueprint | Fases 1-3 |

---

## Archivos a crear

| Archivo | Descripción |
|---------|-------------|
| `app/models/bank.py` | Bank, BankBalance |
| `app/routes/banks.py` | Blueprint Bancos |
| `app/services/bank_service.py` | Lógica saldos y evolución |
| `app/services/reconciliation_service.py` | Cálculo ajuste |
| `app/services/broker_sync_service.py` | DEPOSIT/WITHDRAWAL → totals |
| `app/services/income_expense_aggregator.py` | Totales con ajuste + broker |
| `app/services/summary_metrics_service.py` | Métricas para cuadros resumen |
| `app/templates/banks/dashboard.html` | Vista principal Bancos |
| `app/templates/banks/bank_form.html` | Formulario banco |
| `migrations/versions/xxx_add_banks_and_bank_balances.py` | Migración |

---

## Archivos a modificar

| Archivo | Cambios |
|---------|---------|
| `app/models/__init__.py` | Import Bank, BankBalance |
| `app/__init__.py` | Registrar banks_bp |
| `app/routes/incomes.py` | Usar agregador, pasar summary_metrics |
| `app/routes/expenses.py` | Usar agregador, pasar summary_metrics |
| `app/templates/incomes/list.html` | Cuadros resumen, formato media+(total), bloquear Ajustes en selector |
| `app/templates/expenses/list.html` | Igual |
| `app/templates/base/layout.html` | Dropdown Bancos |
| `app/forms/` | Validar que Ajustes no sea seleccionable en formularios |

---

## Validaciones y casos límite

- Eliminar banco: solo si no tiene saldos, o preguntar si eliminar saldos
- Eliminar categoría Ajustes: no permitir
- Crear ingreso/gasto en Ajustes: no permitir (excluir del selector)
- Mes sin datos en resumen: mostrar 0 o "—" según convenga

---

*Documento generado como plan de implementación. Actualizar conforme avance el desarrollo.*
