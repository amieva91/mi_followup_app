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

- Con caché de benchmarks **sin** `dirty_now`, si `benchmark_global_quote.updated_at` supera `meta.benchmark_quotes_applied_at`, se fusiona la cotización global en `benchmark_data_daily` y se ejecuta `_recompute_now` (sin Yahoo) cuando el precio difiere; el gráfico y `meta.version` se refrescan al abrir la página o en el poll del navegador (cada 6 h; ver `BENCHMARK_CHART_POLL_INTERVAL_MS` en `charts.js`).
- Si la fusión no cambia números (ya alineados con Yahoo), solo se actualiza `benchmark_quotes_applied_at` sin subir versión.

## Regresión breve

- Top Movers y flash de precios en dashboard siguen funcionando.
- `flask price-poll-one` no lanza excepción con cola vacía (sin activos y sin benchmarks imposible: siempre hay 5 benchmarks).

---

## Resultados de validación (2026-04-13)

Entorno **desarrollo** (`instance/followup.db`, Flask `development`) salvo donde se indica **producción**.

| Caso | Resultado | Notas |
|------|-----------|--------|
| **1. Migración** | OK | `flask db current` → `j5f6g7h8k9l0 (head)` en dev y en **producción**. Tablas `benchmark_global_quote`, `benchmark_global_daily`, `benchmark_global_state` presentes en SQLite dev. |
| **2. Cola solo benchmarks** | Parcial | En esta BD hay cartera: cola **52 activos + 5 benchmarks = 57** slots. No se vació la BD; el camino benchmark se valida en prod (ver abajo) y con `_poll_benchmark_slot` al restaurar quotes. |
| **3. Cola mixta** | Parcial | 7× `price-poll-one` seguidos → solo `asset_id` (esperable: hace falta ~57 min para una vuelta completa). **Producción:** log muestra alternancia `asset` y `benchmark` (`OK: actualizado benchmark S&P 500`). |
| **4. Dashboard índices** | OK | `get_market_indices_snapshot(1)`: **5/5 con % día** con quotes cargados. Tras **vaciar** `benchmark_global_quote` (solo dev): **5/5 con %** vía fallback `benchmark_global_daily` + penúltimo/último cierre. Quotes **restaurados** con5× `_poll_benchmark_slot`. |
| **5. Precio acción / benchmarks** | OK (código + meta) | `PortfolioBenchmarksCacheService.touch_for_prices_update(1)`: fila cache **misma id=1**, `meta.dirty_now=True`. Código: `touch_for_prices_update` en benchmarks, no `invalidate` en `_invalidate_caches_for_asset`. |
| **6. Producción** | OK | `flask db current` = head. `price_poll_cron.log`: **25** líneas con `benchmark`; ejemplo reciente actualización S&P 500. `benchmark_global_daily_cron.log`: ejecución OK (versión global). |
| **Refactor global HIST** | OK | 5 filas `benchmark_global_daily`, `daily_data_version=1` en dev. Segunda ejecución `benchmark-global-daily-once` → **sin cambios** (~0.1s). |
| **Fase 2 (fusión quotes)** | No medido en UI | Comportamiento cubierto por código en `get_comparison_state`; validación fina con F5 o poll del cliente (6 h) y trazas opcional. |
| **Regresión** | OK | `get_comparison_state(1)` sin excepción; `meta.version` presente. `py_compile` del fix de indentación ya en `main`. |

**Incidencia previa:** `IndentationError` en `_meta_defaults` en prod → corregido en commit `e80a8d1`; tras despliegue, index-comparison y `/dashboard/state` operativos.
