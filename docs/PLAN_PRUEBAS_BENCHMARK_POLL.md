# Plan de pruebas: cola de precios con índices + `benchmark_global_quote`

**Alcance:** migración `i4e5f6g7h8j9`, `price-poll-one` (activos + benchmarks), `get_market_indices_snapshot`, invalidación `touch_for_prices_update` en benchmarks al actualizar un activo.

## Pre-requisitos

- `flask db upgrade` aplicado (tabla `benchmark_global_quote`).
- Cron `price-poll-one` activo (1 tick/minuto).

## Casos

1. **Migración**
   - Tras `upgrade`, existe tabla `benchmark_global_quote` vacía; `downgrade` opcional solo en entorno de prueba.

2. **Cola con solo benchmarks**
   - Usuario/BD sin holdings ni watchlist con tickers válidos: ejecutar `flask price-poll-one` varias veces; al menos una ejecución debe loguear `OK: actualizado benchmark …` y aparecer filas en `benchmark_global_quote` (5 índices tras varios minutos de rotación).

3. **Cola mixta**
   - Con cartera activa: la cola es `activos ordenados por id` + benchmarks; verificar en logs alternancia entre `asset_id` y `benchmark` a lo largo de `len(activos)+5` minutos.

4. **Dashboard “Índices (día)”**
   - Sin abrir antes Index comparison: con cotizaciones globales rellenas, `/dashboard` debe mostrar % y no “—” (tras poll de dashboard ~30 s o F5).
   - Tras vaciar tabla `benchmark_global_quote`, si existe `portfolio_benchmarks_cache` con `benchmark_data_daily`, debe hacer fallback a penúltimo/último cierre diario.

5. **Actualización de precio de acción**
   - Tras un tick que actualiza un holding: `portfolio_benchmarks_cache` del usuario **no** debe borrarse (sigue existiendo fila); `meta.dirty_now` puede quedar en true. Comprobar que Index comparison no fuerza full rebuild solo por ese tick (salvo otros flags).

6. **Producción / despliegue**
   - Tras `git pull`, ejecutar `flask db upgrade` como usuario de la app antes o junto al reinicio de Gunicorn.
   - Revisar `logs/price_poll_cron.log` para líneas `benchmark`.

## Refactor global HIST (`benchmark_global_daily`)

- Migración `j5f6g7h8k9l0`: tablas `benchmark_global_daily`, `benchmark_global_state`.
- `flask benchmark-global-daily-once`: rellena/actualiza series; sube `daily_data_version` solo si hubo cambios Yahoo.
- Tras deploy: comprobar `logs/benchmark_global_daily_cron.log` y que `daily_data_version` aumenta al cambiar de día (o forzar con segundo `--` no existe; usar código `force` solo en desarrollo si se añade flag).
- Varios usuarios: mismas filas globales; cada uno recibe comparación distinta al recortar por `start_date`.

## Fase 2 (Index comparison / `get_comparison_state`)

- Con caché de benchmarks **sin** `dirty_now`, si `benchmark_global_quote.updated_at` supera `meta.benchmark_quotes_applied_at`, se fusiona la cotización global en `benchmark_data_daily` y se ejecuta `_recompute_now` (sin Yahoo) cuando el precio difiere; el gráfico y `meta.version` deben actualizarse en el poll del cliente.
- Si la fusión no cambia números (ya alineados con Yahoo), solo se actualiza `benchmark_quotes_applied_at` sin subir versión.

## Regresión breve

- Top Movers y flash de precios en dashboard siguen funcionando.
- `flask price-poll-one` no lanza excepción con cola vacía (sin activos y sin benchmarks imposible: siempre hay 5 benchmarks).
