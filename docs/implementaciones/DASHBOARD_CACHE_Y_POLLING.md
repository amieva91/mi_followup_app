# Dashboard: caché HIST/NOW y polling

## Resumen

- **HIST**: serie mensual guardada en caché; solo se recalcula entera si invalidas el caché (p. ej. operación con fecha **pasada**).
- **NOW**: patrimonio actual, desglose, widgets; se recalcula con `recompute_current_from_cache` cuando la operación afecta solo **hoy** o el **mes actual** (bancos).
- El **último punto** de `history` se sustituye por los valores del breakdown actual para alinear gráfica y cabecera.

## Reinicio y recarga

| Cambio | Qué hacer |
|--------|-----------|
| Código Python (`app/services/…`, rutas) | **Reiniciar** el servidor Flask / Gunicorn / `flask run`. Sin reinicio, el proceso sigue con código viejo en memoria. |
| Plantilla `dashboard.html` (JS inline) | **Recarga fuerte** del navegador (Ctrl+F5) o nueva pestaña; el navegador puede cachear HTML. |

## Dónde se recalcula el caché «actual» (NOW)

- **No** en POST de bancos (saldos del **mes en curso**) ni al crear/editar transacción de **hoy**: el guardado es instantáneo y la pestaña no espera al dashboard.
- **Sí** en **`GET /dashboard/state`** (cada ~30 s con la pestaña del dashboard abierta, y ~0,6 s al cargar `/dashboard`): ahí se ejecuta `recompute_current_from_cache` (NOW desde BD + último punto del histórico, sin reconstruir toda la serie).
- **Mes bancario pasado** o **transacción con fecha pasada**: solo se hace **`invalidate`** del caché (rápido); la próxima visita a `/dashboard` regenera el snapshot completo (HIST coherente).

## Polling `/dashboard/state`

- Cada ~30 s (y una vez al abrir el dashboard) el servidor **recalcula NOW** y devuelve el snapshot.
- Si **`meta.version`** / **`_cached_at`** cambian respecto a la carga anterior, el cliente llama a `applyDashboardUpdate`.
- Correcciones aplicadas frente a fallos anteriores:
  - Cachés antiguos **sin** `meta.version` ya no bloquean el polling: `get()` rellena `version` al leer y el cliente usa `_cached_at` como respaldo.
  - Eliminado el **reload automático** cuando la versión inicial era `null` (provocaba bucles o sensación de “no pasa nada”).

## Cuándo no verás actualización en vivo

1. **Sin caché** (`has_cache: false`): tras `invalidate` o si el TTL expiró (`DASHBOARD_CACHE_MINUTES`, por defecto **15** en local). El polling **no** puede pintar datos nuevos hasta que vuelvas a abrir `/dashboard` (se regenera el caché).
2. **Misma huella**: si no hubo `recompute` ni `set` tras tu cambio (p. ej. la ruta que usaste solo invalida pero no tocas el dashboard en otra pestaña y no recargas).
3. **Fecha “pasada” vs UTC**: `touch_for_dates` usa **fecha UTC** como “hoy”. Una transacción con fecha local “hoy” pero día distinto en UTC puede clasificarse como pasada → invalidación completa → de nuevo el punto 1 hasta F5.

## Archivos relevantes

- `app/services/dashboard_summary_cache.py` — `get`, `set`, `invalidate`, `touch_for_dates`, `recompute_current_from_cache`
- `app/routes/main_routes.py` — `/dashboard`, `/dashboard/state`
- `app/templates/dashboard.html` — `pollDashboardState`, `applyDashboardUpdate`
- `docs/scripts/update_dashboard_cache.py` — forzar refresh de caché en desarrollo

## TTL

- Variable `DASHBOARD_CACHE_MINUTES` (p. ej. `10080` en deploy para ~1 semana).
- En desarrollo sin `.env`, suele ser **15 minutos**: pasado ese tiempo el caché expira y hace falta recargar `/dashboard`.
