# Plan de pruebas – Mejoras módulo Deudas (Fases 1–4)

**Fecha**: Enero 2026  
**Módulos**: Gastos, Ingresos, Deudas

---

## Requisitos previos

- Servidor Flask ejecutándose (`python run.py`)
- Usuario con sesión iniciada
- Datos de prueba: al menos 1 categoría de gastos, 1 de ingresos, y (opcional) 1 plan de deuda activo

---

## Fase 1 – Bugs críticos

### 1.1 CSRF en delete (ingresos y gastos)

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Ir a **Gastos** → Eliminar un gasto puntual | Modal de confirmación → Al confirmar, se elimina sin error 400 |
| 2 | Ir a **Ingresos** → Eliminar un ingreso puntual | Igual comportamiento |
| 3 | Eliminar un gasto recurrente → "Eliminar toda la serie" | Serie completa eliminada sin error |
| 4 | Eliminar un ingreso recurrente → "Eliminar toda la serie" | Serie completa eliminada sin error |

### 1.2 Gastos: solo cuotas vencidas

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Tener un plan de deuda activo con cuotas futuras | En **Gastos**, no aparecen cuotas con fecha futura |
| 2 | Revisar la lista de gastos | Solo se muestran cuotas con `date <= hoy` |
| 3 | Comprobar que las cuotas pasadas sí aparecen | Las ya vencidas están visibles |

### 1.3 Pagar anticipado

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Ir a **Deudas** → Plan activo con varias cuotas futuras | Plan visible en la tabla |
| 2 | Pulsar "✓ Pagar anticipado" y confirmar | Mensaje de éxito |
| 3 | Ir a **Gastos** | Existe un gasto único con el importe restante en el mes actual |
| 4 | Volver a **Deudas** | Plan aparece como "pagado" (histórico) |
| 5 | Comprobar que no quedan cuotas futuras del plan | Solo el gasto de pago anticipado en Gastos |

---

## Fase 2 – UX rápida

### 2.1 Layout form de deudas

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Ir a **Deudas** → "+ Nueva deuda" | Formulario se muestra a ancho completo (sin `max-w-2xl`) |
| 2 | Comparar con formulario de gastos/ingresos | Mismo estilo de layout ancho |

### 2.2 Orden por caducidad

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Tener 2+ planes activos con distintas fechas de fin | Planes ordenados por fecha de finalización (el que termina antes, primero) |

### 2.3 Columna meses "X/Y"

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Ver tabla de planes activos | Columna "Meses" muestra "3/12" (pagados/total), no solo "12" |

### 2.4 Modal crear categoría

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Ir a **Gastos** → "+ Nuevo Gasto" | Junto al desplegable de categoría hay botón "+" |
| 2 | Pulsar "+" | Modal para crear categoría sin cambiar de página |
| 3 | Crear categoría y guardar | Modal se cierra, categoría seleccionada en el desplegable |
| 4 | Repetir en **Ingresos** → "+ Nuevo Ingreso" | Mismo comportamiento |
| 5 | Ir a **Deudas** → "+ Nueva deuda" | Mismo comportamiento en el selector de categoría |

---

## Fase 3 – Gráfico

### 3.1 Colores por plan (stacked)

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Tener 2+ planes activos con cuotas en el rango visible | Gráfico de barras apiladas con un color distinto por plan |
| 2 | Revisar la leyenda | Cada plan aparece con su nombre y color |

### 3.2 Cuotas pasadas en gráfico

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Plan con cuotas ya pagadas (meses anteriores) | Barras incluyen histórico (12 meses atrás) |
| 2 | Título del gráfico | Indica "histórico y próximos 12 meses" |

### 3.3 Hover tabla → resaltar en gráfico

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Pasar el cursor sobre una fila de plan activo | En el gráfico solo se resaltan las barras de ese plan |
| 2 | Quitar el cursor | Vuelve a mostrarse el gráfico completo con todos los planes |

---

## Fase 4 – Funcionalidad extra

### 4.1 Resumen por categoría (ingresos/gastos)

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Ir a **Gastos** | Bloque "Resumen por categoría (últimos 12 meses)" encima de la lista |
| 2 | Categorías con subcategorías | Se pueden expandir con clic (▶/▼) para ver desglose |
| 3 | Clic en subcategoría del resumen | Lista de gastos filtrada por esa categoría |
| 4 | Ir a **Ingresos** | Resumen similar (12 meses, por categoría) |
| 5 | Clic en categoría del resumen | Lista filtrada por esa categoría |

### 4.2 Sección planes no activos

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Tener al menos 1 plan PAID_OFF o CANCELLED | Aparece sección "Histórico (pagados / cancelados)" debajo de planes activos |
| 2 | Revisar tabla | Muestra nombre, total, estado (✓ Pagado / ⏹ Cancelado), inicio, categoría |
| 3 | Pulsar "✏️ Editar" en un plan histórico | Formulario de edición (nombre, categoría, notas) |
| 4 | Pulsar "🗑 Eliminar" | Confirmación → plan y cuotas eliminados del historial |

### 4.3 Reestructuración de deuda

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Plan activo con cuotas futuras | En la fila hay enlace "🔄 Reestructurar" |
| 2 | Pulsar "Reestructurar" | Página con formulario y bloque con: pendiente total, cuotas actuales |
| 3 | Introducir nueva cuota mensual (ej. 50 €) y guardar | Mensaje de éxito, redirección al dashboard |
| 4 | Revisar plan en dashboard | Cuota mensual actualizada, meses recalculados |
| 5 | Ir a **Gastos** | Cuotas futuras nuevas con el importe indicado |

---

## Checklist rápido (por fases)

- [ ] **Fase 1**: CSRF OK, solo cuotas vencidas, pagar anticipado correcto
- [ ] **Fase 2**: Layout ancho, orden caducidad, meses X/Y, modal categoría
- [ ] **Fase 3**: Colores stacked, histórico en gráfico, hover tabla↔gráfico
- [ ] **Fase 4**: Resumen categorías, planes no activos, reestructuración

---

## Notas

- Si el puerto 5000 está ocupado, detener el proceso existente o usar otro puerto.
- Para pruebas con cuotas futuras, puede ser útil ajustar fechas de planes o usar datos de prueba.
