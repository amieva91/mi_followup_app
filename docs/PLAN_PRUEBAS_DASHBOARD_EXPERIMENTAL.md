# Plan de Pruebas - Dashboard Experimental

## Objetivo
Validar end-to-end todos los cambios definidos para el rediseño global de `/dashboard` en `ui/dashboard-layout-experiments`, incluyendo UI, reglas de visibilidad, persistencia de orden, recomendaciones, y cache/polling.

## Alcance funcional
- Vista `GET /dashboard`.
- Endpoint `POST /debts/limit`.
- Endpoint layout `GET/POST /dashboard/layout`.
- Integracion de modulos: finanzas, deudas, portfolio, crypto, metales, inmuebles.
- Polling de dashboard (`meta.version`, `meta._now_cached_at`).

## Datos de prueba minimos
- Usuario A: con datos completos (ingresos, gastos, deudas, activos, salud financiera).
- Usuario B: usuario nuevo con pocos o ningun dato.
- Usuario C: datos parciales (solo algunos modulos) para validar visibilidad condicional.

## Checklist manual completo

### 1) Cabecera y score salud financiera
- [ ] Abrir `/dashboard` con datos de salud.
- [ ] Confirmar que el score de salud aparece en el grid izquierdo, en la misma linea del importe de patrimonio neto total.
- [ ] Verificar que no aparece duplicado en otra zona de cabecera.
- [ ] Confirmar cabecera en una sola linea en desktop y sin solapes en mobile/tablet.

### 2) Salud financiera (card + modales)
- [ ] Confirmar que en la card de salud NO aparece el score global.
- [ ] Confirmar que los indicadores son clicables.
- [ ] Verificar que cada click abre modal sin botones de confirmar.
- [ ] Verificar cierre del modal con click fuera y con tecla `Esc`.
- [ ] Validar que `emergency_fund` y `savings_rate` muestran en modal el detalle ampliado esperado.
- [ ] Verificar que no se muestra el texto "Pulsa en un indicador para ver detalle".

### 3) Recomendaciones personalizadas
- [ ] Confirmar que se muestran recomendaciones solo para modulos con registros.
- [ ] Verificar integracion de alertas de salud dentro de recomendaciones.
- [ ] Validar que no hay duplicados evidentes entre recomendaciones equivalentes.
- [ ] Comprobar prioridades/estilos (high/medium/low) correctos.

### 4) Tarjeta Activos (version final)
- [ ] Confirmar que `Activos` es tarjeta simple (no wide), solo con rosco + leyenda.
- [ ] Verificar que el rosco mantiene tooltip/hover.
- [ ] Verificar que la leyenda muestra solo categorias con valor > 0.
- [ ] Validar que no aparece el bloque de detalle por activo (cash/portfolio/crypto/metales/inmuebles) dentro de esta tarjeta.

### 5) Deudas: card wide + mini chart + limite
- [ ] Con deudas activas, verificar bloque izquierdo (totales + top proximos vencimientos).
- [ ] Verificar mini chart de 6 barras (-2, -1, actual, +1, +2, +3) y linea de limite.
- [ ] Confirmar escala Y progresiva y legible (sin ticks repetidos absurdos).
- [ ] Validar color y valor del margen segun positivo/negativo.
- [ ] Sin deudas: confirmar que la tarjeta no aparece.

### 6) Cambio de limite de endeudamiento (rendimiento + consistencia)
- [ ] Cambiar limite varias veces (ej. 35 -> 40 -> 30).
- [ ] Medir respuesta percibida (objetivo: rapida, sin bloqueos largos).
- [ ] Verificar actualizacion de `max_monthly_debt`, `max_yearly_debt`, `margin`, y linea de limite.
- [ ] Confirmar que no hay recompute pesado del dashboard en ese POST.

### 7) Cache y polling
- [ ] Con dashboard abierto en pestana 1, cambiar limite en pestana 2.
- [ ] Confirmar que la pestana 1 se actualiza por polling (cambio de `meta.version`/`_now_cached_at`).
- [ ] Validar que historicos no se recalculan indebidamente por cambiar el limite.
- [ ] Hacer F5 y comprobar coherencia de datos con los modulos origen.

### 8) Persistencia de orden de tarjetas (multi-dispositivo)
- [ ] Reordenar tarjetas por drag&drop y recargar: se mantiene orden.
- [ ] Cerrar sesion y volver a entrar: se mantiene orden.
- [ ] Abrir con otro navegador/dispositivo del mismo usuario: se replica orden.
- [ ] Verificar que una tarjeta nueva se inserta al final de su lane por defecto sin romper orden previo.

### 9) Visibilidad condicional y empty states
- [ ] Usuario con datos parciales: solo aparecen tarjetas de modulos con datos.
- [ ] Usuario nuevo: aparece empty state guiado (no dashboard vacio).
- [ ] Confirmar que no se renderizan tarjetas vacias.

### 10) Ingresos/Gastos por categoria
- [ ] Verificar card de medias por categoria en dos columnas (gastos vs ingresos).
- [ ] Validar comportamiento cuando solo una columna tiene datos.

### 11) FAB de acciones rapidas
- [ ] Verificar boton flotante abajo izquierda.
- [ ] Confirmar alternancia `+` / `x` y despliegue de opciones.
- [ ] Validar navegacion de cada accion y cierre al pulsar fuera.

### 12) Regresion rapida transversal
- [ ] Crear/editar/eliminar una deuda y validar actualizacion dashboard.
- [ ] Revisar consola browser: sin errores JS nuevos en `/dashboard`.
- [ ] Revisar que charts existentes (evolucion, ingresos/gastos, proyeccion) siguen operativos.

## Criterios de aceptacion
- Comportamiento visual y funcional acorde al rediseño acordado.
- Sin regresiones de cache/polling ni datos stale persistentes.
- Cambio de limite de deuda rapido y consistente.
- Orden de tarjetas persistente en sesion y multi-dispositivo.

## Notas tecnicas (cache limite deuda)
- `POST /debts/limit` modifica solo `debt_details.limit_info` del cache del usuario cuando existe.
- Se actualiza `meta.version` y `meta._now_cached_at` para notificar polling.
- No fuerza invalidate/recompute completo en ese endpoint.
- Si no existe cache, no lo construye en caliente; se genera en carga normal del dashboard.
