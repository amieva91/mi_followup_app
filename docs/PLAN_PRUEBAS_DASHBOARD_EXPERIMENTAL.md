# Plan de Pruebas - Dashboard Experimental

## Objetivo
Validar que los cambios visuales y de rendimiento del dashboard en `ui/dashboard-layout-experiments` funcionan sin regresiones, incluyendo:
- Nuevo layout del bloque `Activos` (lista con detalle por tipo de activo).
- Reubicacion del score de salud financiera en cabecera (bloque izquierdo).
- Rendimiento y consistencia al cambiar `limite de endeudamiento`.

## Alcance funcional
- Vista `/dashboard`.
- Endpoint `POST /debts/limit`.
- Polling de dashboard (`meta.version` / `_now_cached_at`).
- Tarjeta `Activos` y cabecera principal.

## Checklist manual

### 1) Cabecera y score de salud
- [ ] Abrir `/dashboard` con datos de salud financiera.
- [ ] Confirmar que el score de salud aparece en el bloque izquierdo, debajo del patrimonio neto total.
- [ ] Verificar que no aparece duplicado en otros bloques de cabecera.
- [ ] Confirmar que en desktop la cabecera se mantiene en una sola linea visual.

### 2) Tarjeta Activos (detalle en lista)
- [ ] Confirmar que rosco y leyenda siguen igual (sin cambios de interaccion).
- [ ] Verificar que el bloque derecho muestra una lista compacta por activo (Cash, Portfolio, Crypto, Metales, Inmuebles).
- [ ] Validar que cada fila mantiene su enlace al modulo correspondiente.
- [ ] Revisar que importes y subtotales coinciden con el detalle del modulo origen.
- [ ] Comprobar que tipos sin datos no se muestran.

### 3) Limite de endeudamiento (rendimiento)
- [ ] Ir a deudas y cambiar el limite (por ejemplo 35% -> 40% -> 30%).
- [ ] Medir tiempo de respuesta percibido (objetivo: inmediato, sin espera larga).
- [ ] Confirmar que se actualizan los valores derivados:
  - `max_monthly_debt`
  - `max_yearly_debt`
  - `margin`
  - linea de limite en el mini grafico
- [ ] Confirmar que no se recalcula todo el dashboard en ese POST (sin bloqueo largo).

### 4) Consistencia de cache/polling
- [ ] Con dashboard abierto en una pestana, cambiar el limite en otra pestana.
- [ ] Verificar que la pestana abierta refleja el cambio via polling (version NOW actualizada).
- [ ] Confirmar que historicos/series no cambian por este ajuste de limite.
- [ ] Hacer F5 y comprobar que los datos siguen consistentes con los modulos origen.

### 5) Pruebas de no regresion rapidas
- [ ] Crear/editar/eliminar una deuda y confirmar que el dashboard sigue actualizando valores.
- [ ] Revisar tarjetas de ingresos/gastos y recomendaciones para confirmar que no hay efectos colaterales.
- [ ] Revisar consola del navegador (sin errores JS nuevos en `/dashboard`).

## Criterios de aceptacion
- Cambios visuales aplicados segun diseno esperado.
- Cambio de limite sin latencia alta.
- Sin datos stale persistentes tras polling y F5.
- Sin regresiones funcionales en deudas ni en tarjetas relacionadas.

## Notas tecnicas de seguridad del cambio en cache
- `POST /debts/limit` solo modifica `debt_details.limit_info` dentro del cache del usuario.
- Se actualiza `meta.version` y `meta._now_cached_at` para que polling detecte el cambio.
- No invalida ni recalcula bloques historicos, reduciendo coste y riesgo de bloqueo.
- Si no existe cache, no fuerza rebuild en el POST; se reconstruye en carga normal del dashboard.
