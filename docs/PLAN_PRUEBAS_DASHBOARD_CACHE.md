# Plan de pruebas – Dashboard, cache y actualización en vivo

Documentación de apoyo: **[`docs/implementaciones/DASHBOARD_CACHE_Y_POLLING.md`](implementaciones/DASHBOARD_CACHE_Y_POLLING.md)** (reinicio, TTL, por qué falla el polling).

## Modelo acordado (resumen)

| Acción | En el POST (bancos / transacciones) | Dashboard |
|--------|-------------------------------------|-----------|
| Saldos **mes actual** | Nada de caché; respuesta rápida | NOW vía `/dashboard/state` (~30s y ~0,6s al abrir `/dashboard`) |
| Saldos **mes pasado** | Solo `invalidate` (rápido) | Próxima visita a `/dashboard` = snapshot completo (HIST) |
| Transacción **hoy** | Sin tocar caché dashboard | Igual: NOW en polling |
| Transacción **fecha pasada** | `invalidate` | Regeneración completa al entrar en `/dashboard` |

## 0. Pre-requisitos (si “no funciona nada”)

- [ ] **Reiniciar el servidor** tras cambios en Python (Flask/Gunicorn sigue el código cargado al arrancar).
- [ ] **Ctrl+F5** en `/dashboard` tras cambios en el JS de `dashboard.html`.
- [ ] Comprobar que existe caché: cargar `/dashboard` al menos una vez tras invalidar; si el TTL (p. ej. 15 min en local) expiró, `/dashboard/state` devuelve `has_cache: false` y **el polling no actualiza** hasta volver a cargar `/dashboard`.
- [ ] Tras operaciones que **invalidan** el caché (fecha pasada), abrir de nuevo `/dashboard` en esa pestaña o esperar a que otra acción regenere el caché.

## Leyenda

- [ ] Pendiente de ejecutar
- [x] Completada

## 1. TTL y comportamiento básico del cache

1.1 **TTL (local / producción)**

- [x] Borrar el cache del dashboard desde Admin → Cache para tu usuario.
- [x] Cargar `/dashboard` una vez.
- [x] Comprobar TTL según `DASHBOARD_CACHE_MINUTES` en `.env` / `config.py` (local suele ser 15 min; deploy puede ser 10080 min).

```bash
cd /home/ssoo/www
source venv/bin/activate
PYTHONPATH=/home/ssoo/www python - << 'EOF'
from app import create_app
from app.models import User, DashboardSummaryCache

app = create_app('development')
with app.app_context():
    u = User.query.first()
    cache = DashboardSummaryCache.query.filter_by(user_id=u.id).first()
    print('created_at', cache.created_at)
    print('expires_at', cache.expires_at)
    ttl_min = (cache.expires_at - cache.created_at).total_seconds() / 60
    print('ttl_minutes', ttl_min)
EOF
```

1.2 **No recalcular sin cambios (local)**

- [x] Con el cache recién creado, dejar la pestaña del dashboard abierta al menos 20 minutos (si TTL > 20 min).
- [x] Pulsar F5 y comprobar que el dashboard carga y el caché sigue siendo válido o se regenera según TTL.

## 2. Invalidación fina (hoy vs pasado) – local

2.1 **Editar transacción con fecha de hoy (UTC)**

- [ ] Abrir `/dashboard`, anotar patrimonio / último punto del gráfico.
- [ ] Editar una transacción con `transaction_date` = **hoy en UTC** (o coherente con el criterio del servidor).
- [ ] En ≤30 s (polling): patrimonio, cambios, **último mes del gráfico**, donut y “Actualizado hace X min” coherentes **sin F5**.
- [ ] Opcional: script para comprobar que el histórico no crece de golpe (recompute parcial):

```bash
PYTHONPATH=/home/ssoo/www python - << 'EOF'
from app import create_app
from app.models import User, DashboardSummaryCache

app = create_app('development')
with app.app_context():
    u = User.query.first()
    cache = DashboardSummaryCache.query.filter_by(user_id=u.id).first()
    data = cache.cached_data or {}
    print('len_history', len((data.get('history_block') or {}).get('history') or data.get('history') or []))
EOF
```

2.2 **Editar transacción con fecha pasada**

- [ ] Editar transacción de hace meses.
- [ ] Tras invalidación, **recargar `/dashboard`** (o nueva visita): datos correctos; puede haberse recalculado el histórico completo.

## 3. `/dashboard/state` y actualización en vivo – local

3.1 **Respuesta sin cache**

- [x] Invalidar cache (Admin → Cache).
- [x] `curl` con sesión: `{"has_cache": false}`.

3.2 **Respuesta con cache**

- [x] Cargar `/dashboard`, luego `GET /dashboard/state`: `has_cache: true`, `meta.version` y `meta._cached_at` presentes (si faltaba `version` en BD, `get()` la expone igualmente).

3.3 **Actualización sin recarga**

- [ ] Dashboard abierto; en otra shell:

```bash
cd /home/ssoo/www
source venv/bin/activate
PYTHONPATH=/home/ssoo/www python docs/scripts/update_dashboard_cache.py <user_id_o_username>
```

- [ ] En ≤30 s: sin recarga completa, actualización de patrimonio/gráficos si el script cambió datos; etiqueta “Actualizado hace X min” se acerca a 0.

3.4 **UI + timestamps (implementado)**

- [x] Sin parpadeo de patrimonio si la huella (`meta.version` / `_cached_at`) no cambia.
- [x] `meta._cached_at` en ISO UTC (`Z`); staleness desde ese valor.

3.5 **Criterio unificado por fecha (implementado)**

- [x] Hoy / mes actual → `recompute_current_from_cache` (fallback `invalidate`).
- [x] Pasado → `invalidate`.

3.6 **Polling sin cambios (≥90 s)**

- [ ] Tres ciclos de polling sin tocar datos: sin animación de patrimonio ni parpadeos.

3.7 **“Actualizado hace X min”**

- [ ] Tras `update_dashboard_cache.py`, en ≤30 s la etiqueta refleja cache reciente.

3.8 **Update real**

- [ ] Script o edición de hoy: gráfico evolución (último punto), donut, ingresos/gastos, proyección si aplica.

3.9 **Operación “hoy” en cualquier módulo**

- [ ] Donde esté cableado `touch_for_dates` / invalidación coherente: dashboard vía polling en ≤30 s con caché válido.

3.10 **Operación en el pasado**

- [ ] Invalidación; F5 en `/dashboard` para ver cambios históricos.

## 4. Regresión de UI – local

4.1 **Aspecto general**

- [ ] Sin errores en consola (`applyDashboardUpdate` loguea error si algo falla en un gráfico concreto).

4.2 **CRUD transacciones, ingresos, gastos, bancos, deudas, inmuebles**

- [ ] Dashboard coherente tras cada flujo (recordar F5 si el caché se invalidó por completo).

## 5. Checklist rápido de depuración

| Síntoma | Acción |
|---------|--------|
| Polling no hace nada | ¿`has_cache: true` en `/dashboard/state`? Si no, recargar `/dashboard`. |
| Cambié Python y no se nota | Reiniciar servidor. |
| Cambié JS y no se nota | Ctrl+F5. |
| Edité “hoy” y no actualiza | Fecha de la TX en UTC vs “hoy” servidor; consola por errores JS. |
