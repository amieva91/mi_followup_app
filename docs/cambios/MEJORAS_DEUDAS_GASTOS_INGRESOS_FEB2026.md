# Mejoras Deudas, Gastos e Ingresos - Febrero 2026

**Versión**: v9.0.0  
**Fecha**: Febrero 2026  
**Módulos afectados**: Deudas, Gastos, Ingresos

---

## Resumen ejecutivo

Mejoras en los módulos de planificación financiera: planes de deuda con edición completa, pago anticipado mejorado, categorías jerárquicas de ingresos, modales personalizados y correcciones en formularios y sincronización de datos.

---

## DEUDAS (Debts)

### Dashboard y gráfico

| Cambio | Descripción |
|--------|-------------|
| **Fondo gris en meses pasados** | El gráfico "Pagos por mes (histórico y próximos 12 meses)" muestra los meses pasados con fondo gris (`rgba(156, 163, 175, 0.2)`) para distinguirlos de los futuros |
| **Modales personalizados** | Sustitución del `confirm()` nativo por modales de la app en "Pagar anticipado" y "Solo futuras" |
| **Rango del gráfico** | Dashboard usa `months_back=6` para el historial del gráfico |

### Edición de planes

| Cambio | Descripción |
|--------|-------------|
| **Edición completa** | El formulario de edición permite modificar todos los campos: Nombre, Importe total, Número de meses, Fecha de inicio, Categoría, Notas |
| **Lógica de edición** | La edición trata el plan como si se creara de nuevo: todas las cuotas (pasadas y futuras) usan la nueva cuota mensual (`total / meses`) |
| **Validación** | Los meses no pueden ser menores que las cuotas ya pagadas |
| **Sincronización** | Cambios de total/meses actualizan todas las cuotas; cambio de fecha de inicio desplaza todas las fechas |

### Pago anticipado y descripciones

| Cambio | Descripción |
|--------|-------------|
| **Descripción pago anticipado** | Formato `"Cuota X/X - Plan - Pago Anticipado"` preservado tras sincronización |
| **Cuotas anteriores** | Actualizadas a `"Cuota 1/X - Plan"`, `"Cuota 2/X - Plan"` con X = total final de cuotas |
| **Histórico** | Columnas "MESES" (X/X) y "CUOTA/MES" actualizadas correctamente tras pago anticipado |
| **Notas** | Preservación de notas de pago anticipado al editar |
| **Plan PAID_OFF** | Al eliminar todas las cuotas futuras, el plan pasa automáticamente a PAID_OFF |

### Reestructuración

| Cambio | Descripción |
|--------|-------------|
| **Modos** | Elegir por cuota mensual o por número de meses |
| **Vista previa** | Cálculo en tiempo real antes de guardar |

### Navegación y redirección

| Cambio | Descripción |
|--------|-------------|
| **Parámetro next** | Redirección correcta según origen: crear/editar desde Gastos → vuelve a Gastos; desde Deudas → vuelve a Deudas |
| **Cancelar** | Botón Cancelar en edición respeta el parámetro `next` |

---

## GASTOS (Expenses)

### Lista de gastos

| Cambio | Descripción |
|--------|-------------|
| **Descripción y notas completas** | Sin truncar; se muestra el texto completo (eliminado `notes[:50]`) |
| **Categoría visible** | Uso de `joinedload(Expense.category)` para mostrar correctamente la categoría tras editar |

### Modales de confirmación

| Cambio | Descripción |
|--------|-------------|
| **Modal personalizado** | Al eliminar una cuota de plan desde Gastos: opciones "Eliminar entradas futuras" y "Eliminar toda la serie" |
| **Gastos recurrentes** | Opciones "Eliminar solo esta entrada" y "Eliminar toda la serie" |
| **Gastos puntuales** | Confirmación con botón "Sí, eliminar" |

### Formularios

| Cambio | Descripción |
|--------|-------------|
| **Botones Guardar** | Corrección con `requestSubmit()`, `novalidate` para envío correcto del formulario |

### Navegación

| Cambio | Descripción |
|--------|-------------|
| **Enlaces con next** | Crear plan, editar plan y cancelar desde Gastos incluyen `next=expenses` |

---

## INGRESOS (Income)

### Modelo y base de datos

| Cambio | Descripción |
|--------|-------------|
| **Jerarquía de categorías** | Campo `parent_id` en `IncomeCategory` para categorías padre/hijo |
| **Relaciones** | `parent`, `children` y propiedad `full_name` (formato "Padre > Hijo") |
| **Migración** | Columna `parent_id` en `income_categories` con FK a la misma tabla |

### Formulario de categorías

| Cambio | Descripción |
|--------|-------------|
| **Campo "Categoría padre"** | Igual que en Gastos, opcional, con texto de ayuda |
| **Nueva/Editar** | Soporte completo de `parent_id` en rutas |

### Lista de categorías

| Cambio | Descripción |
|--------|-------------|
| **Columna "Jerarquía"** | Muestra "Principal" o "Subcategoría" |
| **Vista jerárquica** | Listado ordenado por padres e hijas con indentación |
| **full_name** | Uso en formularios de ingresos, filtro y modal rápido |

### API quick_create

| Cambio | Descripción |
|--------|-------------|
| **parent_id** | Soporte en `quick_create_category` |
| **full_name** | Retorno en respuesta JSON |

---

## FORMULARIOS (común)

| Cambio | Descripción |
|--------|-------------|
| **requestSubmit() y novalidate** | Aplicado en `expenses/form.html`, `incomes/form.html`, `debts/form.html`, `debts/edit.html`, `debts/restructure.html` |

---

## Archivos modificados

### Nuevos
- `app/models/debt_plan.py`
- `app/routes/debts.py`
- `app/services/debt_service.py`
- `app/templates/debts/*`
- `app/templates/components/*`
- `migrations/versions/a1b2c3d4e5f6_add_debt_plans_and_user_config.py`
- `migrations/versions/b124ec9f496b_add_parent_id_to_income_categories.py`

### Modificados
- `app/forms/finance_forms.py` - DebtPlanEditForm con todos los campos, IncomeCategoryForm con parent_id
- `app/models/income.py` - parent_id, children, parent, full_name
- `app/routes/expenses.py` - joinedload, next parameter
- `app/routes/incomes.py` - parent_id, full_name, jerarquía
- `app/templates/expenses/*` - modales, next, joinedload
- `app/templates/incomes/*` - parent_id, jerarquía, full_name
- `app/templates/base/layout.html` - enlaces deuda
- `app/routes/__init__.py`, `app/__init__.py` - blueprints debts

---

*Documento generado a partir del sprint de mejoras Febrero 2026.*
