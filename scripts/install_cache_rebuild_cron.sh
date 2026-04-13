#!/usr/bin/env bash
# Inventario de crons del proyecto: scripts/README_CRONS.md
#
# Instala o actualiza entradas cron para el worker de rebuild de cachés.
# Ejecuta cada 30s usando dos líneas:
# - en el segundo 0 de cada minuto
# - en el segundo 30 (sleep 30)
#
# Uso:
#   ./scripts/install_cache_rebuild_cron.sh
#   ./scripts/install_cache_rebuild_cron.sh --dev
#   ./scripts/install_cache_rebuild_cron.sh --dry-run
#   ./scripts/install_cache_rebuild_cron.sh --remove

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MARKER_A="followup-cache-rebuild-worker-0s"
MARKER_B="followup-cache-rebuild-worker-30s"
CRON_TAG_A="# ${MARKER_A}"
CRON_TAG_B="# ${MARKER_B}"

DRY_RUN=0
REMOVE=0
FLASK_ENV_CRON="production"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --remove) REMOVE=1 ;;
    --dev) FLASK_ENV_CRON="development" ;;
    -h|--help)
      sed -n '1,20p' "$0"
      exit 0
      ;;
  esac
done

LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/cache_rebuild_worker.log"

FLASK_BIN="${PROJECT_ROOT}/venv/bin/flask"
if [[ ! -x "$FLASK_BIN" ]]; then
  echo "Error: no existe ${FLASK_BIN} (ejecutable)." >&2
  exit 1
fi

LOCK_FILE="${PROJECT_ROOT}/instance/cache_rebuild_worker.cron.flock"
# Cron-level lock (non-blocking) para evitar acumulación de procesos cuando un FULL tarda > 30s.
# Si hay un worker corriendo, el tick sale sin hacer nada.
BASE_CMD="cd \"${PROJECT_ROOT}\" && mkdir -p \"${PROJECT_ROOT}/instance\" && flock -n \"${LOCK_FILE}\" -c 'FLASK_APP=run.py FLASK_ENV=${FLASK_ENV_CRON} \"${FLASK_BIN}\" cache-rebuild-worker-once' >> \"${LOG_FILE}\" 2>&1"
CRON_LINE_A="* * * * * ${BASE_CMD} ${CRON_TAG_A}"
CRON_LINE_B="* * * * * sleep 30; ${BASE_CMD} ${CRON_TAG_B}"

if [[ "$REMOVE" -eq 1 ]]; then
  TMP="$(mktemp)"
  crontab -l 2>/dev/null | grep -vF "${CRON_TAG_A}" | grep -vF "${CRON_TAG_B}" > "$TMP" || true
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "--- crontab resultante (dry-run) ---"
    cat "$TMP"
    rm -f "$TMP"
    exit 0
  fi
  if [[ ! -s "$TMP" ]]; then
    rm -f "$TMP"
    crontab -r 2>/dev/null || true
  else
    crontab "$TMP"
    rm -f "$TMP"
  fi
  echo "Entradas de worker eliminadas."
  exit 0
fi

echo "Proyecto: ${PROJECT_ROOT}"
echo "Flask:    ${FLASK_BIN}"
echo "Log:      ${LOG_FILE}"
echo "Entorno:  FLASK_ENV=${FLASK_ENV_CRON}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo ""
  echo "$CRON_LINE_A"
  echo "$CRON_LINE_B"
  exit 0
fi

TMP="$(mktemp)"
crontab -l 2>/dev/null | grep -vF "${CRON_TAG_A}" | grep -vF "${CRON_TAG_B}" > "$TMP" || true
echo "$CRON_LINE_A" >> "$TMP"
echo "$CRON_LINE_B" >> "$TMP"
crontab "$TMP"
rm -f "$TMP"

echo "Cron de cache worker instalado. Comprueba con: crontab -l"
