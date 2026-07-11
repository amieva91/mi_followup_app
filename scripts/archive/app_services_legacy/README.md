# Scripts legacy (ex `app/services/`)

Scripts de investigación, depuración y pruebas manuales que vivían en el paquete de producción `app/services/`.

**Movidos en Fase 0** (Jul 2026). Ninguno era importado por rutas, workers, crons ni tests de pytest.

## Uso

Desde la raíz del repo, con venv activo:

```bash
cd /var/www/followup   # o raíz local
source venv/bin/activate
export FLASK_APP=run.py FLASK_ENV=production

python scripts/archive/app_services_legacy/test_openfigi_api.py
python scripts/archive/app_services_legacy/update_prices.py
```

Algunos scripts asumen `sys.path` relativo al antiguo sitio; si fallan el import, ejecutar con:

```bash
PYTHONPATH=. python scripts/archive/app_services_legacy/<script>.py
```

## Sustitutos en producción

| Legacy | Usar en su lugar |
|--------|------------------|
| `importer.py` (eliminado) | `app/services/importer_v2.py` |
| `update_prices.py` | `flask price-poll-one` (cron) o `PriceUpdater` en `market_data` |
| `test_import.py`, parsers debug | `tests/` + import web `/portfolio/import` |
| `clean_all_portfolio.py` | Operaciones admin / SQL con backup |

## No mover de vuelta a `app/services/`

Mantener el paquete `app/services/` solo para código importado en runtime de la app.
