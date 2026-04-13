# Crons instalados por scripts (`install_*_cron.sh`)

Todos los scripts viven en `scripts/`, son idempotentes (re-ejecutar sustituye la línea marcada) y aceptan `--dev` (FLASK_ENV=development), `--dry-run` y `--remove` donde se documenta en cada uno.

| Script | Frecuencia | Comando Flask | Log |
|--------|------------|----------------|-----|
| `install_price_poll_cron.sh` | Cada minuto (`* * * * *`) | `price-poll-one` | `logs/price_poll_cron.log` |
| `install_benchmark_global_cron.sh` | Cada 15 min (`*/15 * * * *`) | `benchmark-global-daily-once` | `logs/benchmark_global_daily_cron.log` |
| `install_cache_rebuild_cron.sh` | Dos ticks por minuto (s 0 y s 30) | `cache-rebuild-worker-once` | `logs/cache_rebuild_worker.log` |

- **Locks:** cada script usa `flock` en `instance/*.flock` para no solapar ejecuciones.
- **Index comparison (gráfico):** no hay cron de servidor para esa pantalla. El navegador hace polling a `/portfolio/api/benchmarks` cada **6 horas** (constante `BENCHMARK_CHART_POLL_INTERVAL_MS` en `app/static/js/charts.js`). Los crons de arriba alimentan datos globales (`benchmark_global_quote`, `benchmark_global_daily`, cachés) que luego consume el caché de comparación al servir la API.

**Instalación en un entorno:** desde la raíz del repo, con `venv` creado:

```bash
./scripts/install_price_poll_cron.sh
./scripts/install_benchmark_global_cron.sh
./scripts/install_cache_rebuild_cron.sh
```

Para desarrollo local: añadir `--dev` a cada uno. Comprobar con `crontab -l`.
