# Plan de pruebas – Módulo Bancos + Ajustes + Stock Market

**Fecha creación**: Febrero 2026  
**Estado**: En progreso  
**Marcar con `[x]` cada prueba al confirmarla**

---

## Precondiciones

- [ ] Usuario logueado en la aplicación
- [ ] Cuenta(s) de broker IBKR/DeGiro con transacciones DEPOSIT y WITHDRAWAL

---

## 1. Módulo Bancos (Fase 1)

| # | Prueba | Pasos | Resultado esperado | ✓ |
|---|--------|-------|--------------------|---|
| 1.1 | Acceso pestaña Bancos | Clic en "Bancos" en el navbar (entre Deudas y Portfolio) | Se abre el dashboard de bancos | |
| 1.2 | Crear banco | Clic "Añadir banco" → Nombre (ej. "BBVA") → Guardar | Banco creado y visible en la lista | |
| 1.3 | Editar banco | Editar un banco existente → Cambiar nombre/icono → Guardar | Cambios guardados correctamente | |
| 1.4 | Registrar saldos | Seleccionar año/mes → Introducir cantidad por banco → Guardar | Saldos guardados y visibles | |
| 1.5 | Gráfico evolución | Ir a Bancos con varios meses con saldos | Gráfico de barras muestra evolución mensual | |
| 1.6 | Eliminar banco sin saldos | Eliminar banco que no tiene saldos | Banco eliminado correctamente | |
| 1.7 | Eliminar banco con saldos | Intentar eliminar banco que tiene saldos | Debe bloquear o advertir (según diseño) | |

---

## 2. Categoría Ajustes (Fase 2)

| # | Prueba | Pasos | Resultado esperado | ✓ |
|---|--------|-------|--------------------|---|
| 2.1 | Ajustes en Income | Ir a Ingresos → Resumen por categoría | Aparece categoría "Ajustes" si hay ajuste negativo | |
| 2.2 | Ajustes en Expenses | Ir a Gastos → Resumen por categoría | Aparece categoría "Ajustes" si hay ajuste positivo | |
| 2.3 | Ajustes no clicable | Clic en categoría "Ajustes" | No es enlace clicable (solo lectura) | |
| 2.4 | Crear categoría Ajustes | Intentar crear categoría "Ajustes" manualmente | Sistema rechaza con mensaje | |
| 2.5 | Editar Ajustes | Intentar editar la categoría Ajustes | Sistema bloquea la edición | |

---

## 3. Stock Market – Income (Fase 4)

| # | Prueba | Pasos | Resultado esperado | ✓ |
|---|--------|-------|--------------------|---|
| 3.1 | Stock Market visible | Ir a Ingresos | Categoría "Stock Market" en resumen por categoría | |
| 3.2 | Total correcto | Comparar total Stock Market con retiradas broker | Coincide con suma de WITHDRAWAL | |
| 3.3 | Verificación en Portfolio | Portfolio → Transacciones → filtrar WITHDRAWAL | Importes coinciden con Stock Market Income | |
| 3.4 | Formato media+total | Revisar texto de Stock Market | Formato `X €/mes (Y €)` | |

---

## 4. Stock Market – Expenses (Fase 4)

| # | Prueba | Pasos | Resultado esperado | ✓ |
|---|--------|-------|--------------------|---|
| 4.1 | Stock Market visible | Ir a Gastos | Categoría "Stock Market" en resumen por categoría | |
| 4.2 | Total correcto | Comparar total Stock Market con depósitos broker | Coincide con suma de DEPOSIT | |
| 4.3 | Verificación en Portfolio | Portfolio → Transacciones → filtrar DEPOSIT | Importes coinciden con Stock Market Expenses | |
| 4.4 | Formato media+total | Revisar Stock Market en Gastos | Formato `X €/mes (Y €)` | |

---

## 5. Formato media + total (Fase 5)

| # | Prueba | Pasos | Resultado esperado | ✓ |
|---|--------|-------|--------------------|---|
| 5.1 | Todas categorías Income | Ir a Ingresos | Todas las categorías muestran `media €/mes (total €)` | |
| 5.2 | Categorías padre Expenses | Ir a Gastos | Categorías padre muestran formato correcto | |
| 5.3 | Subcategorías Expenses | Gastos con subcategorías | Subcategorías muestran formato `media €/mes (total €)` | |

---

## 6. Cuadros de resumen (Fase 6)

| # | Prueba | Pasos | Resultado esperado | ✓ |
|---|--------|-------|--------------------|---|
| 6.1 | Cards en Income | Ir a Ingresos | 5 cards: Media mensual, Total período, Mes máx, Meses con datos, Tendencia | |
| 6.2 | Valores coherentes Income | Revisar valores de las cards | Coinciden con gráfico y resumen por categoría | |
| 6.3 | Cards en Expenses | Ir a Gastos | 5 cards similares visibles | |
| 6.4 | Tendencia | Comprobar icono de tendencia | ↑, ↓ o ≈ según último mes vs media | |
| 6.5 | Meses con datos | Revisar "Meses con datos" | Número entre 0 y 12 | |

---

## 7. Reconciliación (Fases 2 y 3)

| # | Prueba | Pasos | Resultado esperado | ✓ |
|---|--------|-------|--------------------|---|
| 7.1 | Cálculo ajuste | Tener saldos en Bancos en dos meses consecutivos | Ajuste se calcula cuando hay diferencia | |
| 7.2 | Ajuste en totales | Revisar totales mensuales en Income/Expenses | Totales incluyen ajuste calculado | |
| 7.3 | Gráficos | Ver gráficos de barras por mes | Reflejan ajuste y Stock Market correctamente | |

---

## 8. Integración y navegación

| # | Prueba | Pasos | Resultado esperado | ✓ |
|---|--------|-------|--------------------|---|
| 8.1 | Navbar | Revisar menú principal | "Bancos" visible entre Deudas y Portfolio | |
| 8.2 | Enlace categoría Income | Clic en categoría de Income (excepto Ajustes) | Filtra la lista por esa categoría | |
| 8.3 | Enlace categoría Expenses | Clic en categoría de Expenses (excepto Ajustes) | Filtra la lista por esa categoría | |

---

## 9. Casos límite

| # | Prueba | Pasos | Resultado esperado | ✓ |
|---|--------|-------|--------------------|---|
| 9.1 | Sin saldos bancarios | Bancos sin saldos en ningún mes | No aparece Ajustes o muestra 0 | |
| 9.2 | Sin transacciones broker | Sin cuentas IBKR/DeGiro o sin WITHDRAWAL/DEPOSIT | No aparece Stock Market | |
| 9.3 | Usuario nuevo | Usuario sin ingresos ni gastos | Páginas cargan sin error, valores vacíos/0 | |
| 9.4 | Meses sin datos | Usuario con pocos meses de actividad | "Meses con datos" muestra valor correcto (< 12) | |

---

## Resumen de progreso

| Sección | Completadas | Total |
|---------|-------------|-------|
| 1. Bancos | 0 | 7 |
| 2. Ajustes | 0 | 5 |
| 3. Stock Market Income | 0 | 4 |
| 4. Stock Market Expenses | 0 | 4 |
| 5. Formato media+total | 0 | 3 |
| 6. Cuadros resumen | 0 | 5 |
| 7. Reconciliación | 0 | 3 |
| 8. Integración | 0 | 3 |
| 9. Casos límite | 0 | 4 |
| **TOTAL** | **0** | **38** |

---

## Notas

_Añadir aquí cualquier observación durante las pruebas:_

---

*Documento para ir marcando las pruebas confirmadas. Sustituir el espacio en la columna ✓ por [x] al completar cada una.*
