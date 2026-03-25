# Plan de implementación: Polling de precios cada minuto + Top Movers + actualización en vivo

## 1. Respuesta a tu pregunta: ¿Una llamada con varios datos = 1 o N llamadas?

**Respuesta: 1 llamada HTTP = 1 “consumo” de rate limit.**

Yahoo Finance no documenta oficialmente el límite, pero en la práctica:
- Cada petición HTTP (GET a Chart API, quoteSummary, etc.) cuenta como **una** llamada.
- Da igual si esa petición devuelve solo precio o precio + sector + industria + market cap: **sigue siendo 1 llamada**.
- El `price_updater` actual hace a veces 2 llamadas por activo:
  1. Chart API (precio, previous_close) → 1 llamada
  2. quoteSummary (sector, industry, P/E, etc.) → 1 llamada adicional si hay autenticación

Para el polling de fondo, usaremos **solo la Chart API** (1 llamada por activo) para respetar el límite de ~2000/día.

---

## 2. Resumen de la solución

| Componente | Descripción |
|------------|-------------|
| **Background job** | Tarea cada 1 min que actualiza 1 activo por minuto (lista rotativa) |
| **Lista de activos** | Portfolio (todos los usuarios) + Watchlist (no en cartera), sin duplicados |
| **Top Movers** | Sección en el Dashboard con acciones con mayor \|% cambio día\| del usuario |
| **Actualización en vivo** | Cuando un precio cambia, efecto visual (flash) solo en ese activo |
| **Pestañas afectadas** | Dashboard principal, Portfolio, Watchlist; opcional: Crypto, Metales |

---

## 3. Fase 1: Lista de activos unificada

### 3.1 Servicio `PricePollingService`

**Archivo**: `app/services/price_polling_service.py`

```python
# Pseudocódigo
def get_assets_to_poll() -> List[Asset]:
    """
    Devuelve lista única de assets (Stock, ETF, Crypto, Commodity) a actualizar:
    1. Assets con holdings > 0 de CUALQUIER usuario (PortfolioHolding)
    2. Assets en Watchlist de CUALQUIER usuario que NO estén en (1)
    3. Sin duplicados (por asset_id)
    4. Solo assets con yahoo_ticker válido
    5. Excluir delisted
    """
```

**Queries**:
- Holdings: `PortfolioHolding.query.filter(quantity > 0).join(Asset).filter(Asset.asset_type.in_(['Stock','ETF','Crypto','Commodity'])).distinct(Asset.id)`
- Watchlist: `Watchlist.query` con asset_id NOT IN holdings
- Merge y deduplicar por asset_id

### 3.2 Persistencia del índice actual

Guardar en BD o Redis qué activo toca actualizar en el siguiente minuto:

- **Opción A**: Tabla `price_polling_state` (last_asset_index, last_run_at)
- **Opción B**: Redis `price_poll:index` y `price_poll:last_run`

---

## 4. Fase 2: Job de actualización cada minuto

### 4.1 Scheduler

**Opción recomendada**: APScheduler dentro de la app Flask (o script separado con cron).

```python
# En app/__init__.py o run.py (solo si WORKER_PRICE_POLLING=True)
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(price_polling_job, 'interval', minutes=1)
scheduler.start()
```

**Alternativa**: comando `flask price-poll-one` ejecutado por cron cada minuto.

### 4.2 Lógica del job

1. Obtener lista de activos con `get_assets_to_poll()`
2. Si vacía → salir
3. Leer índice actual (ej. último procesado)
4. Siguiente activo: `index = (last_index + 1) % len(assets)`
5. Actualizar solo ese activo con Chart API (sin quoteSummary)
6. Guardar nuevo precio en `Asset`, commit
7. Publicar evento “asset X actualizado” (para UI en vivo)
8. Guardar `last_index` y `last_run_at`

### 4.3 Función de actualización ligera

Nueva función en `PriceUpdater` o módulo aparte:

```python
def update_single_asset_price_only(asset: Asset) -> bool:
    """
    Solo Chart API. Sin autenticación, sin quoteSummary.
    Actualiza: current_price, previous_close, day_change_percent, last_price_update.
    Returns True si OK.
    """
```

---

## 5. Fase 3: Propagación a la UI (actualización en vivo)

### 5.1 Opción A: Extender polling existente

- `/dashboard/state` ya se llama cada ~30 s
- Añadir en la respuesta: `updated_asset_ids: [1, 5, 12]` (IDs actualizados desde la última respuesta)
- El cliente comprueba si alguno de sus activos visibles está en esa lista y aplica el efecto visual

### 5.2 Opción B: Endpoint específico

- `GET /api/price-updates?since=<timestamp>` devuelve `{asset_ids: [...], prices: {1: 150.5, 5: 23.1}}`
- Las pestañas con precios hacen polling a este endpoint cada 30–60 s

### 5.3 Efecto visual

Cuando se detecte que un `asset_id` se actualizó:

- Añadir clase CSS (ej. `price-updated`) al contenedor del activo
- Animación breve (ej. 0.5 s de highlight)
- Quitar la clase tras la animación

```css
.price-updated { animation: price-flash 0.5s ease-out; }
@keyframes price-flash { ... }
```

### 5.4 Pestañas a modificar

| Pestaña | Dónde mostrar el efecto |
|---------|-------------------------|
| Dashboard | Donut/distribución si aplica; Top Movers (nuevo) |
| Portfolio Dashboard | Tabla de holdings (celda de precio/P&L del activo) |
| Watchlist | Precio actual de cada ítem |
| Crypto / Metales | Si muestran precios por activo, igual |

---

## 6. Fase 4: Top Movers en el Dashboard

### 6.1 Ubicación

Zona derecha del banner del header (área marcada en rojo en el mockup).

### 6.2 Condiciones

- Solo si el usuario tiene **acciones (Stock)** en cartera
- Mostrar hasta N activos (ej. 5–8) con mayor `|day_change_percent|`
- Orden: descendente por valor absoluto del cambio

### 6.3 Fuente de datos

- Assets del usuario con `asset_type in ('Stock','ETF')` y `quantity > 0` en portfolio
- Usar `day_change_percent` de `Asset` (ya lo rellena el price updater)
- Filtrar `day_change_percent is not None`

### 6.4 Diseño propuesto

```
┌─────────────────────────────────────────┐
│ Top Movers (día)                        │
├─────────────────────────────────────────┤
│ AAPL    +2.3%  ████████                 │
│ MSFT    -1.8%  ██████                   │
│ GRF     +1.5%  █████                    │
│ ...                                     │
└─────────────────────────────────────────┘
```

- Si no hay acciones o no hay datos de cambio: no mostrar el bloque (como ahora).

### 6.5 Integración en el Dashboard

- `get_dashboard_summary` o `DashboardSummaryCacheService` deben incluir `top_movers`
- Estructura: `[{symbol, name, day_change_percent, current_price}, ...]`
- El template del dashboard renderiza esta sección solo si `top_movers` tiene datos

---

## 7. Orden de implementación sugerido

| # | Tarea | Dependencias |
|---|-------|--------------|
| 1 | `PricePollingService.get_assets_to_poll()` | — |
| 2 | `update_single_asset_price_only()` (Chart API solo) | — |
| 3 | Modelo/estado para índice (tabla o Redis) | 1 |
| 4 | Job cada minuto (APScheduler o cron) | 1, 2, 3 |
| 5 | Top Movers: datos en summary + bloque en template | — |
| 6 | Incluir `updated_asset_ids` en `/dashboard/state` (o endpoint nuevo) | 4 |
| 7 | Lógica JS para efecto visual en pestañas | 6 |
| 8 | Propagación a Portfolio, Watchlist, etc. | 6, 7 |

---

## 8. Consideraciones técnicas

### 8.1 Límite de 2000 llamadas/día

- 1 llamada/minuto ≈ 1440 llamadas/día
- Por debajo de 2000 si el job corre cada minuto
- Con varios workers, asegurar que solo uno ejecute el job (ej. lock en BD o Redis)

### 8.2 Lista muy larga

Si hay > 1440 activos, en un día no se recorren todos. Opciones:
- Priorizar activos con holdings recientes o mayor valor
- O asumir que es un caso raro al inicio

### 8.3 Múltiples instancias (producción)

- Usar lock distribuido (Redis, advisory lock en PostgreSQL)
- O ejecutar el job en un único worker dedicado

### 8.4 Crypto y Commodity

- Mismo flujo que acciones: `yahoo_ticker` y Chart API
- Ej. Bitcoin: `BTC-EUR` o `BTC-USD`; oro: `GC=F` (futuros)

---

## 9. Archivos a crear/modificar

| Archivo | Acción |
|---------|--------|
| `app/services/price_polling_service.py` | Crear |
| `app/services/price_updater.py` | Añadir `update_single_asset_price_only()` |
| `app/models/price_polling_state.py` | Crear (opcional) |
| `app/__init__.py` o `run.py` | Iniciar scheduler |
| `app/services/dashboard_summary_cache.py` | Incluir top_movers y updated_asset_ids |
| `app/services/net_worth_service.py` | Helper para top_movers si hace falta |
| `app/templates/dashboard.html` | Bloque Top Movers + JS efecto visual |
| `app/templates/portfolio/dashboard.html` | Efecto visual en holdings |
| `app/templates/portfolio/watchlist.html` | Efecto visual en precios |
| `app/static/js/dashboard.js` o inline | Lógica de flash en activos actualizados |
| `requirements.txt` | APScheduler (si se usa) |

---

## 10. Pruebas recomendadas

1. Lista de activos correcta (portfolio + watchlist, sin duplicados)
2. Rotación correcta del índice (vuelta al inicio)
3. Respeto del límite (1 activo/minuto)
4. Top Movers solo con stocks y solo si hay datos
5. Efecto visual solo en el activo que cambió
6. Comportamiento con 0 activos, 1 activo y lista grande
