# Plan de pruebas — Planificación de gastos

Usar en [followup.fit](https://followup.fit/) (rama experimental) o entorno local. Ir marcando cada escenario. Objetivo: validar UI (modales, mensajes) y el comportamiento del planificador (reorganización, DSR, saldo).

## Preparación

1. Iniciar sesión con un usuario que tenga ingresos y categorías de gasto configuradas.
2. Ir a **Planificación de gastos** (`/planificacion`).
3. Anotar: ingreso medio, gastos fijos, efectivo inicial, DSR % configurado.

### Seguimiento (marcado al confirmar cada prueba)

- [ ] Prep
- [x] A1
- [x] A2
- [x] A3
- [x] A4
- [x] A5
- [x] A6
- [x] A7
- [x] B1
- [x] B2
- [x] C1
- [x] C2
- [ ] C3
- [ ] C4
- [ ] C5
- [ ] C6
- [ ] C7
- [ ] D1
- [ ] D2
- [ ] D3
- [ ] E1
- [ ] E2
- [ ] E3
- [ ] E4
- [ ] F1
- [ ] F2
- [ ] G

---

## A. Modales y navegación (UI)

| # | Escenario | Pasos | Resultado esperado |
|---|-----------|--------|-------------------|
| A1 | Eliminar — modal integrado | En la tabla, **Eliminar** en un objetivo | Modal propio (fondo oscuro, tarjeta blanca, título y nombre del objetivo). Sin diálogo nativo del navegador. **Cancelar** cierra sin borrar. |
| A2 | Eliminar — confirmar | En el modal, **Eliminar** | POST correcto, redirect, flash «Objetivo eliminado.», fila desaparece. |
| A3 | Editar genérico — sin salir | **Editar** en objetivo genérico | Modal con formulario; URL sigue siendo `/planificacion` (no `/objetivo/…/editar`). |
| A4 | Editar — cancelar | **Cancelar** | Cierra modal, sin cambios. |
| A5 | Editar — guardar | Cambiar un campo y **Guardar y replanificar** | Flash «Objetivo actualizado y plan replanificado.», tabla y proyección actualizadas. |
| A6 | URL antigua `/planificacion/objetivo/<id>/editar` | Abrir esa URL en navegador (objetivo genérico) | Redirección a `/planificacion?edit_goal=<id>`, modal de edición abierto; la query `edit_goal` se limpia del historial (barra de direcciones sin parámetro). |
| A7 | Hipoteca — editar | **Editar** en fila hipoteca | Navegación al simulador con `?edit=…` (sin modal en índice; comportamiento acordado). |

---

## B. Configuración global

| # | Escenario | Pasos | Resultado esperado |
|---|-----------|--------|-------------------|
| B1 | Guardar DSR y horizonte | Cambiar % DSR y meses de horizonte, **Guardar configuración** | Flash de éxito; tarjetas resumen y tabla de proyección coherentes con el nuevo horizonte (hasta el máximo permitido). |
| B2 | Categorías fijas | Marcar/desmarcar categorías | Media de fijos y proyección cambian de forma razonable; aviso si padre+hijo mal usado. |

---

## C. Añadir objetivos genéricos (algoritmo + mensajes)

| # | Escenario | Pasos | Resultado esperado |
|---|-----------|--------|-------------------|
| C1 | Solo nombre + importe + prioridad | Sin fecha, **N.º cuotas** vacío | Objetivo añadido; planificador asigna modo (único/cuotas) según saldo, DSR y prioridades. |
| C2 | Automático + fecha límite | Fecha futura, cuotas vacías | Intenta cumplir hacia esa fecha si el plan es viable. |
| C3 | Pago único explícito | **N.º cuotas = 1** | Una carga concentrada en un mes (o mensaje de error / aviso si no cabe). |
| C4 | Cuotas + número | **N.º cuotas = N** (≥ 2) | Reparto en N meses (o aviso del planificador). |
| C5 | Cuotas “automáticas” | **N.º cuotas** vacío con objetivo que requiera fraccionar | Mínimo de meses posible según reglas (tooltip / avisos). |
| C6 | Plan inviable | Varios objetivos + poco saldo o DSR muy bajo | Banner rojo «Plan no viable…» con mensaje claro; proyección fallback si aplica. |
| C7 | Avisos no bloqueantes | Configuración límite | Caja ámbar «Avisos del planificador» con lista de textos comprensibles. |

---

## D. Prioridades y reorganización

| # | Escenario | Pasos | Resultado esperado |
|---|-----------|--------|-------------------|
| D1 | Dos genéricos, prioridades 1 y 3 | Añadir A (prio 1), B (prio 3) | El de prioridad 1 recurre antes a capacidad de pago / fechas. |
| D2 | Cambiar prioridad (modal editar) | Editar y subir/bajar prioridad | Tabla reordenada por prioridad; cuotas mensuales y proyección recalculadas. |
| D3 | Genérico + hipoteca | Objetivo genérico y uno hipoteca | Cuota hipoteca cuenta en DSR y efectivo; sin saldo negativo en el modelo. |

---

## E. Edición y borrado (impacto en el plan)

| # | Escenario | Pasos | Resultado esperado |
|---|-----------|--------|-------------------|
| E1 | Reducir importe | Editar modal, bajar importe | Menor carga mensual o menos meses; proyección mejora. |
| E2 | Aumentar importe | Subir importe | Puede empeorar saldo o volver plan inviable → mensaje adecuado. |
| E3 | Quitar fecha límite | Dejar fecha vacía en edición | Planificador ya no fuerza esa fecha. |
| E4 | Borrar objetivo | Eliminar desde modal | Totales «Objetivos / mes» y filas de proyección se actualizan. |

---

## F. Hipoteca (simulador)

| # | Escenario | Pasos | Resultado esperado |
|---|-----------|--------|-------------------|
| F1 | Crear desde simulador | Flujo completo **Añadir** | Objetivo en tabla tipo Hipoteca; proyección con cuotas e ingresos iniciales si aplica. |
| F2 | Editar desde tabla | **Editar** → simulador | Textos de edición; **Guardar** con `update_goal_id`; vuelta al índice con plan actualizado. |

---

## G. Regresión rápida

- Tras cada cambio: recarga dura (F5) y comprueba que no quedan modales abiertos ni CSRF caducado sin mensaje.
- Probar en ventana privada si hay dudas de caché.

---

## Notas

- Los textos exactos de flash pueden variar ligeramente; lo importante es el significado (éxito, error, inviabilidad).
- Si un escenario falla, anotar: usuario, fecha, objetivos (importes/prioridades) y captura del mensaje o de la proyección.
