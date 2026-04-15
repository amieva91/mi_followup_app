#!/usr/bin/env bash
# Inventario de crons del proyecto: scripts/README_CRONS.md
#
# Cron: mantenimiento global de series diarias de benchmarks (Yahoo si hay día nuevo).
# Cada 15 minutos con flock para no solapar.
#
# Uso:
#   ./scripts/install_benchmark_global_cron.sh
#   ./scripts/install_benchmark_global_cron.sh --dev
#   ./scripts/install_benchmark_global_cron.sh --dry-run
#   ./scripts/install_benchmark_global_cron.sh --remove

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MARKER="followup-benchmark-global-daily"
CRON_TAG="# ${MARKER}"

DRY_RUN=0
REMOVE=0
FLASK_ENV_CRON="production"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --remove) REMOVE=1 ;;
    --dev) FLASK_ENV_CRON="development" ;;
    -h|--help)
      sed -n '1,15p' "$0"
      exit 0
      ;;
  esac
done

LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/benchmark_global_daily_cron.log"

FLASK_BIN="${PROJECT_ROOT}/venv/bin/flask"
if [[ ! -x "$FLASK_BIN" ]]; then
  echo "Error: no existe ${FLASK_BIN}" >&2
  exit 1
fi

LOCK_FILE="${PROJECT_ROOT}/instance/benchmark_global_daily.cron.flock"
BASE_CMD="cd \"${PROJECT_ROOT}\" && mkdir -p \"${PROJECT_ROOT}/instance\" && flock -n \"${LOCK_FILE}\" -c 'FLASK_APP=run.py FLASK_ENV=${FLASK_ENV_CRON} \"${FLASK_BIN}\" benchmark-global-daily-once' >> \"${LOG_FILE}\" 2>&1"
CRON_LINE="*/15 * * * * ${BASE_CMD} ${CRON_TAG}"

if [[ "$REMOVE" -eq 1 ]]; then
  TMP="$(mktemp)"
  crontab -l 2>/dev/null | grep -vF "${CRON_TAG}" > "$TMP" || true
  if [[ ! -s "$TMP" ]]; then
    rm -f "$TMP"
    crontab -r 2>/dev/null || true
  else
    crontab "$TMP"
    rm -f "$TMP"
  fi
  echo "Entrada benchmark-global-daily eliminada."
  exit 0
fi

echo "Proyecto: ${PROJECT_ROOT}"
echo "Flask:    ${FLASK_BIN}"
echo "Log:      ${LOG_FILE}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "$CRON_LINE"
  exit 0
fi

TMP="$(mktemp)"
crontab -l 2>/dev/null | grep -vF "${CRON_TAG}" > "$TMP" || true
echo "$CRON_LINE" >> "$TMP"
crontab "$TMP"
rm -f "$TMP"

echo "Cron benchmark-global-daily instalado (cada 15 min). crontab -l"
