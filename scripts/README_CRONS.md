# Crons instalados por scripts (`install_*_cron.sh`)

Todos los scripts viven en `scripts/`, son idempotentes (re-ejecutar sustituye la línea marcada) y aceptan `--dev` (FLASK_ENV=development), `--dry-run` y `--remove` donde se documenta en cada uno.

Configuracion recomendada en local:
- Desarrollo interactivo de la app/web: `FLASK_ENV=development`.
- Crons locales para reproducir comportamiento de produccion: `FLASK_ENV=production`.
- Si quieres que los jobs locales se comporten como en el servidor, instala los crons sin `--dev`.

| Script | Frecuencia | Comando | Log |
|--------|------------|---------|-----|
| `install_price_poll_cron.sh` | Cada minuto (`* * * * *`) | `flask price-poll-one` | `logs/price_poll_cron.log` |
| `install_cache_rebuild_cron.sh` | Dos ticks por minuto (s 0 y s 30) | `flask cache-rebuild-worker-once` | `logs/cache_rebuild_worker.log` |
| `install_benchmark_global_cron.sh` | Cada 15 min (`*/15 * * * *`) | `flask benchmark-global-daily-once` | `logs/benchmark_global_daily_cron.log` |
| `install_analyst_consensus_cron.sh` | Cada día a las 00:00 (`0 0 * * *`, hora del servidor) | `flask analyst-consensus-refresh-stale` | `logs/analyst_consensus_cron.log` |
| `install_global_strategy_macro_cron.sh` | 1× día 22:35 (`35 22 * * *`, `TZ=Europe/Madrid`) | `flask global-strategy-macro-daily-once` | `logs/global_strategy_macro_daily_cron.log` |
| `install_interest_rate_context_cron.sh` | 1× día 07:00 UTC (`0 7 * * *`) | `python scripts/refresh_interest_rate_context_snapshot.py` | `logs/interest_rate_context_cron.log` |

- **Locks:** cada script usa `flock` en `instance/*.flock` para no solapar ejecuciones. Con `flock -n`, si el lock ya está cogido, **esa invocación sale al instante sin ejecutar el comando** (no cancela al otro proceso ni queda en cola; el tick simplemente se omite). El siguiente cron volverá a intentarlo.
- **Medianoche (00:00, hora del servidor):** además de `analyst-consensus-refresh-stale`, suelen dispararse el mismo minuto `price-poll-one`, `cache-rebuild-worker-once` (también a +30 s) y, si cae en cuarto hora, `benchmark-global-daily-once`. Cada job usa su propio `flock`; no se anulan entre sí, pero pueden competir por CPU/BD. En GCP la hora del servidor suele ser **UTC** salvo que configures `TZ` en la línea de cron.
- **Index comparison (gráfico):** no hay cron de servidor para esa pantalla. El navegador hace polling a `/portfolio/api/benchmarks` cada **6 horas** (constante `BENCHMARK_CHART_POLL_INTERVAL_MS` en `app/static/js/charts.js`). Los crons de arriba alimentan datos globales (`benchmark_global_quote`, `benchmark_global_daily`, cachés) que luego consume el caché de comparación al servir la API.

## Instalación

**Todos los crons** (recomendado en deploy y en servidor):

```bash
./scripts/install_all_crons.sh
```

**Uno a uno** (desde la raíz del repo, con `venv` creado):

```bash
./scripts/install_price_poll_cron.sh
./scripts/install_cache_rebuild_cron.sh
./scripts/install_benchmark_global_cron.sh
./scripts/install_analyst_consensus_cron.sh
./scripts/install_global_strategy_macro_cron.sh
./scripts/install_interest_rate_context_cron.sh
```

Para desarrollo local, añade `--dev` a `install_all_crons.sh` o a cada script.

**Comprobar sin instalar** (solo lectura del crontab del usuario actual):

```bash
./scripts/verify_crons_installed.sh
```

En producción (usuario `followup`):

```bash
sudo -u followup bash -lc 'cd /var/www/followup && ./scripts/verify_crons_installed.sh'
```

Los deploy `subidaPRO.sh`, `scripts/deploy-followup-production.sh` y `scripts/deploy-experimental-branch.sh` ejecutan `install_all_crons.sh` tras migraciones.
