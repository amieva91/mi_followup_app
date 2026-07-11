#!/usr/bin/env bash
# Smoke tests en el servidor (VM GCP / entorno desplegado).
#
# Se ejecutan DESPUÉS del deploy, con el mismo código y venv que producción.
# Usan FLASK_ENV=testing → BD SQLite EN MEMORIA (no toca instance/followup.db).
#
# Uso (en /var/www/followup):
#   ./scripts/run_smoke_tests.sh
#   ./scripts/run_smoke_tests.sh --all   # incluye tests unitarios (valoración, etc.)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

RUN_ALL=0
for arg in "$@"; do
  case "$arg" in
    --all) RUN_ALL=1 ;;
    -h|--help)
      sed -n '1,12p' "$0"
      exit 0
      ;;
  esac
done

if [[ ! -x "$PROJECT_ROOT/venv/bin/pytest" ]]; then
  echo "Error: no existe venv/bin/pytest en $PROJECT_ROOT" >&2
  exit 1
fi

export FLASK_APP=run.py
# Importante: testing → sqlite:///:memory: (ver config.TestingConfig)
export FLASK_ENV=testing

echo "=== Smoke tests (servidor, BD en memoria) ==="
echo "Proyecto: $PROJECT_ROOT"
echo ""

if [[ "$RUN_ALL" -eq 1 ]]; then
  "$PROJECT_ROOT/venv/bin/pytest" tests/ -q --tb=line
else
  "$PROJECT_ROOT/venv/bin/pytest" -m smoke -q --tb=line
fi

echo ""
echo "OK: smoke tests completados"
