# Plan de pruebas: integrar ajuste de reconciliación en categoría

Objetivo: validar el botón **Integrar** en filas de ajuste (Gastos / Ingresos) antes de decidir merge o marcha atrás.

## Precondiciones

- Usuario con al menos **dos meses consecutivos** con saldos bancarios cargados.
- **Gastos**: mes con `ajuste > 0` (gasto no registrado) visible en lista.
- **Ingresos**: mes con `ajuste` sintético (ajuste negativo en fórmula → muestra importe positivo en UI).
- Al menos una categoría de gasto y una de ingreso que **no** sean «Ajustes» ni «Stock Market».

## Casos

### G1 — Integrar ajuste de gasto (feliz camino)

1. Ir a **Gastos**, localizar mes con fila ⚖️ Ajustes (importe > 0).
2. Pulsar **Integrar**, elegir categoría, **Confirmar**.
3. **Esperado**: mensaje de éxito; desaparece la fila de ajuste de ese mes (o importe 0); aparece un gasto con descripción «Integrado desde reconciliación bancaria» e importe igual al ajuste.
4. Comprobar **fecha**: si ya había en ese mes un gasto **sin plan de deuda** en esa categoría, la fecha del nuevo gasto coincide con el más reciente de esos; si no, **último día del mes**.

### G2 — Categoría solo con cuotas de deuda

1. Elegir una categoría donde en ese mes **solo** existan gastos con plan de deuda.
2. Integrar el ajuste en esa categoría.
3. **Esperado**: nuevo gasto **sin** `debt_plan_id`, fecha = último día del mes; el ajuste desaparece.

### G3 — Sin categorías elegibles

1. (Solo si en test tenéis un usuario sin categorías filtrables) No debe mostrarse **Integrar**; crear categoría y repetir G1.

### I1 — Integrar ajuste de ingreso

1. Ir a **Ingresos** con mes que muestre ajuste de ingreso no registrado.
2. **Integrar** → categoría → confirmar.
3. **Esperado**: nuevo ingreso con misma descripción fija e importe mostrado en el modal; fila de ajuste de ese mes desaparece.

### I2 — Doble integración / repetir

1. Tras G1 o I1, intentar **Integrar** de nuevo en el mismo mes (si la fila ya no existe, no aplica).
2. Si aún hubiera ajuste residual por redondeo, comprobar mensaje de error coherente; si no hay ajuste, debe fallar con texto del tipo «no hay ajuste… pendiente».

### Seguridad / sesión

- Petición **POST** sin CSRF debe rechazarse (403/400 según configuración).
- `next` solo rutas relativas que empiecen por `/` (no open redirect).

### Regresión

- Botones **Incluir** / **Excluir** métricas del ajuste siguen funcionando en la misma fila.
- Gráficos / resumen tras integrar: sin errores; caché de dashboard se actualiza (cambio visible tras recarga si aplica).

## Marcha atrás

- Revertir commit o `git checkout` a SHA anterior en la VM y `systemctl restart followup.service`.
- Opcional: eliminar manualmente los gastos/ingresos creados con descripción «Integrado desde reconciliación bancaria» en BD de prueba.
