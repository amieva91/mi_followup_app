# Estrategia de tests en producción (followup.fit / VM GCP)

## Resumen

| Qué | Dónde | BD | Cuándo |
|-----|-------|-----|--------|
| **Smoke tests** (`pytest -m smoke`) | **Servidor** `/var/www/followup` | **En memoria** (`TESTING`) | Tras cada deploy |
| **Verificación jobs** | Servidor | Solo lectura crons/systemd | Tras deploy o manual |
| **Tests unitarios** (valoración, SG…) | Servidor o local | En memoria | Opcional `--all` |
| **Datos reales** (`followup.db`) | — | **No se usa en pytest** | — |

Los smoke tests deben ejecutarse **en el mismo entorno que los crons** (misma VM, mismo venv, mismo código desplegado), pero **sin escribir en la BD de producción**.

## Por qué no pytest contra `followup.db`

- Crear/borrar usuarios y datos de prueba **contaminaría** tu cartera real.
- Compite con Gunicorn, cron y `followup-jobs` por locks SQLite.
- Un test que falle a mitad puede dejar transacciones a medias.

Por eso `TestingConfig` usa `sqlite:///:memory:`.

## Crons y scripts archivados

Tras la Fase 0 (Jul 2026), **ningún cron ni systemd** invoca scripts de `scripts/archive/app_services_legacy/`.

Jobs reales en producción:

| Job | Comando |
|-----|---------|
| Precios | `flask price-poll-one` |
| Caché | `flask cache-rebuild-worker-once` |
| Benchmarks | `flask benchmark-global-daily-once` |
| Consenso analistas | `flask analyst-consensus-refresh-stale` |
| Macro estrategia | `flask global-strategy-macro-daily-once` |
| Tipos de interés | `python scripts/refresh_interest_rate_context_snapshot.py` |
| Informes IA | `python -m app.jobs_worker_main` (systemd) |
| Web | `gunicorn run:app` (systemd) |

Los ~78 scripts movidos a `scripts/archive/` eran **herramientas manuales de depuración** (OpenFIGI, parsers DeGiro, etc.), no entrada de cron.

Comprobar en cualquier momento:

```bash
./scripts/verify_production_jobs.sh
```

## Comandos en el servidor

```bash
cd /var/www/followup
sudo -u followup ./scripts/verify_production_jobs.sh
sudo -u followup ./scripts/run_smoke_tests.sh
sudo -u followup ./scripts/run_smoke_tests.sh --all   # + unitarios
```

Tras deploy experimental, `deploy-experimental-branch.sh` lanza smoke tests automáticamente.

## Qué cubren los smoke tests

Ver `tests/smoke_routes_test.py`: login, rutas protegidas, admin, APIs watchlist, CLI `price-poll-one` / `cache-rebuild-worker-once`, CSRF, invalidación de caché.

**No sustituyen** probar import CSV con tus ficheros reales ni informes Gemini en la UI; detectan “la app no arranca” o “ruta crítica rota”.

## Si necesitas validar un script archivado

Ruta nueva:

```bash
PYTHONPATH=. python scripts/archive/app_services_legacy/<script>.py
```

No volver a colocarlo en `app/services/`.

## Relacionado

- `scripts/README_CRONS.md` — inventario crons
- `docs/ARQUITECTURA_JOBS_Y_CONCURRENCIA.md` — procesos y locks
- `docs/PLAN_REFACTOR_MEJORAS_2026.md` — Fase 1 tests
