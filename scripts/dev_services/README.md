# Scripts de desarrollo y debug

Scripts temporales de análisis, debug y pruebas que no forman parte del código de producción.

## Uso

Ejecutar desde la raíz del proyecto:

```bash
cd ~/www
PYTHONPATH=. python scripts/dev_services/nombre_script.py
```

## Convención

- Los scripts aquí son **solo para desarrollo**: debug de parsers CSV, análisis de assets, pruebas de APIs.
- No deben importarse desde el código de producción.
- Scripts en `app/services/` con patrones `debug_*`, `analyze_*`, etc. están ignorados por git.
