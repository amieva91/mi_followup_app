# Plan de pruebas – Polling de precios, Top Movers y efecto flash

Documentación: **[`docs/PLAN_POLLING_PRECIOS_TOP_MOVERS.md`](PLAN_POLLING_PRECIOS_TOP_MOVERS.md)**

## Resumen de lo implementado

| Componente | Estado |
|------------|--------|
| `PricePollingService.get_assets_to_poll()` | ✅ |
| `update_single_asset_price_only()` (Chart API solo) | ✅ |
| Tabla `price_polling_state` + job `flask price-poll-one` | ✅ |
| Top Movers en dashboard principal | ✅ |
| `updated_asset_ids` en `/dashboard/state` | ✅ |
| Endpoint `/api/price-updates` | ✅ |
| Efecto flash: Dashboard, Portfolio, Holdings, Watchlist, Crypto, Metales | ✅ |

## Pre-requisitos

1. **Cron** (producción o desarrollo): instalar la entrada con el repo en el servidor:
   ```bash
   ./scripts/install_price_poll_cron.sh              # producción (FLASK_ENV=production)
   ./scripts/install_price_poll_cron.sh --dev        # desarrollo local
   ```
   Equivale a una línea `* * * * *` que ejecuta `venv/bin/flask price-poll-one` con log en `logs/price_poll_cron.log`. Ver comentarios en el script.
2. **Desarrollo**: ejecutar manualmente cuando quieras simular el job:
   ```bash
   flask price-poll-one
   ```
3. Migración aplicada: `flask db upgrade` (tabla `price_polling_state`)

- [x] **Migración head** (`flask db current`): `g2b3c4d5e6f7` — verificado por CLI.

---

## Leyenda

- [ ] Pendiente
- [x] Completada

---

## A. Verificado por CLI (sesión asistente)

| Comando / comprobación | Resultado |
|------------------------|-----------|
| `flask db current` | Head `g2b3c4d5e6f7` |
| `flask price-poll-one` (1ª vez) | `OK: actualizado asset_id=10` |
| `flask price-poll-one` (2ª vez) | `OK: actualizado asset_id=12` (rotación distinta) |
| `get_assets_to_poll()` | 50 activos con ticker (ej. ids 1, 8, 10, 12, 15) |
| `price_polling_state` id=1 | `last_asset_index`, `last_run_at`, `last_updated_asset_id` actualizados |
| `get_updated_asset_ids_for_user` (últimos 5 min, user 1) | Incluyó `[10]` tras actualización |

**Nota:** Los casos sin holdings/watchlist (lista vacía) están cubiertos por revisión de código (`get_assets_to_poll` → `[]`, `run_poll_one` → `None`, mensaje CLI). Una prueba manual con BD sin posiciones sigue siendo opcional.

---

## 1. Job de polling

### 1.1 Lista de activos

- [x] Ejecutar `flask price-poll-one` con al menos 1 holding o 1 watchlist.
- [x] Verificar salida: `OK: actualizado asset_id=X` o `OK: sin activos o sin actualización`.
- [x] Sin holdings ni watchlist: salida `OK: sin activos...` sin error. *(verificado código: `get_assets_to_poll()` devuelve `[]` si no hay IDs; `run_poll_one()` → `None`; CLI imprime la línea OK. Prueba manual con BD vacía opcional.)*

### 1.2 Rotación del índice

- [x] Ejecutar `flask price-poll-one` varias veces (ej. 5) con 3+ activos en cartera.
- [x] Verificar que cada ejecución actualiza un asset distinto (o que rota correctamente).
- [x] Comprobar en BD: `SELECT * FROM price_polling_state` — `last_asset_index` y `last_run_at` cambian.

### 1.3 Límite 1 activo/minuto

- [x] Una sola ejecución del comando → 1 llamada a Yahoo Chart API (implícito: 1 `OK: actualizado asset_id=` por ejecución).
- [x] No debe hacer 2+ llamadas por ejecución. *(verificado código: `update_single_asset_price_only` hace una sola `requests.get` al chart de Yahoo por intento; si falla no reintenta en bucle.)*

### 1.4 Casos borde

- [x] 0 activos: salida correcta, sin crash. *(misma rama que sin holdings/watchlist o lista filtrada vacía → `run_poll_one` no llama al updater.)*
- [x] 1 activo: funciona y rota (siguiente ejecución mismo activo). *(índice `(last+1) % len`; con `len==1` siempre el mismo asset, sin error.)*
- [x] Activo sin `yahoo_ticker`: no debe bloquear; se omite o falla controladamente. *(excluido en `get_assets_to_poll`; no entra en la cola. Si estuviera en cola, `update_single_asset_price_only` devuelve `False` sin excepción.)*

---

## 2. Top Movers (Dashboard principal)

### 2.1 Con acciones en cartera

- [x] Usuario con Stock/ETF en portfolio y `day_change_percent` en Asset.
- [x] Cargar `/dashboard`.
- [x] Bloque "Top Movers (día)" visible a la derecha del header (patrimonio).
- [x] Muestra hasta 6 activos ordenados por mayor |% cambio día|.
- [x] Formato: símbolo + % con color (verde sube, rojo baja). *(revisado usuario)*

### 2.2 Sin acciones o sin day_change

- [x] Usuario sin Stock/ETF en cartera: bloque no aparece.
- [x] Usuario con acciones pero sin `day_change_percent`: bloque no aparece o vacío. *(revisado usuario)*

---

## 3. Efecto flash – Dashboard principal

### 3.1 Polling /dashboard/state

- [x] Abrir `/dashboard`, mantener pestaña abierta.
- [x] En otra terminal: `flask price-flash-test --index 0` (fuerza update del primer Top Mover).
- [x] Esperar ≤30 s (ciclo de polling).
- [x] La fila del activo actualizado en Top Movers debe hacer flash verde breve. *(revisado usuario)*
- [x] "Actualizado hace X min" debe actualizarse.

### 3.2 Parámetro `since`

- [x] DevTools → Network: peticiones a `/dashboard/state`.
- [x] Tras la primera respuesta, la siguiente incluye `?since=...` (timestamp ISO).
- [x] Respuesta incluye `updated_asset_ids` (array, puede estar vacío). *(revisado usuario)*

---

## 4. Efecto flash – Portfolio, Holdings, Watchlist, Crypto, Metales

### 4.1 Portfolio (Mi Portfolio)

- [x] Abrir `/portfolio/` (dashboard de portfolio).
- [x] Ejecutar `flask price-simulate-change --bump 0.01 --scope all` (o `price-poll-one` / `price-flash-test` según prueba).
- [x] Esperar ≤30 s.
- [x] Celda de Precio, Valor o P&L: flash + **valores repintados sin F5** (`/api/price-updates?view=portfolio`). *(revisado usuario; flash estable tras fix JS/WAAPI + un fetch en vuelo)*

### 4.2 Cartera (Holdings)

- [x] Abrir `/portfolio/holdings`.
- [x] Mismo flujo: `flask price-simulate-change --bump 0.01 --scope all` → flash + repintado en ≤30 s en Precio/Valor/P&L (`view=holdings`). *(revisado usuario; flash estable tras fix JS)*

### 4.3 Watchlist

- [x] Abrir `/portfolio/watchlist` con activos en seguimiento.
- [x] Job actualiza un activo de la watchlist → flash en columna "Precio actual". *(revisado usuario; flash verde no persistente tras fix JS/WAAPI)*

### 4.4 Crypto

- [x] Abrir `/crypto/` con posiciones.
- [x] Job actualiza un activo crypto (BTC, ETH, etc.) → flash en Precio, Valor, P&L. *(revisado usuario)*

### 4.5 Metales

- [x] Abrir `/metales/` con posiciones.
- [x] Job actualiza un metal (GC=F, etc.) → flash en Precio actual, Valor, P&L. *(revisado usuario)*

### 4.6 Endpoint /api/price-updates

- [x] Con sesión activa: `GET /api/price-updates` → JSON con `updated_asset_ids`, `server_now`.
- [x] Sin `since`: `updated_asset_ids` vacío (evita flash al cargar).
- [x] Con `since` (timestamp anterior a una actualización): devuelve IDs de activos actualizados. *(revisado usuario)*

---

## 5. Invalidación de caches

### 5.1 Evolution y Benchmarks

- [x] Tras `flask price-poll-one` que actualice un activo tuyo:
  - Cache de evolution/benchmarks se invalida para tu usuario.
  - Próximo poll en Performance / Index comparison recalculará si aplica.  
  *(Verificado código: `_invalidate_caches_for_asset` → `PortfolioEvolutionCacheService.invalidate` y `PortfolioBenchmarksCacheService.invalidate` por cada `user_id` con holding o watchlist en ese asset.)*

### 5.2 Dashboard recompute NOW

- [x] Tras job que actualiza un activo tuyo:
  - Dashboard hace `recompute_current_from_cache` (no rebuild completo).
  - Patrimonio y Top Movers se actualizan en el siguiente poll de `/dashboard/state`.  
  *(Verificado código: mismo hook llama a `DashboardSummaryCacheService.recompute_current_from_cache(uid)`.)*

---

## 6. Resumen rápido (sanity check)

1. `flask price-poll-one` → OK, actualiza 1 activo.
2. Dashboard principal → Top Movers visible si hay acciones con day_change.
3. Mantener Portfolio/Holdings/Watchlist/Crypto/Metales abiertos → ejecutar job → flash en ≤30 s.
4. Sin activos: job no falla; sin datos: Top Movers no se muestra.

---

## 7. Notas de depuración

- **No hay flash:** ¿El job actualizó un activo que está en la vista? ¿El polling está activo? Revisar Network para `/dashboard/state` o `/api/price-updates`.
- **Top Movers vacío:** ¿Hay Stock/ETF en cartera? ¿Tienen `day_change_percent`? Ejecutar "Actualizar precios" manual una vez.
- **Cron no corre:** Verificar crontab (`crontab -l`) y logs del sistema.
- **Varios workers:** En producción, solo un proceso debe ejecutar el job (evitar duplicados). Opción: lock en BD o worker dedicado.
